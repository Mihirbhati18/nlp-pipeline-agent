"""G2 data preparation (PROJECT_PLAN.md section 4).

Builds, for each project defined in ``configs/projects.json``:

- a k-shot example pool (k = 10 per intent) from the official train split
- a development set (100 cases: 80 in-scope + 20 out-of-scope)
- a test set (300 cases: 250 in-scope + 50 out-of-scope; P3 uses the plan's
  200-case fallback because its official test split is smaller)
- the project's entity schema, derived from the **train** split only
- a manifest recording source, licence, counts, label inventory, split IDs and
  file hashes

Then runs the leakage checks and writes a report. Official split assignments
are preserved: a case sampled for development came from the official dev
split, and a test case from the official test split. Sampling is seeded, so
this script is reproducible.

Out-of-scope cases are drawn only from the reserved pool domains and are
disjoint across projects.

Usage:
    python scripts/prepare_data.py            # writes data/processed and manifests
    python scripts/prepare_data.py --check    # re-verify existing output only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.massive import parse_annotation  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "projects.json"
PROCESSED = ROOT / "data" / "processed"
MANIFESTS = ROOT / "data" / "manifests"

OOS_LABEL = "none_of_the_above"


def load_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def normalise(text: str) -> str:
    """Normalisation used only for near-duplicate detection, never for scoring."""
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def make_case(row: dict, *, in_scope: bool) -> dict:
    """One evaluation case with verified gold spans."""
    entities = [e.as_dict() for e in parse_annotation(row["utt"], row["annot_utt"])]
    return {
        "case_id": f"massive-{row['id']}",
        "utt": row["utt"],
        "intent": row["intent"] if in_scope else OOS_LABEL,
        "true_intent": row["intent"],
        "scenario": row["scenario"],
        "in_scope": in_scope,
        # Gold entities are kept for out-of-scope cases too, but an out-of-scope
        # request has no supported entity to extract: the correct behaviour is
        # to reject it, so the evaluator ignores entities when in_scope is false.
        "entities": entities if in_scope else [],
        "partition": row["partition"],
    }


def stratified_sample(
    rows: list[dict], total: int, key: str, rng: random.Random
) -> list[dict]:
    """Sample ``total`` rows, spreading them as evenly as possible over ``key``.

    Groups are filled one case at a time in a fixed rotation, so a label with
    few available cases contributes all of them rather than being dropped, and
    a label with many does not swamp the sample.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    for name in groups:
        groups[name] = sorted(groups[name], key=lambda r: int(r["id"]))
        rng.shuffle(groups[name])

    chosen: list[dict] = []
    names = sorted(groups)
    while len(chosen) < total:
        progressed = False
        for name in names:
            if groups[name] and len(chosen) < total:
                chosen.append(groups[name].pop())
                progressed = True
        if not progressed:
            break  # every group exhausted
    return sorted(chosen, key=lambda r: int(r["id"]))


