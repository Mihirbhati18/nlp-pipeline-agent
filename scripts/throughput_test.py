"""G0 day-1 throughput and determinism test (PROJECT_PLAN.md section 2A).

Measures, for each candidate model:

1. median and p95 seconds per request, input and output tokens
2. JSON-validity rate on 50 representative full-size few-shot requests
3. the identical-output rate of a second pass with caching disabled

Then applies the model-choice rule: the largest model whose estimated run time
for the expected budget (about 21,000 calls) fits in about two overnight
batches, and whose JSON validity is at least 95%.

The prompts here are hand-written stand-ins in the MASSIVE style, sized to the
2,000-token cap. They measure speed and JSON behaviour only. No score from
this script is a research result, and these utterances never enter a scored
run; real data arrives at G2.

Usage:
    python scripts/throughput_test.py --models qwen2.5:3b llama3.1:8b
    python scripts/throughput_test.py --models qwen2.5:3b --n 10   # quick check
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.runs import new_run  # noqa: E402
from src.llm.client import (  # noqa: E402
    MAX_EXAMPLES,
    MAX_INPUT_TOKENS,
    LLMClient,
    estimate_tokens,
    ollama_version,
    resolve_model_digest,
)

# -- the expected-budget rule from section 2A --------------------------
EXPECTED_BUDGET_CALLS = 21_000
OVERNIGHT_HOURS = 9.0
BATCHES = 2
JSON_VALIDITY_FLOOR = 0.95

# -- a stand-in project in the MASSIVE style (alarm + iot, like P1) ----
INTENTS = {
    "alarm_set": "the user asks to create an alarm or reminder at a time",
    "alarm_remove": "the user asks to delete or cancel an existing alarm",
    "alarm_query": "the user asks what alarms are currently set",
    "iot_hue_lightchange": "the user asks to change the colour of a light",
    "iot_hue_lightdim": "the user asks to dim or brighten a light",
    "iot_hue_lightoff": "the user asks to switch a light off",
    "iot_hue_lighton": "the user asks to switch a light on",
    "iot_cleaning": "the user asks a cleaning robot to start or stop",
    "iot_coffee": "the user asks the coffee machine to brew",
    "iot_wemo_on": "the user asks to switch a plug or socket on",
    "iot_wemo_off": "the user asks to switch a plug or socket off",
    "none_of_the_above": "the request is not one of the supported requests above",
}

ENTITIES = {
    "time": "a clock time or relative time expression, as written in the request",
    "date": "a calendar date or day name, as written in the request",
    "house_place": "a room or place in the home",
    "device_type": "the kind of device referred to",
    "color_type": "a colour name",
    "media_type": "the kind of media referred to",
}

EXAMPLES = [
    ("wake me up at seven am tomorrow", "alarm_set", [("time", "seven am"), ("date", "tomorrow")]),
    ("cancel my alarm for six thirty", "alarm_remove", [("time", "six thirty")]),
    ("what alarms do i have set for monday", "alarm_query", [("date", "monday")]),
    ("make the kitchen lights blue", "iot_hue_lightchange",
     [("house_place", "kitchen"), ("color_type", "blue")]),
    ("dim the lamp in the bedroom", "iot_hue_lightdim", [("house_place", "bedroom")]),
    ("turn off the lights in the hallway", "iot_hue_lightoff", [("house_place", "hallway")]),
    ("switch the living room light on please", "iot_hue_lighton", [("house_place", "living room")]),
    ("start the vacuum in the study", "iot_cleaning", [("house_place", "study")]),
    ("brew me a coffee now", "iot_coffee", [("time", "now")]),
    ("turn the socket on in the garage", "iot_wemo_on", [("house_place", "garage")]),
    ("switch off the plug by the tv", "iot_wemo_off", [("device_type", "plug")]),
    ("set an alarm for five in the morning on friday", "alarm_set",
     [("time", "five in the morning"), ("date", "friday")]),
    ("remove all my alarms for the weekend", "alarm_remove", [("date", "the weekend")]),
    ("change the bathroom light to warm white", "iot_hue_lightchange",
     [("house_place", "bathroom"), ("color_type", "warm white")]),
    ("brighten the lights a bit in here", "iot_hue_lightdim", []),
    ("stop the cleaning robot", "iot_cleaning", []),
]

TEST_UTTERANCES = [
    "set an alarm for quarter past six tomorrow morning",
    "please wake me at eight on saturday",
    "delete the alarm i set for noon",
    "do i have any alarms tonight",
    "turn the bedroom lamp red",
    "make it darker in the living room",
    "lights off in the kitchen please",
    "switch on the light above the stairs",
    "start vacuuming the hallway now",
    "make me an espresso",
    "turn on the socket in the shed",
    "cut power to the plug in the office",
    "cancel every alarm for next week",
    "what time is my first alarm on sunday",
    "set the porch light to green",
    "dim the hall lights to half",
    "kill the lights in the garage",
    "put the bathroom light on",
    "have the robot clean the study at nine am",
    "coffee please at seven thirty",
    "wake me up in twenty minutes",
    "remove my seven am alarm for monday",
    "list my alarms",
    "change the lamp colour to purple in the bedroom",
    "turn the brightness down in the kitchen",
    "switch all the lights off upstairs",
    "turn the lights on in the dining room",
    "stop the vacuum please",
    "make two coffees now",
    "power on the socket in the loft",
    "turn off the plug in the bedroom",
    "set a reminder alarm for three pm friday",
    "clear the alarm for half past five",
    "which alarms are set for tomorrow",
    "set the kitchen lights to yellow",
    "brighten up the study",
    "turn off every light in the house",
    "light on in the basement",
    "send the robot to clean the kitchen",
    "brew decaf at six am",
    "switch the garden socket on at eight",
    "turn the office plug off now",
    "alarm at four in the afternoon on tuesday",
    "cancel the alarm i just set",
    "any alarms this evening",
    "make the hallway light cooler",
    "dim everything in the bedroom",
    "lights out in the study",
    "turn the lamp on by the sofa",
    "vacuum the living room at ten tomorrow",
]


def render_prompt(utterance: str) -> tuple[str, int]:
    """Build one full-size schema-guided prompt. Returns (prompt, n_examples).

    Examples are dropped first if the cap would be exceeded; intent and entity
    definitions are never truncated (section 2A).
    """
    header = [
        "You label a home-assistant request. Reply with JSON only.",
        "",
        "Supported intents:",
    ]
    header += [f"- {name}: {desc}" for name, desc in INTENTS.items()]
    header += ["", "Entity types to extract (copy the text exactly as written):"]
    header += [f"- {name}: {desc}" for name, desc in ENTITIES.items()]
    header += [
        "",
        'Reply with: {"intent": "<one intent name>", "entities": '
        '[{"type": "<entity type>", "text": "<exact text from the request>"}]}',
        "Use an empty list if there are no entities. Do not add other fields.",
        "",
        "Examples:",
    ]

    footer = ["", f"Request: {utterance}", "Answer:"]

    chosen = EXAMPLES[:MAX_EXAMPLES]
    while True:
        example_lines = []
        for text, intent, entities in chosen:
            answer = {
                "intent": intent,
                "entities": [{"type": t, "text": v} for t, v in entities],
            }
            example_lines.append(f"Request: {text}")
            example_lines.append(f"Answer: {json.dumps(answer)}")
        prompt = "\n".join(header + example_lines + footer)
        if estimate_tokens(prompt) <= MAX_INPUT_TOKENS or len(chosen) <= 1:
            return prompt, len(chosen)
        chosen = chosen[:-1]


def is_valid_json_answer(text: str) -> bool:
    """A reply is valid only if it parses and has the declared shape."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(data, dict) or "intent" not in data:
        return False
    if not isinstance(data.get("intent"), str):
        return False
    entities = data.get("entities", [])
    if not isinstance(entities, list):
        return False
    return all(
        isinstance(item, dict) and isinstance(item.get("type"), str)
        and isinstance(item.get("text"), str)
        for item in entities
    )


