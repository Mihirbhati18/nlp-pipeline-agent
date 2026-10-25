"""Show, step by step, how one evaluation test works (a teaching tool).

Runs one pipeline design on a few development requests and prints every step
an evaluation goes through, so the process can be explained and shown live:

  1. the request and its correct answer (from the dataset)
  2. the examples chosen for the prompt
  3. the prompt sent to the AI model
  4. the model's raw reply
  5. how the reply is read and checked (parsed, entities located in the text)
  6. whether it was right
  7. the scores for these requests, computed by our scorer and by scikit-learn

It writes no run folder and changes nothing. Answers come from the saved
prediction cache when available (the same answers the experiments used);
``--live`` asks the model fresh instead.

Usage:
    python scripts/walkthrough.py                        # B1 design, P1, 3 requests
    python scripts/walkthrough.py --n 5 --design schema-sim-llm
    python scripts/walkthrough.py --live
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sklearn.metrics import accuracy_score  # noqa: E402

from src.analyzer.access import access_for  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.evaluation.output_schema import parse_output  # noqa: E402
from src.evaluation.scorer import score  # noqa: E402
from src.evaluation.span_rule import locate_entities  # noqa: E402
from src.llm.client import make_client  # noqa: E402
from src.pipelines.catalogue import B1_CONFIG_ID, get_config, render_prompt  # noqa: E402
from src.pipelines.examples import ExampleSelector  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LINE = "-" * 78


def show(title: str, text: str = "", indent: int = 4) -> None:
    print(f"\n  {title}")
    for line in text.splitlines():
        print(" " * indent + line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk through one evaluation test")
    parser.add_argument("--project", choices=["P1", "P2"], default="P1")
    parser.add_argument("--design", default=B1_CONFIG_ID,
                        help="a single-call design, e.g. joint-fixed-llm or schema-sim-llm")
    parser.add_argument("--n", type=int, default=3, help="how many development requests to walk through")
    parser.add_argument("--live", action="store_true", help="ask the model fresh, ignoring saved answers")
    args = parser.parse_args()

    config = get_config(args.design)
    if config.extraction == "two_stage":
        print("Pick a single-call design (joint-... or schema-...) so every step fits on screen.")
        return 1

    spec = load_spec(args.project)
    access = access_for(spec)  # the lock: only training and development data are reachable
    pool = load_cases(access.train_path)
    dev = load_cases(access.dev_path)
    client = make_client("qwen2.5:3b", cache_dir=None if args.live else ROOT / "cache")
    selector = ExampleSelector(list(pool))

    print(LINE)
    print(f"Walkthrough: design {config.config_id} on {args.project} ({spec.name})")
    print(f"  extraction={config.extraction}, examples={config.example_selection}, "
          f"off-topic policy={config.oos_policy}")
    print(f"  model {client.model}, answers {'asked live' if args.live else 'from the saved cache'}")
    print(LINE)

    cases = [c for c in dev if c["in_scope"]][: max(1, args.n - 1)] + [c for c in dev if not c["in_scope"]][:1]
    predictions = []
    for number, case in enumerate(cases, 1):
        print(f"\nREQUEST {number}: \"{case['utt']}\"")
        gold_entities = ", ".join(f"{e['type']}='{e['text']}'" for e in case["entities"]) or "none"
        show("1. Correct answer (from the dataset):",
             f"intent = {case['true_intent'] if case['in_scope'] else 'OUT OF SCOPE (should be refused)'}\n"
             f"entities = {gold_entities}")

        examples = selector.fixed() if config.example_selection == "fixed" else selector.similarity(case["utt"])
        shown = "\n".join(f"\"{e['utt']}\" -> {e['true_intent']}" for e in examples[:3])
        show(f"2. Examples put in the prompt ({len(examples)} in total, first 3 shown):", shown)

        prompt, _ = render_prompt(config, spec, case["utt"], examples)
        lines = prompt.splitlines()
        preview = "\n".join(lines[:6] + ["   ... (" + str(len(lines) - 10) + " more lines: label list, examples) ..."] + lines[-4:])
        show(f"3. Prompt sent to the model ({len(lines)} lines, start and end shown):", preview)

        record = client.generate(prompt)
        show("4. Model's raw reply:", textwrap.fill(record.text.strip(), 90))

        parsed = parse_output(record.text, labels=spec.intent_names, entity_types=spec.entity_type_names)
        prediction = parsed.as_prediction(case["case_id"])
        located = locate_entities(case["utt"], prediction.entities)
        found = ", ".join(f"{e.type}='{e.text}' at characters {e.start}-{e.end}" if e.supported
                          else f"{e.type}='{e.text}' NOT IN THE REQUEST" for e in located) or "none"
        show("5. Reading the reply:",
             f"valid format = {parsed.schema_valid}\n"
             f"status = {prediction.status}   intent = {prediction.intent}\n"
             f"entities located in the request text = {found}")

        if case["in_scope"]:
            right = prediction.status == "ok" and prediction.intent == case["true_intent"]
            verdict = "intent RIGHT" if right else "intent WRONG"
        else:
            verdict = "correctly REFUSED" if prediction.status == "oos" else "WRONG: answered an off-topic request"
        show("6. Verdict:", verdict)
        predictions.append(prediction)

    metrics = score(cases, predictions, labels=spec.intent_names)["primary"]
    in_scope = [(c, p) for c, p in zip(cases, predictions) if c["in_scope"]]
    sk_acc = accuracy_score([c["true_intent"] for c, _ in in_scope],
                            [p.intent if p.status == "ok" else "none" for _, p in in_scope])
    print("\n" + LINE)
    print(f"7. Scores for these {len(cases)} requests")
    print(f"   our scorer:   intent accuracy {metrics['intent_accuracy_in_scope']:.3f}, "
          f"entity F1 {metrics['entity_span_f1']:.3f}, off-topic F1 {metrics['oos_f1']:.3f}")
    print(f"   scikit-learn: intent accuracy {sk_acc:.3f}")
    print("   A real evaluation does exactly this for all 100 development requests, saves every")
    print("   prediction in a run folder, and computes macro-F1 over all intents.")
    print(LINE)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
