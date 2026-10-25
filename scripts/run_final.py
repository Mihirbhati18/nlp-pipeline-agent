"""G11 final evaluation: every system's frozen choice, scored on the test split.

Each system's choice is made on development data exactly as before (design
runs, B4 search, B2's worksheet, dev-tuned thresholds); all of that replays
from the prediction cache. Only then is the chosen pipeline applied to the
target split. Nothing is chosen, tuned or selected on test data.

    python scripts/run_final.py --split dev                         # dry run before the freeze
    python scripts/run_final.py --count                             # exact planned test calls
    python scripts/run_final.py --split test --freeze-commit <hash> # the final evaluation

Systems: B0, B1, B2 (where a B2 run exists), B4-random (5 seeds), B4-best
(the development-best of all 12), A1, A2 and the A1 ablations. B3 is trained
and scored by scripts/run_b3_local.py --split test. Writes one run folder per
system and reports/final_<split>.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.access import access_for  # noqa: E402
from src.analyzer.analyzer import Analyzer  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.architect.design_run import estimate_p95, make_config_evaluator, run_design  # noqa: E402
from src.baselines.b0_tfidf import B0TfidfClassifier  # noqa: E402
from src.baselines.b4_search import DEFAULT_SEEDS, run_random_seeds, run_search  # noqa: E402
from src.evaluation.runs import new_run  # noqa: E402
from src.evaluation.scorer import score  # noqa: E402
from src.evaluation.thresholds import tune_binary_threshold  # noqa: E402
from src.llm.client import make_client, ollama_version  # noqa: E402
from src.pipelines.catalogue import B1_CONFIG_ID, ConfigRunner, get_config  # noqa: E402
from src.pipelines.examples import ExampleSelector  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SINGLE_CALL_P95_S = 0.59


def latest(pattern: str) -> Path | None:
    found = sorted((ROOT / "runs").glob(pattern))
    return found[-1] if found else None


def plan_systems(project, spec, access, client):
    """Every system's frozen choice, made on development data only.

    Returns a list of (system name, config id, spec to use, allow_repair, how chosen).
    """
    pool = load_cases(access.train_path)
    dev = load_cases(access.dev_path)
    kw = dict(load_cases=load_cases, single_call_p95_s=SINGLE_CALL_P95_S)
    plans = []

    a1 = run_design(spec, access, runtime_client=client, planning_client=client, **kw)
    a2 = run_design(spec, access, runtime_client=client, planning_client=client, architect_version="v2", **kw)
    enriched = a1.analysis.spec
    plans.append(("B1", B1_CONFIG_ID, spec, True, "predeclared design, bare specification"))

    b2_run = latest(f"*_{project}_B2_0")
    if b2_run:
        b2 = json.loads((b2_run / "config.json").read_text(encoding="utf-8"))
        b2_spec = spec.with_descriptions(b2["intent_descriptions"], b2["entity_descriptions"])
        plans.append(("B2", b2["config"]["config_id"], b2_spec, True, f"the person's frozen worksheet choice ({b2_run.name})"))

    evaluate = make_config_evaluator(Analyzer(client=client).analyze(spec, pool).spec, client, pool, dev,
                                     a1.oos_threshold.threshold)
    estimator = lambda c: estimate_p95(c, SINGLE_CALL_P95_S)  # noqa: E731
    for result in run_random_seeds(evaluate_config=evaluate, seeds=DEFAULT_SEEDS, estimate_p95=estimator):
        plans.append((f"B4-random-seed{result.seed}", result.selection.selected.config_id, enriched, True,
                      f"best of 4 random designs, seed {result.seed}, on development data"))
    best = run_search(variant="B4-exhaustive", evaluate_config=evaluate, estimate_p95=estimator)
    plans.append(("B4-best", best.selection.selected.config_id, enriched, True,
                  "best of all 12 designs on development data"))

    plans.append(("A1", a1.selected_config_id, enriched, True, "A1 design run on development data"))
    plans.append(("A2", a2.selected_config_id, a2.analysis.spec, True, "A2 design run on development data"))

    no_an = run_design(spec, access, runtime_client=client, planning_client=client, enrich=False, **kw)
    no_reason = run_design(spec, access, runtime_client=client, planning_client=None, **kw)
    plans += [
        ("A1-noAnalyzer", no_an.selected_config_id, no_an.analysis.spec, True, "ablation: no Analyzer"),
        ("A1-noReasoning", no_reason.selected_config_id, enriched, True, "ablation: fallback order, no reasoning"),
        ("A1-noSelection", a1.design.attempts[0].config_id, enriched, True, "ablation: first choice, unscored"),
        ("A1-oneCandidate", B1_CONFIG_ID, enriched, True, "ablation: one predeclared design"),
        ("A1-noRepair", a1.selected_config_id, enriched, False, "ablation: no repair retry"),
    ]
    return plans, pool, dev, a1.oos_threshold.threshold


def main() -> int:
    parser = argparse.ArgumentParser(description="G11 final evaluation")
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--freeze-commit", help="required for the test split")
    parser.add_argument("--projects", nargs="+", default=["P1", "P2"])
    parser.add_argument("--count", action="store_true", help="print the exact planned test calls and stop")
    parser.add_argument("--model", default="qwen2.5:3b")
    args = parser.parse_args()

    if args.split == "test" and not args.freeze_commit:
        print("the test split needs --freeze-commit <hash>", file=sys.stderr)
        return 2
    try:
        ollama_version()
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach Ollama: {exc}", file=sys.stderr)
        return 2
    client = make_client(args.model, cache_dir=ROOT / "cache")

    spec_mod = importlib.util.spec_from_file_location("run_dev_analysis", ROOT / "scripts" / "run_dev_analysis.py")
    analysis = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(analysis)

    report = {"split": args.split, "freeze_commit": args.freeze_commit,
              "generated": time.strftime("%Y-%m-%d %H:%M"), "projects": {}}
    grand_total = 0
    for project in args.projects:
        spec = load_spec(project)
        access = access_for(spec)
        if args.freeze_commit:
            access = access.release_after_freeze(commit=args.freeze_commit)
        plans, pool, dev, threshold = plan_systems(project, spec, access, client)
        # Counted from the frozen manifest, so the locked test file is never opened before the freeze.
        n_test = json.loads((ROOT / f"data/manifests/{project}.json").read_text(encoding="utf-8"))["counts"]["test_total"]

        if args.count:
            unique = {(cid, id(sp), rep) for _, cid, sp, rep, _ in plans}
            calls = sum(n_test * get_config(cid).calls_per_request for cid, _, _ in unique)
            grand_total += calls
            print(f"{project}: {len(plans)} systems, {len(unique)} distinct pipelines, {n_test} test cases, "
                  f"at most {calls} first-attempt calls (repairs add at most one per call that fails validation; "
                  f"tfidf rejections make fewer)")
            for name, cid, _, rep, why in plans:
                print(f"    {name:20} {cid:22} {'' if rep else '(no repair) '}{why}")
            continue

        target = load_cases(access.test_path if args.split == "test" else access.dev_path)
        labels = spec.intent_names
        selector = ExampleSelector(list(pool))
        results, predictions_by = {}, {}
        print(f"\n=== {project} ({args.split}: {len(target)} cases) ===")

        # B0 first: no model, dev-tuned threshold.
        b0 = B0TfidfClassifier(labels=labels).fit(pool)
        b0_choice = b0.tune(dev)
        preds = b0.predict(target)
        plans_out = [("B0", "tfidf-logreg", None, True, "TF-IDF classifier, threshold tuned on development data")]
        predictions_by["B0"] = preds

        for name, cid, sp, rep, why in plans:
            runner = ConfigRunner(config=get_config(cid), spec=sp, client=client, selector=selector,
                                  oos_threshold=threshold, allow_repair=rep)
            predictions_by[name] = [runner.run_case(c).prediction for c in target]
            plans_out.append((name, cid, sp, rep, why))

        for name, cid, sp, rep, why in plans_out:
            preds = predictions_by[name]
            metrics = score(target, preds, labels=labels)
            with new_run(project, f"{name}-final", 0, {
                "system": name, "split": args.split, "config_id": cid, "how_chosen": why,
                "allow_repair": rep, "freeze_commit": args.freeze_commit, "oos_threshold": threshold,
                "b0_threshold": b0_choice.as_dict() if name == "B0" else None,
                "model": client.model, "model_digest": client.model_digest, "settings": client.settings,
                "data_access": access.as_dict(), "data_sources": spec.source,
            }, data_paths={"pool": spec.source["kshot"], args.split: spec.source[args.split]}) as log:
                for case, p in zip(target, preds):
                    log.log_prediction(case_id=case["case_id"], gold_intent=case["true_intent"],
                                       gold_in_scope=case["in_scope"], status=p.status, predicted_intent=p.intent,
                                       predicted_entities=p.entities, schema_valid_raw=p.schema_valid_raw,
                                       schema_valid_final=p.schema_valid_final, retries=p.retries, error=p.error)
                log.write_metrics(metrics)
                log.finish(status="complete", n_cases=len(target))
                run_id = log.run_id
            prim = metrics["primary"]
            results[name] = {"run_id": run_id, "config": cid, "how_chosen": why,
                             **{k: prim[k] for k in ("intent_macro_f1", "intent_accuracy_in_scope", "entity_span_f1",
                                                     "oos_f1", "schema_validity_after_repair")}}
            print(f"  {name:20} {cid:22} intent {prim['intent_macro_f1']:.3f}  entity {prim['entity_span_f1']:.3f}  "
                  f"oos {prim['oos_f1']:.3f}  schema {prim['schema_validity_after_repair']:.3f}")

        seeds = [results[f"B4-random-seed{s}"]["intent_macro_f1"] for s in DEFAULT_SEEDS]
        b4 = {"mean_intent_macro_f1": statistics.mean(seeds), "min": min(seeds), "max": max(seeds)}
        print(f"  B4-random mean over 5 seeds: {b4['mean_intent_macro_f1']:.3f} ({b4['min']:.3f}-{b4['max']:.3f})")

        intervals = {}
        for a, other in (("A2", "B1"), ("A1", "B1"), ("A2", "A1"), ("A2", "B2"), ("A2", "B4-best"), ("A1", "B4-best")):
            if a in predictions_by and other in predictions_by:
                ci = analysis.paired_bootstrap(target, predictions_by[a], predictions_by[other], labels)
                intervals[f"{a} vs {other}"] = ci
                i = ci["intent_macro_f1"]
                print(f"  {a} vs {other:8} intent {i['difference']:+.3f} [{i['ci_low']:+.3f}, {i['ci_high']:+.3f}]")
        report["projects"][project] = {"systems": results, "b4_random": b4, "bootstrap": intervals}

    if args.count:
        print(f"\nTOTAL at most {grand_total} first-attempt model calls on the test split")
        return 0
    out = ROOT / "reports" / f"final_{args.split}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