def measure(model: str, prompts: list[tuple[str, int]], host: str, log) -> dict:
    """Two uncached passes over the same prompts: timing, then determinism."""
    digest = resolve_model_digest(model, host)
    # Cache disabled throughout: this script produces latency figures.
    llm = LLMClient(model=model, model_digest=digest, host=host, cache=None, timeout_s=300)

    print(f"\n=== {model} (digest {digest[:19] or 'unknown'}) ===", flush=True)
    print("warm-up (5 requests)...", flush=True)
    for prompt, n_ex in prompts[:5]:
        llm.generate(prompt, max_examples_used=n_ex)

    passes: list[list[str]] = []
    latencies: list[float] = []
    prompt_tokens: list[int] = []
    output_tokens: list[int] = []
    valid = 0
    failures = 0

    for pass_index in (1, 2):
        outputs: list[str] = []
        label = "timing" if pass_index == 1 else "determinism repeat"
        print(f"pass {pass_index} ({label}): {len(prompts)} requests", flush=True)
        for i, (prompt, n_ex) in enumerate(prompts, 1):
            record = llm.generate(prompt, max_examples_used=n_ex)
            outputs.append(record.text)
            if record.error:
                failures += 1
            if pass_index == 1:
                if record.latency_s is not None:
                    latencies.append(record.latency_s)
                    log.log_timing(
                        model=model, case_index=i, latency_s=record.latency_s, warmup=False
                    )
                if record.prompt_tokens:
                    prompt_tokens.append(record.prompt_tokens)
                if record.output_tokens:
                    output_tokens.append(record.output_tokens)
                if is_valid_json_answer(record.text):
                    valid += 1
            log.log_prediction(
                model=model,
                pass_index=pass_index,
                case_index=i,
                cache_hit=record.cache_hit,
                error=record.error,
                prompt_tokens=record.prompt_tokens,
                output_tokens=record.output_tokens,
                latency_s=record.latency_s,
                text=record.text,
            )
            if i % 10 == 0:
                print(f"  {i}/{len(prompts)}", flush=True)
        passes.append(outputs)

    identical = sum(1 for a, b in zip(*passes) if a == b)
    n = len(prompts)
    median_s = statistics.median(latencies) if latencies else None
    p95_s = (
        statistics.quantiles(latencies, n=20)[18]
        if len(latencies) >= 20
        else (max(latencies) if latencies else None)
    )
    est_hours = (median_s * EXPECTED_BUDGET_CALLS / 3600) if median_s else None

    result = {
        "model": model,
        "model_digest": digest,
        "n_requests": n,
        "median_s": median_s,
        "p95_s": p95_s,
        "mean_prompt_tokens": statistics.mean(prompt_tokens) if prompt_tokens else None,
        "mean_output_tokens": statistics.mean(output_tokens) if output_tokens else None,
        "json_validity": valid / n if n else None,
        "identical_output_rate": identical / n if n else None,
        "runtime_failures": failures,
        "estimated_hours_for_expected_budget": est_hours,
        "fits_two_overnight_batches": (
            None if est_hours is None else est_hours <= OVERNIGHT_HOURS * BATCHES
        ),
        "meets_json_floor": (None if n == 0 else valid / n >= JSON_VALIDITY_FLOOR),
    }
    log.log_event("model_measured", **result)
    return result


