"""B2: the manually configured project-specific pipeline (PROJECT_PLAN.md section 3).

    B2 | Manually configured project-specific pipeline | Same local model and
    same catalogue; human picks a configuration and hand-writes intent/entity
    descriptions; 2-hour budget per project, recorded.

B2 answers RQ2: how does the framework compare with a person doing the same job
by hand, on quality, configuration effort, design cost and latency? It is the
only system whose cost is *human* time, so it is the only one you must do
yourself.

The work happens in a worksheet file rather than an interactive prompt, so you
can take your time, stop and come back, and leave a record of what you decided
and why.

Three commands:

    python scripts/run_b2.py start  --project P1
        Creates configs/b2/P1_worksheet.md with the project description, the
        twelve configurations explained, and blanks to fill in. Starts the clock.

    python scripts/run_b2.py check  --project P1
        Reads your worksheet and scores your current choice on development
        data, then appends the result. Use it as often as you like inside your
        2-hour budget; every check is counted and reported, because a human who
        tried eight configurations did more work than one who tried one.

    python scripts/run_b2.py finish --project P1
        Records your active minutes and any AI assistance, runs your final
        configuration, scores it with the shared scorer and writes a run folder.

Honesty requirements this script enforces:

- Active human minutes are **your** figure, entered by you, separate from wall
  time and from model waiting time. The plan requires those be distinguished.
- AI assistance must be declared. The plan flags that the same person builds A1
  and B2, which biases the effort comparison; hidden assistance would make it
  worse.
- The number of development checks is recorded, because it is part of the
  effort and part of the design cost.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.access import access_for  # noqa: E402
from src.analyzer.analyzer import validate  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.evaluation.runs import new_run  # noqa: E402
from src.evaluation.scorer import score  # noqa: E402
from src.evaluation.thresholds import tune_binary_threshold  # noqa: E402
from src.llm.client import make_client  # noqa: E402
from src.pipelines.catalogue import CATALOGUE, ConfigRunner, get_config  # noqa: E402
from src.pipelines.examples import ExampleSelector  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
B2_DIR = ROOT / "configs" / "b2"
BUDGET_MINUTES = 120

FACTORS = """The twelve configurations combine three choices. Pick one id.

Extraction strategy
  joint          one call returns the intent and the information together
  twostage       one call for the intent, then one for that intent's fields
  schema         one call, with your written descriptions included in the prompt

Example selection
  fixed          the same one example per intent every time
  sim            the examples most similar to each request

Out-of-scope policy
  llm            the model may answer none_of_the_above
  tfidf          a similarity threshold rejects a request before any model call

Configuration ids are <extraction>-<examples>-<oos>, for example joint-sim-llm.

Available ids:
"""

TEMPLATE = """# B2 worksheet - {project} {name}

You are configuring this pipeline **by hand**. This is the comparison against
the automated framework, so work as a developer would: read the project, decide
what suits it, write the descriptions, try things on development data.

Budget: **{budget} minutes of active work** for this project. Keep your own
count of time actually spent working, excluding breaks and excluding time spent
waiting for the model.

Do not open the test split. It is locked by the code anyway.

---

## 1. The project you are configuring

{description}

---

## 2. Pick a configuration

{factors}

**Your choice** (replace the placeholder with one id):

```
CONFIG: {default_config}
```

---

## 3. Write a description for each request type

These go into the prompt for schema-guided configurations, and the framework's
Analyzer writes its own version of exactly this. One short line each. Leave a
line blank if you want no description for it.

```
{intent_block}
```

---

## 4. Write a description for each kind of information

Say what the field holds, in the project's own terms.

```
{entity_block}
```

---

## 5. Your effort, in your own words

Fill these in before running `finish`. Be accurate rather than flattering;
an honest number is the whole point of this baseline.
Write each answer on its own line inside the box below, after the colon;
the notes under the box only explain the fields.

```
ACTIVE_MINUTES: 0
AI_ASSISTANCE: none
NOTES:
```

- `ACTIVE_MINUTES`: minutes you actually spent working on this, excluding
  breaks and excluding model waiting time.
