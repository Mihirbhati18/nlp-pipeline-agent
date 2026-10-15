"""Show real example requests for each intent and each field (B2 helper).

A developer configuring a pipeline by hand looks at the training examples to
understand what each label means. This prints them from the project's k-shot
pool, which is training data only; development and test labels are not shown.

Usage:
    python scripts/b2_examples.py --project P1            # everything
    python scripts/b2_examples.py --project P1 intents    # request types only
    python scripts/b2_examples.py --project P1 fields     # fields only
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Example requests per intent and field")
    parser.add_argument("--project", choices=["P1", "P2"], default="P1")
    parser.add_argument("what", nargs="?", choices=["intents", "fields", "all"], default="all")
    args = parser.parse_args()

    path = ROOT / "data" / "processed" / args.project / "kshot.jsonl"
    with open(path, encoding="utf-8") as handle:
        pool = [json.loads(line) for line in handle if line.strip()]

    if args.what in ("intents", "all"):
        by_intent = defaultdict(list)
        for case in pool:
            by_intent[case["true_intent"]].append(case["utt"])
        print("=== REQUEST TYPES (intents) ===")
        for intent in sorted(by_intent):
            print(f"\n{intent}")
            for utt in by_intent[intent][:5]:
                print(f"    {utt}")

    if args.what in ("fields", "all"):
        manifest = json.loads((ROOT / "data" / "manifests" / f"{args.project}.json").read_text(encoding="utf-8"))
        schema = manifest["entity_schema"]
        names = sorted(schema) if isinstance(schema, dict) else sorted(schema)
        by_field = defaultdict(list)
        for case in pool:
            for entity in case["entities"]:
                by_field[entity["type"]].append((entity["text"], case["utt"]))
        print("\n=== FIELDS (information to extract) ===")
        for name in names:
            print(f"\n{name}")
            if not by_field[name]:
                print("    (no examples - work it out from the field name and the project description)")
            for text, utt in by_field[name][:5]:
                print(f"    '{text}'   in: {utt}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
