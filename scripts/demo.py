"""Load an exported pipeline in a fresh process and answer requests (G9 demo).

Shows the three kinds of request the G9 gate requires: normal, out-of-scope
and invalid. Nothing here touches the Architect or the evaluation cache.

Usage:
    python scripts/demo.py --project P1                 # scripted demo requests
    python scripts/demo.py --project P1 --interactive   # type your own
    python scripts/demo.py --package artifacts/P1/<dir> "wake me at 7am"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.runtime.package import load_pipeline  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Written by hand for the demo, not drawn from any dataset split.
DEMO_REQUESTS = {
    "P1": [
        ("normal", "wake me up at six thirty tomorrow"),
        ("normal", "turn the bedroom lights off"),
        ("out of scope", "who won the football match last night"),
        ("invalid", ""),
        ("invalid", "x" * 600),
    ],
    "P2": [
        ("normal", "add a meeting with sara on friday at ten"),
        ("normal", "put milk on my shopping list"),
        ("out of scope", "how tall is mount everest"),
        ("invalid", "   "),
        ("invalid", None),
    ],
}


def newest_package(project: str) -> Path:
    candidates = sorted(
        (ROOT / "artifacts" / project).glob("*/manifest.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise SystemExit(f"no package under artifacts/{project}; run scripts/export_pipeline.py first")
    return candidates[-1].parent


def show(response: dict) -> None:
    status = response["status"]
    line = f"  -> {status}"
    if response["intent"]:
        line += f"  intent={response['intent']}"
    if response["entities"]:
        line += "  " + ", ".join(f"{e['type']}='{e['text']}'" for e in response["entities"])
    if response["unsupported_entities"]:
        line += f"  (unsupported: {response['unsupported_entities']})"
    if response["error"]:
        line += f"  error: {response['error'][:90]}"
    line += f"  [{response['model_calls']} model calls, {response['latency_s']:.2f}s]"
    print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an exported pipeline")
    parser.add_argument("--project", choices=["P1", "P2"], default="P1")
    parser.add_argument("--package", help="package directory (default: newest for --project)")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--json", action="store_true", help="print full JSON responses")
    parser.add_argument("requests", nargs="*")
    args = parser.parse_args()

    package = Path(args.package) if args.package else newest_package(args.project)
    pipeline = load_pipeline(package, host=args.host)
    info = pipeline.describe()
    print(f"Loaded {info['project_id']} ({info['project_name']}) pipeline "
          f"{info['config_id']}, package {info['package_hash'][:12]}")
    print(f"Model {info['model']} @ {info['model_digest'][:12]} | "
          f"{len(info['intents'])} intents, {len(info['entity_types'])} entity types\n")

    def answer(kind: str, request) -> None:
        shown = request if not isinstance(request, str) or len(request) < 70 else request[:40] + "..."
        print(f"[{kind}] {shown!r}")
        response = pipeline.handle(request)
        print(json.dumps(response, indent=2)) if args.json else show(response)

    if args.requests:
        for request in args.requests:
            answer("request", request)
    elif args.interactive:
        print("Type a request, or an empty line to stop.")
        while True:
            try:
                request = input("> ")
            except EOFError:
                break
            if not request:
                break
            answer("request", request)
    else:
        for kind, request in DEMO_REQUESTS[info["project_id"]]:
            answer(kind, request)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