def choose_model(results: list[dict], order: list[str]) -> tuple[str | None, str]:
    """The section 2A rule: largest eligible model, by the order given."""
    eligible = [
        r for r in results
        if r["meets_json_floor"] and r["fits_two_overnight_batches"]
    ]
    if not eligible:
        return None, (
            "No candidate passes both the JSON-validity floor (0.95) and the "
            "expected-budget time rule. Section 2A step 6 applies: move the "
            "runtime to a Kaggle GPU with Transformers and rerun every "
            "compared system there."
        )
    # "Largest" = latest in the order the user listed them (smallest first).
    best = max(eligible, key=lambda r: order.index(r["model"]))
    return best["model"], (
        f"{best['model']} is the largest candidate meeting both rules: JSON "
        f"validity {best['json_validity']:.2f} and an estimated "
        f"{best['estimated_hours_for_expected_budget']:.1f} h for the expected "
        f"{EXPECTED_BUDGET_CALLS:,}-call budget."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="G0 throughput and determinism test")
    parser.add_argument(
        "--models", nargs="+", required=True,
        help="candidate Ollama models, smallest first (e.g. qwen2.5:3b llama3.1:8b)",
    )
    parser.add_argument("--n", type=int, default=50, help="requests per pass (default 50)")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    try:
        version = ollama_version(args.host)
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach Ollama at {args.host}: {exc}", file=sys.stderr)
        print("Install Ollama and run `ollama serve`, then retry.", file=sys.stderr)
        return 2

    prompts = [render_prompt(u) for u in TEST_UTTERANCES[: args.n]]
    sizes = [estimate_tokens(p) for p, _ in prompts]
    print(f"Ollama {version}; {len(prompts)} prompts, "
          f"about {min(sizes)}-{max(sizes)} estimated input tokens, "
          f"{prompts[0][1]} examples each")

    config = {
        "purpose": "G0 day-1 throughput and determinism test",
        "models": args.models,
        "n_requests": args.n,
        "ollama_version": version,
        "cache_enabled": False,
        "settings": {"temperature": 0.0, "seed": 0, "format": "json"},
        "budgets": {"expected_calls": EXPECTED_BUDGET_CALLS},
        "prompt_source": "hand-written MASSIVE-style stand-in; not a scored result",
    }

    started = time.time()
    with new_run("setup", "throughput", 0, config) as log:
        results = [measure(m, prompts, args.host, log) for m in args.models]
        chosen, reason = choose_model(results, args.models)

        log.write_metrics({
            "results": results,
            "chosen_model": chosen,
            "decision_reason": reason,
            "wall_clock_s": time.time() - started,
        })

        lines = [
            f"# G0 throughput and determinism test ({log.run_id})",
            "",
            f"Ollama {version}. {args.n} full-size requests per pass, cache disabled.",
            "",
            "| model | median s | p95 s | JSON valid | identical repeat | est. h for 21k calls | eligible |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in results:
            fmt = lambda v, p=2: "n/a" if v is None else f"{v:.{p}f}"  # noqa: E731
            lines.append(
                f"| {r['model']} | {fmt(r['median_s'])} | {fmt(r['p95_s'])} | "
                f"{fmt(r['json_validity'])} | {fmt(r['identical_output_rate'])} | "
                f"{fmt(r['estimated_hours_for_expected_budget'], 1)} | "
                f"{'yes' if r['meets_json_floor'] and r['fits_two_overnight_batches'] else 'no'} |"
            )
        lines += ["", f"**Chosen runtime model: {chosen or 'none eligible'}**", "", reason, ""]

        below = [r for r in results if (r["identical_output_rate"] or 1) < 1.0]
        if below:
            lines.append(
                "Determinism is below 100% for: "
                + ", ".join(f"{r['model']} ({r['identical_output_rate']:.2f})" for r in below)
                + ". Report this as a limitation; the cached first output is the "
                "recorded prediction for every system."
            )
        log.write_summary("\n".join(lines))
        print("\n".join(lines[3:]))
        print(f"\nSaved to runs/{log.run_id}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