def write_jsonl(path: Path, cases: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def leakage_checks(project: str, pool, dev, test) -> dict:
    """Exact and near-duplicate overlap across a project's three splits.

    Rules reported:
    - ID overlap: a case ID must appear in at most one split. Any overlap is a
      hard failure.
    - Exact text overlap: identical ``utt`` strings across splits. Reported;
      MASSIVE's own splits may legitimately contain repeated short phrasings.
    - Near-duplicate overlap: identical after lowercasing and removing
      punctuation. Reported as a count with examples.
    """
    sets = {"kshot": pool, "dev": dev, "test": test}
    ids = {name: {c["case_id"] for c in cases} for name, cases in sets.items()}
    texts = {name: Counter(c["utt"] for c in cases) for name, cases in sets.items()}
    norms = {name: Counter(normalise(c["utt"]) for c in cases) for name, cases in sets.items()}

    report: dict[str, object] = {"project": project, "id_overlaps": {}, "exact_text_overlaps": {}, "near_duplicate_overlaps": {}}
    pairs = [("kshot", "dev"), ("kshot", "test"), ("dev", "test")]
    for a, b in pairs:
        key = f"{a}|{b}"
        report["id_overlaps"][key] = sorted(ids[a] & ids[b])
        shared_exact = sorted(set(texts[a]) & set(texts[b]))
        report["exact_text_overlaps"][key] = {
            "count": len(shared_exact),
            "examples": shared_exact[:5],
        }
        shared_near = sorted(set(norms[a]) & set(norms[b]))
        # The exact case-ID pairs, so a sensitivity check can exclude them.
        index_a = {normalise(c["utt"]): c["case_id"] for c in sets[a]}
        index_b = {normalise(c["utt"]): c["case_id"] for c in sets[b]}
        report["near_duplicate_overlaps"][key] = {
            "count": len(shared_near),
            "examples": shared_near[:5],
            "case_id_pairs": [
                {"text": text, a: index_a[text], b: index_b[text]} for text in shared_near
            ],
        }
    report["id_overlap_total"] = sum(len(v) for v in report["id_overlaps"].values())
    report["passes_id_check"] = report["id_overlap_total"] == 0
    return report


def build_project(spec: dict, rows: list[dict], config: dict, taken_oos: set[str]) -> dict:
    sampling = config["sampling"]
    pid = spec["id"]
    domains = set(spec["domains"])
    k = sampling["k_per_intent"]
    dev_total = spec.get("dev_total", sampling["dev_total"])
    dev_oos = spec.get("dev_oos", sampling["dev_oos"])
    test_total = spec.get("test_total", sampling["test_total"])
    test_oos = spec.get("test_oos", sampling["test_oos"])

    # A separate stream per project, so adding a project cannot change another's sample.
    rng = random.Random(f"{sampling['seed']}|{pid}")

    in_scope = [r for r in rows if r["scenario"] in domains]
    pool_rows = [r for r in in_scope if r["partition"] == "train"]
    dev_rows = [r for r in in_scope if r["partition"] == "dev"]
    test_rows = [r for r in in_scope if r["partition"] == "test"]
    intents = sorted({r["intent"] for r in in_scope})

    # k-shot pool: exactly k per intent where available.
    by_intent: dict[str, list[dict]] = defaultdict(list)
    for row in pool_rows:
        by_intent[row["intent"]].append(row)
    pool: list[dict] = []
    short_intents: dict[str, int] = {}
    for intent in intents:
        available = sorted(by_intent[intent], key=lambda r: int(r["id"]))
        rng.shuffle(available)
        if len(available) < k:
            short_intents[intent] = len(available)
        pool.extend(available[:k])
    pool_cases = [make_case(r, in_scope=True) for r in sorted(pool, key=lambda r: int(r["id"]))]

    # In-scope evaluation cases, stratified over intents.
    dev_in = stratified_sample(dev_rows, dev_total - dev_oos, "intent", rng)
    test_in = stratified_sample(test_rows, test_total - test_oos, "intent", rng)

    # Out-of-scope cases from the reserved pool, disjoint across projects.
    oos_domains = set(config["oos_pool"]["domains"])
    oos_available = {
        part: [
            r for r in rows
            if r["scenario"] in oos_domains
            and r["partition"] == part
            and f"massive-{r['id']}" not in taken_oos
        ]
        for part in ("dev", "test")
    }
    dev_oos_rows = stratified_sample(oos_available["dev"], dev_oos, "scenario", rng)
    test_oos_rows = stratified_sample(oos_available["test"], test_oos, "scenario", rng)
    for row in dev_oos_rows + test_oos_rows:
        taken_oos.add(f"massive-{row['id']}")

    dev_cases = [make_case(r, in_scope=True) for r in dev_in] + [
        make_case(r, in_scope=False) for r in dev_oos_rows
    ]
    test_cases = [make_case(r, in_scope=True) for r in test_in] + [
        make_case(r, in_scope=False) for r in test_oos_rows
    ]

    # Entity schema from the TRAIN split only: a developer declares the schema
    # without having seen the evaluation cases.
    schema_types: set[str] = set()
    for row in pool_rows:
        for entity in parse_annotation(row["utt"], row["annot_utt"]):
            schema_types.add(entity.type)
    schema = sorted(schema_types)

    # How often evaluation cases carry a slot type the declared schema lacks.
    out_of_schema: Counter = Counter()
    total_entities = 0
    for case in dev_cases + test_cases:
        for entity in case["entities"]:
            total_entities += 1
            if entity["type"] not in schema_types:
                out_of_schema[entity["type"]] += 1

    paths = {
        "kshot": PROCESSED / pid / "kshot.jsonl",
        "dev": PROCESSED / pid / "dev.jsonl",
        "test": PROCESSED / pid / "holdout" / "test.jsonl",
    }
    hashes = {
        "kshot": write_jsonl(paths["kshot"], pool_cases),
        "dev": write_jsonl(paths["dev"], dev_cases),
        "test": write_jsonl(paths["test"], test_cases),
    }

    leakage = leakage_checks(pid, pool_cases, dev_cases, test_cases)

    manifest = {
        "project": pid,
        "name": spec["name"],
        "role": spec["role"],
        "domains": sorted(domains),
        "rationale": spec["rationale"],
        "override_reason": spec.get("override_reason"),
        "dataset": config["dataset"],
        "sampling": {
            "seed": sampling["seed"],
            "rng_stream": f"{sampling['seed']}|{pid}",
            "k_per_intent": k,
            "dev_total": dev_total,
            "dev_oos": dev_oos,
            "test_total": test_total,
            "test_oos": test_oos,
        },
        "intents": intents,
        "n_intents": len(intents),
        "intents_with_fewer_than_k_train_examples": short_intents,
        "entity_schema": schema,
        "n_entity_types": len(schema),
        "entity_types_in_eval_but_not_in_schema": dict(out_of_schema),
        "n_entities_in_eval": total_entities,
        "counts": {
            "kshot": len(pool_cases),
            "dev_in_scope": len(dev_in),
            "dev_oos": len(dev_oos_rows),
            "dev_total": len(dev_cases),
            "test_in_scope": len(test_in),
            "test_oos": len(test_oos_rows),
            "test_total": len(test_cases),
        },
        "available_in_official_split": {
            "train_in_scope": len(pool_rows),
            "dev_in_scope": len(dev_rows),
            "test_in_scope": len(test_rows),
        },
        "per_intent_support": {
            "dev": dict(Counter(c["true_intent"] for c in dev_cases if c["in_scope"])),
            "test": dict(Counter(c["true_intent"] for c in test_cases if c["in_scope"])),
        },
        "oos_scenarios_used": {
            "dev": sorted({c["scenario"] for c in dev_cases if not c["in_scope"]}),
            "test": sorted({c["scenario"] for c in test_cases if not c["in_scope"]}),
        },
        "files": {name: str(path.relative_to(ROOT)).replace("\\", "/") for name, path in paths.items()},
        "sha256": hashes,
        "case_ids": {
            "kshot": [c["case_id"] for c in pool_cases],
            "dev": [c["case_id"] for c in dev_cases],
            "test": [c["case_id"] for c in test_cases],
        },
        "leakage": leakage,
        "access_rule": (
            "kshot: model fitting and few-shot example selection. dev: prompts, "
            "candidates, thresholds. holdout/test.jsonl: opened only after the G10 "
            "freeze, by the final evaluator."
        ),
    }
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    (MANIFESTS / f"{pid}.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="G2 data preparation")
    parser.add_argument("--check", action="store_true", help="verify existing manifests only")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    source = ROOT / config["dataset"]["local_file"]
    if not source.exists():
        print(f"missing {source}; download MASSIVE 1.1 first", file=sys.stderr)
        return 2

    rows = load_rows(source)
    print(f"MASSIVE {config['dataset']['version']} {config['dataset']['locale']}: "
          f"{len(rows)} records, licence {config['dataset']['licence']}")

    if args.check:
        for spec in config["projects"]:
            path = MANIFESTS / f"{spec['id']}.json"
            if not path.exists():
                print(f"{spec['id']}: no manifest", file=sys.stderr)
                return 2
            manifest = json.loads(path.read_text(encoding="utf-8"))
            print(f"{spec['id']}: {manifest['counts']} | leakage id-check "
                  f"{'pass' if manifest['leakage']['passes_id_check'] else 'FAIL'}")
        return 0

    taken_oos: set[str] = set()
    manifests = [build_project(spec, rows, config, taken_oos) for spec in config["projects"]]

    failures = 0
    print()
    for manifest in manifests:
        pid = manifest["project"]
        counts = manifest["counts"]
        leak = manifest["leakage"]
        print(f"--- {pid} {manifest['name']} ({manifest['role']}) ---")
        print(f"  domains: {', '.join(manifest['domains'])} | {manifest['n_intents']} intents "
              f"| {manifest['n_entity_types']} entity types")
        print(f"  kshot {counts['kshot']} | dev {counts['dev_total']} "
              f"({counts['dev_in_scope']} in-scope + {counts['dev_oos']} OOS) "
              f"| test {counts['test_total']} "
              f"({counts['test_in_scope']} in-scope + {counts['test_oos']} OOS)")
        if manifest["intents_with_fewer_than_k_train_examples"]:
            print(f"  WARNING intents short of k: {manifest['intents_with_fewer_than_k_train_examples']}")
        if manifest["entity_types_in_eval_but_not_in_schema"]:
            print(f"  note: entity types in evaluation but not in the train-derived schema: "
                  f"{manifest['entity_types_in_eval_but_not_in_schema']}")
        if not leak["passes_id_check"]:
            failures += 1
            print(f"  LEAKAGE FAILURE: shared case IDs {leak['id_overlaps']}")
        else:
            print("  leakage: no shared case IDs across kshot/dev/test")
        for pair, info in leak["near_duplicate_overlaps"].items():
            if info["count"]:
                print(f"  near-duplicate text across {pair}: {info['count']} "
                      f"(e.g. {info['examples'][:2]})")
        support = manifest["per_intent_support"]["test"]
        if support:
            thin = {k: v for k, v in sorted(support.items(), key=lambda kv: kv[1]) if v < 10}
            if thin:
                print(f"  thin test support (<10 cases, noisy per-intent F1): {thin}")
        print()

    overlap = Counter()
    for manifest in manifests:
        for cid in manifest["case_ids"]["dev"] + manifest["case_ids"]["test"]:
            overlap[cid] += 1
    shared = [cid for cid, n in overlap.items() if n > 1]
    if shared:
        failures += 1
        print(f"FAILURE: {len(shared)} evaluation cases are shared between projects: {shared[:5]}")
    else:
        print("no evaluation case is shared between projects")

    print(f"\nmanifests written to {MANIFESTS.relative_to(ROOT)}/")
    if failures:
        print(f"{failures} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
