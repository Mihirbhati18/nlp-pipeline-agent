"""Robustness to messy input: typos, capitals and filler words (development data).

Real users type carelessly. This rewrites every development request three
ways, each deterministic (fixed seed), and re-scores the systems on the
rewritten requests:

- ``typo``: two adjacent letters swapped in one word of 4+ letters that lies
  outside every gold entity, so the gold entity spans stay valid
- ``caps``: the whole request in capital letters (positions unchanged)
- ``filler``: "hey, could you please " before the request and ", thanks"
  after it (gold spans shifted by the prefix length)

Systems: A1's selected pipeline (enriched spec), B1, and B0. B0 keeps its
threshold tuned on the clean development split, as it would be deployed.
Each (system, variant) is written as its own run folder. Test data is never
touched. These are new prompts, so they are real model calls (cached after
the first run).

Usage:
    python scripts/run_robustness.py
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.access import access_for  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.architect.design_run import run_design  # noqa: E402
from src.baselines.b0_tfidf import B0TfidfClassifier  # noqa: E402
from src.evaluation.runs import new_run  # noqa: E402
from src.evaluation.scorer import score  # noqa: E402
from src.llm.client import make_client, ollama_version  # noqa: E402
from src.pipelines.catalogue import B1_CONFIG_ID, ConfigRunner, get_config  # noqa: E402
from src.pipelines.examples import ExampleSelector  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261016
PREFIX = "hey, could you please "
SUFFIX = ", thanks"


def typo(case: dict, rng: random.Random) -> dict:
    utt = case["utt"]
    spans = [(e["start"], e["end"]) for e in case.get("entities", [])]
    words = [
        m for m in re.finditer(r"[A-Za-z]{4,}", utt)
        if not any(m.start() < end and start < m.end() for start, end in spans)
    ]
    if not words:
        return dict(case)  # nothing safe to change; the request stays as it is
    word = rng.choice(words)
    # Only swap two different letters; swapping "ll" in "call" changes nothing.
    positions = [i for i in range(word.start(), word.end() - 1) if utt[i] != utt[i + 1]]
    if not positions:
        return dict(case)
    i = rng.choice(positions)
    changed = utt[:i] + utt[i + 1] + utt[i] + utt[i + 2:]
    return {**case, "utt": changed}


def caps(case: dict, rng: random.Random) -> dict:  # noqa: ARG001
    return {**case, "utt": case["utt"].upper(),
            "entities": [{**e, "text": e["text"].upper()} for e in case.get("entities", [])]}


def filler(case: dict, rng: random.Random) -> dict:  # noqa: ARG001
    shift = len(PREFIX)
    return {**case, "utt": PREFIX + case["utt"] + SUFFIX,
            "entities": [{**e, "start": e["start"] + shift, "end": e["end"] + shift}
                         for e in case.get("entities", [])]}


VARIANTS = {"typo": typo, "caps": caps, "filler": filler}


def perturb(dev: list[dict], name: str) -> list[dict]:
    rng = random.Random(f"{SEED}-{name}")
    out = [VARIANTS[name](case, rng) for case in dev]
    for case in out:  # the gold spans must still point at the gold text
        for e in case.get("entities", []):
            assert case["utt"][e["start"]:e["end"]] == e["text"], (name, case["utt"], e)
    return out


def run_llm(config_id, spec, client, pool, cases, threshold):
    runner = ConfigRunner(config=get_config(config_id), spec=spec, client=client,
                          selector=ExampleSelector(list(pool)), oos_threshold=threshold)
    return [runner.run_case(c).prediction for c in cases]


def record(project, system, variant, cases, predictions, metrics, extra, spec):
    with new_run(project, f"{system}-robust-{variant}", 0, {
        "split": "dev", "variant": variant, "seed": SEED,
        "purpose": "robustness to rewritten development requests",
        "rewritten_requests": [c["utt"] for c in cases[:5]], **extra,
    }, data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]}) as log:
        for case, p in zip(cases, predictions):
            log.log_prediction(case_id=case["case_id"], utt=case["utt"],
                               gold_intent=case["true_intent"], gold_in_scope=case["in_scope"],
                               status=p.status, predicted_intent=p.intent,
                               predicted_entities=p.entities, schema_valid_raw=p.schema_valid_raw,
                               schema_valid_final=p.schema_valid_final, retries=p.retries,
                               error=p.error)
        log.write_metrics(metrics)
        log.finish(status="complete", n_cases=len(cases))
        return log.run_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Robustness to messy requests")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--projects", nargs="+", default=["P1", "P2"])
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    try:
        ollama_version(args.host)
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach Ollama at {args.host}: {exc}", file=sys.stderr)
        return 2

    client = make_client(args.model, host=args.host, cache_dir=ROOT / "cache")
    report = {"generated": time.strftime("%Y-%m-%d %H:%M"), "seed": SEED, "projects": {}}

    for project in args.projects:
        spec = load_spec(project)
        access = access_for(spec)
        pool = load_cases(access.train_path)
        dev = load_cases(access.dev_path)
        labels = spec.intent_names
        design = run_design(spec, access, runtime_client=client, planning_client=client,
                            load_cases=load_cases, single_call_p95_s=0.59)
        enriched, threshold, selected = design.analysis.spec, design.oos_threshold.threshold, design.selected_config_id
        b0 = B0TfidfClassifier(labels=labels).fit(pool)
        b0.tune(dev)

        systems = {
            "A1": lambda cases: run_llm(selected, enriched, client, pool, cases, threshold),
            "B1": lambda cases: run_llm(B1_CONFIG_ID, spec, client, pool, cases, threshold),
            "B0": lambda cases: b0.predict(cases),
        }
        configs = {"A1": selected, "B1": B1_CONFIG_ID, "B0": "tfidf-logreg"}
        result = {}
        print(f"\n=== {project} ===")
        for system, predict in systems.items():
            result[system] = {}
            for variant in ("clean", *VARIANTS):
                cases = dev if variant == "clean" else perturb(dev, variant)
                predictions = predict(cases)
                metrics = score(cases, predictions, labels=labels)
                p = metrics["primary"]
                entry = {key: p[key] for key in ("intent_macro_f1", "entity_span_f1", "oos_f1",
                                                 "schema_validity_after_repair")}
                if variant != "clean":
                    entry["run_id"] = record(project, system, variant, cases, predictions, metrics,
                                             {"config_id": configs[system]}, spec)
                result[system][variant] = entry
                print(f"  {system} {variant:7} intent {p['intent_macro_f1']:.3f} "
                      f"entity {p['entity_span_f1']:.3f} oos {p['oos_f1']:.3f}")
        report["projects"][project] = {"a1_config": selected, "systems": result,
                                       "examples": {v: [perturb(dev, v)[i]["utt"] for i in range(3)]
                                                    for v in VARIANTS}}

    out = ROOT / "reports" / "robustness.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