- `AI_ASSISTANCE`: `none`, or describe exactly what help you used and for what.
  The plan requires this because the same person builds the automated system
  and this manual baseline, which biases the effort comparison.
- `NOTES`: anything about why you chose what you chose. This becomes part of
  the record for the paper.

---

## 6. Development checks

Each time you run `python scripts/run_b2.py check --project {project}`, the
result is appended below. Every check counts toward your effort and toward
B2's design cost.

<!-- checks appended below this line -->
"""


def worksheet_path(project: str) -> Path:
    return B2_DIR / f"{project}_worksheet.md"


def read_field(text: str, name: str) -> str | None:
    match = re.search(rf"^{name}:\s*(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def read_descriptions(text: str, section: str, names: list[str]) -> dict[str, str]:
    """Read `name: description` lines from one fenced block."""
    block = re.search(rf"## {section}.*?```\n(.*?)```", text, re.DOTALL)
    if not block:
        return {}
    out: dict[str, str] = {}
    for line in block.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), " ".join(value.split())
        if key in names and value and not value.startswith("<"):
            out[key] = value
    return out


def load_worksheet(project: str):
    path = worksheet_path(project)
    if not path.exists():
        print(f"no worksheet yet. Run: python scripts/run_b2.py start --project {project}",
              file=sys.stderr)
        return None
    return path, path.read_text(encoding="utf-8")


def parse_choice(project: str, spec, text: str):
    config_id = read_field(text, "CONFIG")
    if not config_id or config_id.startswith("<"):
        print("CONFIG is not filled in yet", file=sys.stderr)
        return None
    try:
        config = get_config(config_id)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return None

    intents = read_descriptions(text, "3. Write a description", spec.intent_names)
    entities = read_descriptions(text, "4. Write a description", spec.entity_type_names)
    return config, intents, entities


def build_spec(spec, intents: dict, entities: dict):
    """Apply the hand-written descriptions, exactly as the Analyzer would."""
    return spec.with_descriptions(intents, entities)


def evaluate(spec, config, intents, entities, pool, dev, client):
    enriched = build_spec(spec, intents, entities)
    selector = ExampleSelector(list(pool))
    threshold = tune_binary_threshold(
        [selector.max_similarity(c["utt"]) for c in dev],
        [c["in_scope"] for c in dev],
    )
    runner = ConfigRunner(
        config=config, spec=enriched, client=client, selector=selector,
        oos_threshold=threshold.threshold,
    )
    predictions, logical, physical = [], 0, 0
    for case in dev:
        outcome = runner.run_case(case)
        predictions.append(outcome.prediction)
        logical += outcome.logical_calls
        physical += outcome.physical_calls
    metrics = score(dev, predictions, labels=spec.intent_names)
    return enriched, threshold, predictions, metrics, logical, physical


def cmd_start(project: str) -> int:
    spec = load_spec(project)
    pool = load_cases(access_for(spec).train_path)
    findings = validate(spec, pool)
    if [f for f in findings if f.blocking]:
        print("the project specification is contradictory; fix that first", file=sys.stderr)
        return 1

    B2_DIR.mkdir(parents=True, exist_ok=True)
    path = worksheet_path(project)
    if path.exists():
        print(f"{path.relative_to(ROOT)} already exists; not overwriting your work")
        return 0

    ids = "\n".join(f"  {c.config_id}" for c in CATALOGUE)
    path.write_text(
        TEMPLATE.format(
            project=project,
            name=spec.name,
            budget=BUDGET_MINUTES,
            description=spec.description_text.strip(),
            factors=FACTORS + ids,
            default_config="<put one configuration id here>",
            intent_block="\n".join(f"{n}: " for n in spec.intent_names),
            entity_block="\n".join(f"{n}: " for n in spec.entity_type_names),
        ),
        encoding="utf-8",
    )
    (B2_DIR / f"{project}_started.json").write_text(
        json.dumps({"started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "started_epoch": time.time(), "project": project}, indent=1),
        encoding="utf-8",
    )
    print(f"created {path.relative_to(ROOT)}")
    print(f"\nOpen it, fill in sections 2 to 5, then run:")
    print(f"  python scripts/run_b2.py check  --project {project}   (as often as you like)")
    print(f"  python scripts/run_b2.py finish --project {project}   (when you are done)")
    print(f"\nYour budget is {BUDGET_MINUTES} minutes of active work.")
    return 0


def cmd_check(project: str, model: str) -> int:
    loaded = load_worksheet(project)
    if not loaded:
        return 1
    path, text = loaded
    spec = load_spec(project)
    parsed = parse_choice(project, spec, text)
    if not parsed:
        return 1
    config, intents, entities = parsed

    access = access_for(spec)
    pool = load_cases(access.train_path)
    dev = load_cases(access.dev_path)
    client = make_client(model)

    print(f"checking {config.config_id} on {project} development data "
          f"({len(intents)}/{len(spec.intents)} intents described, "
          f"{len(entities)}/{len(spec.entity_types)} fields described)")
    _, _, _, metrics, logical, physical = evaluate(
        spec, config, intents, entities, pool, dev, client
    )
    p = metrics["primary"]

    def show(v, d=3):
        return "n/a" if v is None else f"{v:.{d}f}"

    checks = text.count("### Check ")
    row = (
        f"\n### Check {checks + 1} - {time.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"- configuration: `{config.config_id}`\n"
        f"- descriptions written: {len(intents)} intents, {len(entities)} fields\n"
        f"- intent macro-F1 **{show(p['intent_macro_f1'])}**, "
        f"entity F1 {show(p['entity_span_f1'])}, "
        f"out-of-scope F1 {show(p['oos_f1'])}, "
        f"schema validity {show(p['schema_validity_after_repair'])}\n"
        f"- logical calls {logical}, physical {physical}\n"
    )
    path.write_text(text + row, encoding="utf-8")

    print(f"  intent macro-F1 {show(p['intent_macro_f1'])} | "
          f"entity F1 {show(p['entity_span_f1'])} | "
          f"oos F1 {show(p['oos_f1'])} | schema {show(p['schema_validity_after_repair'])}")
    print(f"  appended as check {checks + 1} to {path.relative_to(ROOT)}")
    return 0


def cmd_finish(project: str, model: str) -> int:
    loaded = load_worksheet(project)
    if not loaded:
        return 1
    path, text = loaded
    spec = load_spec(project)
    parsed = parse_choice(project, spec, text)
    if not parsed:
        return 1
    config, intents, entities = parsed

    active = read_field(text, "ACTIVE_MINUTES")
    assistance = read_field(text, "AI_ASSISTANCE")
    notes = read_field(text, "NOTES") or ""
    if not active or not active.isdigit() or int(active) <= 0:
        print("ACTIVE_MINUTES must be a positive whole number of minutes you "
              "actually worked. B2's whole purpose is that figure.", file=sys.stderr)
        return 1
    if not assistance:
        print("AI_ASSISTANCE must say `none` or describe the help you used.",
              file=sys.stderr)
        return 1

    active_minutes = int(active)
    checks = text.count("### Check ")
    started = B2_DIR / f"{project}_started.json"
    wall_minutes = None
    if started.exists():
        begun = json.loads(started.read_text(encoding="utf-8"))["started_epoch"]
        wall_minutes = round((time.time() - begun) / 60, 1)

    access = access_for(spec)
    pool = load_cases(access.train_path)
    dev = load_cases(access.dev_path)
    client = make_client(model)

    enriched, threshold, predictions, metrics, logical, physical = evaluate(
        spec, config, intents, entities, pool, dev, client
    )

    over_budget = active_minutes > BUDGET_MINUTES
    config_record = {
        "system": "B2",
        "split": "dev",
        "model": client.model,
        "model_digest": client.model_digest,
        "settings": client.settings,
        "cache_enabled": client.cache_enabled,
        "config": config.as_dict(),
        "chosen_by": "human, by hand",
        "oos_threshold": threshold.as_dict(),
        "descriptions_written": {
            "intents": len(intents), "intents_total": len(spec.intents),
            "entity_types": len(entities), "entity_types_total": len(spec.entity_types),
        },
        "intent_descriptions": intents,
        "entity_descriptions": entities,
        "effort": {
            "active_human_minutes": active_minutes,
            "budget_minutes": BUDGET_MINUTES,
            "over_budget": over_budget,
            "wall_clock_minutes_since_start": wall_minutes,
            "development_checks": checks,
            "note": (
                "active human minutes are self-reported and exclude breaks and "
                "model waiting time. Wall clock is elapsed time since `start`, "
                "which includes both."
            ),
        },
        "ai_assistance": assistance,
        "notes": notes,
        "bias_note": (
            "the same person built the automated system and this manual baseline, "
            "and already knows the data. This is a single, non-blind measurement "
            "of setup effort and must be reported as such."
        ),
        "worksheet": str(path.relative_to(ROOT)).replace("\\", "/"),
        "data_access": access.as_dict(),
        "data_sources": spec.source,
    }

    with new_run(
        project, "B2", 0, config_record,
        data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]},
    ) as log:
        for case, prediction in zip(dev, predictions):
            log.log_prediction(
                case_id=case["case_id"], gold_intent=case["true_intent"],
                gold_in_scope=case["in_scope"], status=prediction.status,
                predicted_intent=prediction.intent,
                predicted_entities=prediction.entities,
                schema_valid_raw=prediction.schema_valid_raw,
                schema_valid_final=prediction.schema_valid_final,
                retries=prediction.retries, error=prediction.error,
            )
        log.log_event("human_configuration", **config_record["effort"],
                      config_id=config.config_id, ai_assistance=assistance)
        metrics["primary"]["design_cost"] = {
            "logical_calls": logical,
            "physical_calls": physical,
            "active_human_minutes": active_minutes,
            "development_checks": checks,
        }
        log.write_metrics(metrics)

        p = metrics["primary"]

        def show(v, d=3):
            return "n/a" if v is None else f"{v:.{d}f}"

        log.write_summary("\n".join([
            f"# B2 on {project} (development)",
            "",
            f"Configuration `{config.config_id}`, chosen by hand. "
            f"{len(intents)} of {len(spec.intents)} intents and {len(entities)} of "
            f"{len(spec.entity_types)} fields described by hand.",
            "",
            f"**Active human time: {active_minutes} minutes** of a "
            f"{BUDGET_MINUTES}-minute budget"
            + (" (**over budget**)" if over_budget else "")
            + f", across {checks} development check(s).",
            f"AI assistance: {assistance}",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| Intent macro-F1 | {show(p['intent_macro_f1'])} |",
            f"| Entity span F1 | {show(p['entity_span_f1'])} |",
            f"| Out-of-scope F1 | {show(p['oos_f1'])} |",
            f"| Schema validity | {show(p['schema_validity_after_repair'])} |",
            "",
            config_record["bias_note"],
            "",
            f"Notes: {notes}" if notes else "",
            "",
        ]))
        log.finish(status="complete", n_cases=len(dev))

        print(f"B2 recorded as {log.run_id}")
        print(f"  configuration {config.config_id} | intent macro-F1 "
              f"{show(p['intent_macro_f1'])} | entity F1 {show(p['entity_span_f1'])}")
        print(f"  active human time {active_minutes} min of {BUDGET_MINUTES}"
              + (" (OVER BUDGET)" if over_budget else "")
              + f" | {checks} development check(s)")
        if wall_minutes:
            print(f"  wall clock since start: {wall_minutes} min "
                  f"(includes breaks and model waiting)")
        print(f"  AI assistance: {assistance}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="B2 manual configuration")
    parser.add_argument("command", choices=["start", "check", "finish"])
    parser.add_argument("--project", required=True)
    parser.add_argument("--model", default="qwen2.5:3b")
    args = parser.parse_args()

    if args.command == "start":
        return cmd_start(args.project)
    if args.command == "check":
        return cmd_check(args.project, args.model)
    return cmd_finish(args.project, args.model)


if __name__ == "__main__":
    raise SystemExit(main())
