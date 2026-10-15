"""Development-stage analysis: ablations, timing, confidence intervals, errors.

Everything here uses train and development data only. The test split stays
locked; these are the plan's section 8 analyses run on development data so
they can inform the freeze. The frozen test runs after G10 are the reported
results, and the same analyses are repeated on them.

1. **Ablations** (plan section 8), each its own run folder:
   - ``A1-noAnalyzer``: bare specification, no enrichment calls
   - ``A1-noReasoning``: the Architect's documented fallback ordering, no planning calls
   - ``A1-noSelection``: the Architect's first choice, not the best development score
   - ``A1-oneCandidate``: one predeclared configuration with the enriched specification
   - ``A1-noRepair``: the selected configuration with the repair retry disabled
2. **Uncached timing** for A1's selected pipeline and B1: 5 warm-up + 50 cases
   with the cache disabled, the only source of latency figures.
3. **Paired bootstrap 95% intervals** on development data for A1 against B1,
   B3-k and the development ceiling, resampling the same cases for both.
4. **Error analysis** of A1's development predictions by the plan's categories.

Writes run folders plus ``reports/dev_analysis.md`` and ``.json``.

Usage:
    python scripts/run_dev_analysis.py
    python scripts/run_dev_analysis.py --projects P1 --skip-timing
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.access import access_for  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.architect.design_run import run_design  # noqa: E402
from src.evaluation.runner import time_requests  # noqa: E402
from src.evaluation.runs import new_run  # noqa: E402
from src.evaluation.scorer import STATUS_OK, STATUS_OOS, Prediction, score  # noqa: E402
from src.evaluation.span_rule import locate_entities  # noqa: E402
from src.llm.client import make_client, ollama_version  # noqa: E402
from src.pipelines.catalogue import B1_CONFIG_ID, ConfigRunner, get_config  # noqa: E402
from src.pipelines.examples import ExampleSelector  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SINGLE_CALL_P95_S = 0.59
CEILING_CONFIG = "schema-sim-llm"  # best of all 12 on both projects (FINDINGS F1)
BOOTSTRAP_SAMPLES = 1000
BOOTSTRAP_SEED = 20261016


def fmt(value, digits=3):
    return "n/a" if value is None else f"{value:.{digits}f}"


def predict(config_id, spec, client, pool, dev, threshold, allow_repair=True):
    runner = ConfigRunner(
        config=get_config(config_id), spec=spec, client=client,
        selector=ExampleSelector(list(pool)), oos_threshold=threshold,
        allow_repair=allow_repair,
    )
    predictions, logical, physical = [], 0, 0
    for case in dev:
        outcome = runner.run_case(case)
        predictions.append(outcome.prediction)
        logical += outcome.logical_calls
        physical += outcome.physical_calls
    return predictions, logical, physical


def load_b3k(project, dev):
    runs = sorted((ROOT / "runs").glob(f"*_{project}_B3-k_*"))
    if not runs:
        return None, None
    path = runs[-1] / "predictions.jsonl"
    by_id = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            by_id[row["case_id"]] = Prediction(
                case_id=row["case_id"], status=row["status"],
                intent=row.get("predicted_intent"),
                entities=row.get("predicted_entities") or [],
                schema_valid_final=bool(row.get("schema_valid_final", True)),
            )
    return [by_id.get(c["case_id"], Prediction(c["case_id"], "missing")) for c in dev], runs[-1].name


def write_run(project, system, config, dev, predictions, metrics, spec):
    with new_run(
        project, system, 0, config,
        data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]},
    ) as log:
        for case, p in zip(dev, predictions):
            log.log_prediction(
                case_id=case["case_id"], gold_intent=case["true_intent"],
                gold_in_scope=case["in_scope"], status=p.status,
                predicted_intent=p.intent, predicted_entities=p.entities,
                schema_valid_raw=p.schema_valid_raw, schema_valid_final=p.schema_valid_final,
                retries=p.retries, error=p.error,
            )
        log.write_metrics(metrics)
        log.finish(status="complete", n_cases=len(dev))
        return log.run_id


# -- bootstrap ---------------------------------------------------------------


def paired_bootstrap(dev, preds_a, preds_b, labels):
    """Paired percentile bootstrap of (A - B) for intent and entity F1."""
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(dev)
    diffs = {"intent_macro_f1": [], "entity_span_f1": []}
    for _ in range(BOOTSTRAP_SAMPLES):
        idx = [rng.randrange(n) for _ in range(n)]
        # Resampled cases need unique ids so the scorer keeps duplicates apart.
        cases = [dict(dev[i], case_id=f"{dev[i]['case_id']}#{k}") for k, i in enumerate(idx)]
        pa = [Prediction(**{**vars(preds_a[i]), "case_id": cases[k]["case_id"]}) for k, i in enumerate(idx)]
        pb = [Prediction(**{**vars(preds_b[i]), "case_id": cases[k]["case_id"]}) for k, i in enumerate(idx)]
        ma = score(cases, pa, labels=labels)["primary"]
        mb = score(cases, pb, labels=labels)["primary"]
        for key in diffs:
            diffs[key].append(ma[key] - mb[key])
    full_a = score(dev, preds_a, labels=labels)["primary"]
    full_b = score(dev, preds_b, labels=labels)["primary"]
    out = {}
    for key, values in diffs.items():
        values.sort()
        out[key] = {
            "difference": full_a[key] - full_b[key],
            "ci_low": values[int(0.025 * len(values))],
            "ci_high": values[int(0.975 * len(values)) - 1],
            "share_a_better": sum(v > 0 for v in values) / len(values),
        }
    return out


# -- error analysis ------------------------------------------------------------


def classify_errors(dev, predictions):
    counts = Counter()
    confusions = Counter()
    examples = {}

    def note(kind, case, detail=""):
        counts[kind] += 1
        examples.setdefault(kind, []).append(f"{case['utt']}{(' -> ' + detail) if detail else ''}")

    for case, p in zip(dev, predictions):
        if p.status not in (STATUS_OK, STATUS_OOS):
            note(f"{p.status} output", case, p.error or "")
            continue
        if not case["in_scope"]:
            if p.status == STATUS_OK:
                note("missed out-of-scope (answered an off-topic request)", case, p.intent)
            continue
        if p.status == STATUS_OOS:
            note("incorrect out-of-scope rejection", case)
            continue
        if p.intent != case["true_intent"]:
            confusions[(case["true_intent"], p.intent)] += 1
            note("confused intent", case, f"{p.intent} (gold {case['true_intent']})")

        gold = [(e["type"], e["start"], e["end"]) for e in case.get("entities", [])]
        claimed = set()
        for e in locate_entities(case["utt"], p.entities):
            if not e.supported:
                note("unsupported value (text not in the request)", case, f"{e.type}='{e.text}'")
                continue
            span = (e.type, e.start, e.end)
            if span in gold:
                claimed.add(span)
                continue
            same_span = [g for g in gold if g[1] == e.start and g[2] == e.end]
            overlap = [g for g in gold if g[1] < e.end and e.start < g[2]]
            if same_span:
                claimed.add(same_span[0])
                note("wrong entity type", case, f"'{e.text}' as {e.type} (gold {same_span[0][0]})")
            elif any(g[0] == e.type for g in overlap):
                claimed.update(g for g in overlap if g[0] == e.type)
                note("wrong entity boundary", case, f"{e.type}='{e.text}'")
            else:
                note("spurious entity", case, f"{e.type}='{e.text}'")
        for g in gold:
            if g not in claimed:
                note("missed entity", case, f"{g[0]}='{case['utt'][g[1]:g[2]]}'")

    return {
        "counts": dict(counts.most_common()),
        "top_confusions": [
            {"gold": g, "predicted": p, "count": n} for (g, p), n in confusions.most_common(5)
        ],
        "examples": {k: v[:3] for k, v in examples.items()},
    }


# -- main -------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Development-stage analysis")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--projects", nargs="+", default=["P1", "P2"])
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--skip-timing", action="store_true")
    args = parser.parse_args()

    try:
        ollama_version(args.host)
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach Ollama at {args.host}: {exc}", file=sys.stderr)
        return 2

    client = make_client(args.model, host=args.host, cache_dir=ROOT / "cache")
    report = {"generated": time.strftime("%Y-%m-%d %H:%M"), "split": "dev", "projects": {}}

    for project in args.projects:
        print(f"\n=== {project} ===")
        spec = load_spec(project)
        access = access_for(spec)
        pool = load_cases(access.train_path)
        dev = load_cases(access.dev_path)
        labels = spec.intent_names
        kwargs = dict(load_cases=load_cases, single_call_p95_s=SINGLE_CALL_P95_S)

        full = run_design(spec, access, runtime_client=client, planning_client=client, **kwargs)
        enriched = full.analysis.spec
        threshold = full.oos_threshold.threshold
        selected = full.selected_config_id
        a1_preds, _, _ = predict(selected, enriched, client, pool, dev, threshold)
        a1_metrics = score(dev, a1_preds, labels=labels)
        print(f"  A1 {selected}: intent {fmt(a1_metrics['primary']['intent_macro_f1'])}")

        result = {"a1": {"config": selected, "primary": a1_metrics["primary"]}, "ablations": {}}
        base_config = {
            "split": "dev", "model": client.model, "model_digest": client.model_digest,
            "settings": client.settings, "cache_enabled": True,
            "score_note": "development-stage ablation; the reported ablations come from the frozen test runs",
            "full_system_selected": selected,
        }

        # ---- ablations ------------------------------------------------------
        def ablation(name, config_id, spec_used, why, design=None, allow_repair=True):
            preds, logical, physical = predict(
                config_id, spec_used, client, pool, dev, threshold, allow_repair=allow_repair
            )
            metrics = score(dev, preds, labels=labels)
            extra = {"ablation": name, "config_id": config_id, "removes": why,
                     "allow_repair": allow_repair, "enriched_spec": spec_used.enriched}
            if design is not None:
                extra["design"] = design.as_dict()["design"]
            run_id = write_run(project, name, {**base_config, **extra}, dev, preds, metrics, spec_used)
            p = metrics["primary"]
            result["ablations"][name] = {"run_id": run_id, "config": config_id, "removes": why,
                                         "primary": p, "calls": {"logical": logical, "physical": physical}}
            print(f"  {name:16} {config_id:20} intent {fmt(p['intent_macro_f1'])} "
                  f"entity {fmt(p['entity_span_f1'])} schema-before-repair "
                  f"{fmt(p['schema_validity_before_repair'])} ({physical} uncached calls)")

        no_an = run_design(spec, access, runtime_client=client, planning_client=client, enrich=False, **kwargs)
        if no_an.selected_config_id:
            ablation("A1-noAnalyzer", no_an.selected_config_id, no_an.analysis.spec,
                     "Analyzer enrichment: bare specification, no descriptions", design=no_an)
        no_reason = run_design(spec, access, runtime_client=client, planning_client=None, **kwargs)
        if no_reason.selected_config_id:
            ablation("A1-noReasoning", no_reason.selected_config_id, enriched,
                     "Architect reasoning: documented fallback ordering, no planning calls", design=no_reason)
        first_choice = full.design.attempts[0].config_id
        ablation("A1-noSelection", first_choice, enriched,
                 "evaluation-driven selection: the Architect's first choice, unscored")
        ablation("A1-oneCandidate", B1_CONFIG_ID, enriched,
                 "candidate search: one predeclared configuration, enriched specification")
        ablation("A1-noRepair", selected, enriched,
                 "post-validation repair: raw outputs only", allow_repair=False)

        # ---- confidence intervals ---------------------------------------------
        b1_preds, _, _ = predict(B1_CONFIG_ID, spec, client, pool, dev, threshold)
        ceiling_preds, _, _ = predict(CEILING_CONFIG, enriched, client, pool, dev, threshold)
        b3_preds, b3_run = load_b3k(project, dev)
        comparisons = {"A1 vs B1": b1_preds, f"A1 vs ceiling ({CEILING_CONFIG})": ceiling_preds}
        if b3_preds:
            comparisons[f"A1 vs B3-k ({b3_run})"] = b3_preds
        result["bootstrap"] = {}
        for name, other in comparisons.items():
            ci = paired_bootstrap(dev, a1_preds, other, labels)
            result["bootstrap"][name] = ci
            i = ci["intent_macro_f1"]
            print(f"  {name:40} intent diff {i['difference']:+.3f} "
                  f"[{i['ci_low']:+.3f}, {i['ci_high']:+.3f}]")

        # ---- error analysis -----------------------------------------------------
        result["errors"] = classify_errors(dev, a1_preds)
        print(f"  A1 errors: {result['errors']['counts']}")

        # ---- uncached timing ----------------------------------------------------
        if not args.skip_timing:
            result["timing"] = {}
            for system, config_id, spec_used in (("A1", selected, enriched), ("B1", B1_CONFIG_ID, spec)):
                run_id, lat = time_requests(
                    system=system, config=get_config(config_id), spec=spec_used,
                    client=client, pool=pool, cases=dev, oos_threshold=threshold,
                )
                lat_sorted = sorted(lat)
                median = lat_sorted[len(lat_sorted) // 2] if lat_sorted else None
                p95 = lat_sorted[min(len(lat_sorted) - 1, int(0.95 * len(lat_sorted)))] if lat_sorted else None
                result["timing"][system] = {"run_id": run_id, "config": config_id, "n": len(lat),
                                            "median_s": median, "p95_s": p95}
                print(f"  timing {system} {config_id}: median {fmt(median, 2)}s p95 {fmt(p95, 2)}s (n={len(lat)})")

        report["projects"][project] = result

    out_json = ROOT / "reports" / "dev_analysis.json"
    out_json.parent.mkdir(exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {out_json.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
