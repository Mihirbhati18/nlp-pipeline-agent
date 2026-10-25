"""Build "How Every Test Was Done": a step-by-step guide to doing each test yourself.

Every command in the document was run on 25 Oct 2026 and the screen images are
drawn from those real outputs (`captures/`). The hand-calculation and
first-test examples were checked: the F1 example against scikit-learn, and
the first test by running it with pytest (2 passed).

Usage (from the project root):
    python reports/guide/make_howto_docx.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from docx_helpers import Builder  # noqa: E402

IMG = HERE / "images"
OUT = HERE / "How_Every_Test_Was_Done.docx"

b = Builder()
b.title(
    "How Every Test Was Done",
    "A step-by-step guide to understanding, explaining and re-doing each test yourself",
    ["Mihir Bhati (24BCE5341)  ·  Ahana Sharan (24BCE5334)",
     "25 October 2026  ·  Project folder: D:\\MyClaudeProject\\nlp"],
)
b.callout(
    "**Why this guide exists.** Your teacher allows AI use, but expects you to understand what was done and "
    "to be able to do any step yourself. Claude Code wrote the code and ran the tests. This guide teaches the "
    "recipe behind every test, gives a small example you can work out on paper, and the exact command to "
    "run it yourself, with what your screen should show.\n"
    "**How to use it:** read Part A first, since it explains the idea every test is built on. Then do the "
    "30-minute rehearsal in Part E once before you present."
)
b.h("Contents", 2)
b.numbered([
    "Part A. The basics: what a test is, and watching one happen",
    "Part B. Software tests: writing and running your own",
    "Part C. Every experiment, one by one (15 tests)",
    "Part D. If the teacher says \"do it now\"",
    "Part E. 30-minute rehearsal checklist",
    "Part F. How to explain the AI use honestly",
])
b.page_break()

# =========================================================================
b.h("Part A. The basics")

b.h("A1. There are two kinds of \"test\" in this project", 2)
b.table(["", "Software tests", "Experiments (evaluations)"], [
    ["Question", "Does the code do what it should?", "How good is each system at the task?"],
    ["Example", "\"If every answer is right, the scorer must give F1 = 1.0\"", "\"How many of 100 real requests does the agent understand?\""],
    ["Answer", "pass or fail", "a score, such as F1 = 0.974"],
    ["How many", "371", "over 60 recorded runs"],
    ["Run with", "python -m pytest tests", "the scripts in the scripts folder"],
    ["Where it lives", "tests folder", "results in the runs folder"],
], [2.6, 7.0, 7.0])
b.p("Both matter. Software tests prove the measuring tools work; experiments use those tools to measure the systems. "
    "A score from a broken scorer would mean nothing, which is why the scorer itself has tests.")

b.h("A2. The recipe every experiment follows", 2)
b.image(IMG / "evaluation_flow.png", "Every experiment repeats these steps for each of the 100 development requests.")
b.numbered([
    "**Take a request** from the development file, for example \"make a room darker\". The dataset also gives its correct answer: intent `iot_hue_lightdim`, entity `house_place = room`.",
    "**Build the prompt**: the list of allowed intents, a few worked examples, then the request.",
    "**Ask the AI model.** It replies in JSON, e.g. `{\"intent\": \"iot_hue_lightdim\", \"entities\": [...]}`.",
    "**Read the reply**: check the format is valid and find each extracted entity in the request text.",
    "**Compare** with the correct answer: right or wrong.",
    "**Save** the prediction, then move to the next request.",
    "**After all 100**, the scorer counts rights and wrongs and computes F1, accuracy and the other scores, and saves them in a dated run folder.",
])
b.p("That is the whole idea. The different experiments change only **which system** answers (B0, B1, A1, A2...) "
    "or **which requests** it gets (clean, with typos...).")

b.h("A3. Watch one experiment happen, step by step", 2)
b.p("The walkthrough tool prints every step from A2 for three requests. **Show this to your teacher first**: "
    "it makes everything else easy to follow.")
b.code("python scripts/walkthrough.py")
b.image(IMG / "screen_walk_request.png", "One request, all six steps (real output).")
b.image(IMG / "screen_walk_scores.png", "The end: the scores for these requests, from our scorer and from scikit-learn.")
b.p("Try other designs, more requests, or a live answer from the model instead of a saved one:")
b.code("python scripts/walkthrough.py --design schema-sim-llm --n 5\npython scripts/walkthrough.py --live")

b.h("A4. Work out F1 by hand", 2)
b.p("Being able to compute F1 yourself is the best proof you understand the results. Here are 8 requests:")
b.table(["#", "Correct intent", "System said", "Right?"], [
    ["1", "alarm_set", "alarm_set", "yes"], ["2", "alarm_set", "alarm_set", "yes"],
    ["3", "alarm_set", "alarm_remove", "no"], ["4", "alarm_remove", "alarm_remove", "yes"],
    ["5", "alarm_remove", "alarm_set", "no"], ["6", "lights_off", "lights_off", "yes"],
    ["7", "lights_off", "lights_off", "yes"], ["8", "lights_off", "alarm_set", "no"],
], [1.0, 5.0, 5.0, 5.6], font=10)
b.p("**Step 1. Count, for each intent:**")
b.bullets([
    "**TP (true positive):** the system said this intent and it was right.",
    "**FP (false positive):** the system said this intent but it was wrong.",
    "**FN (false negative):** this was the correct intent but the system said something else.",
])
b.table(["Intent", "TP", "FP", "FN", "Precision = TP/(TP+FP)", "Recall = TP/(TP+FN)", "F1"], [
    ["alarm_set", "2 (#1, #2)", "2 (#5, #8)", "1 (#3)", "2/4 = 0.500", "2/3 = 0.667", "0.571"],
    ["alarm_remove", "1 (#4)", "1 (#3)", "1 (#5)", "1/2 = 0.500", "1/2 = 0.500", "0.500"],
    ["lights_off", "2 (#6, #7)", "0", "1 (#8)", "2/2 = 1.000", "2/3 = 0.667", "0.800"],
], [2.6, 1.9, 1.9, 1.5, 3.1, 3.0, 2.6], font=9)
b.p("**Step 2. F1 for each intent** = 2 × precision × recall / (precision + recall). "
    "For alarm_set: 2 × 0.5 × 0.667 / (0.5 + 0.667) = 0.571.")
b.p("**Step 3. Macro-F1** = average of the three: (0.571 + 0.500 + 0.800) / 3 = **0.624**. "
    "**Accuracy** = 5 right out of 8 = **0.625**.")
b.p("**Step 4. Check it with scikit-learn.** Save this as `check_f1.py` in the project folder and run "
    "`python check_f1.py`. It prints 0.624 and 0.625, the same as the hand calculation.")
b.code(
    "from sklearn.metrics import f1_score, accuracy_score\n\n"
    "gold = ['alarm_set', 'alarm_set', 'alarm_set', 'alarm_remove', 'alarm_remove',\n"
    "        'lights_off', 'lights_off', 'lights_off']\n"
    "pred = ['alarm_set', 'alarm_set', 'alarm_remove', 'alarm_remove', 'alarm_set',\n"
    "        'lights_off', 'lights_off', 'alarm_set']\n\n"
    "print('macro F1', round(f1_score(gold, pred, average='macro'), 3))\n"
    "print('accuracy', accuracy_score(gold, pred))"
)
b.p("In the real experiments the scorer does exactly this, over 100 requests and 10 to 12 intents. "
    "Requests the system wrongly refused also count as wrong.")
b.page_break()

# =========================================================================
b.h("Part B. Software tests: writing and running your own")

b.h("B1. What an automated test is", 2)
b.p("A test is a short program with three parts: **set up** an input, **run** the code, **check** the result "
    "is what it must be. If the check fails, the test fails. Here is a real-style example:")
b.code(
    "def test_a_perfect_system_scores_1():\n"
    "    # 1. set up: two requests and their correct answers\n"
    "    cases = [\n"
    "        {\"case_id\": \"a\", \"utt\": \"set an alarm\", \"true_intent\": \"alarm_set\",\n"
    "         \"in_scope\": True, \"entities\": []},\n"
    "        {\"case_id\": \"b\", \"utt\": \"delete my alarm\", \"true_intent\": \"alarm_remove\",\n"
    "         \"in_scope\": True, \"entities\": []},\n"
    "    ]\n"
    "    answers = [\n"
    "        Prediction(\"a\", \"ok\", \"alarm_set\", [], True, True),\n"
    "        Prediction(\"b\", \"ok\", \"alarm_remove\", [], True, True),\n"
    "    ]\n"
    "    # 2. run the scorer\n"
    "    result = score(cases, answers, labels=[\"alarm_set\", \"alarm_remove\"])\n"
    "    # 3. check: every answer is right, so F1 must be exactly 1.0\n"
    "    assert result[\"primary\"][\"intent_macro_f1\"] == 1.0"
)
b.p("`assert` means \"this must be true\". The project's 371 tests are all built this way. The scorer's tests use "
    "small examples where the correct F1 was calculated by hand, like Part A4.")

b.h("B2. Write and run your own first test (10 minutes)", 2)
b.numbered([
    "In the project folder, open the `tests` folder and create a new file called `test_my_first.py`.",
    "Paste this into it and save:",
])
b.code(
    "from sklearn.metrics import f1_score\n\n"
    "from src.evaluation.scorer import Prediction, score\n\n\n"
    "def test_a_perfect_system_scores_1():\n"
    "    cases = [\n"
    "        {\"case_id\": \"a\", \"utt\": \"set an alarm\", \"true_intent\": \"alarm_set\", \"in_scope\": True, \"entities\": []},\n"
    "        {\"case_id\": \"b\", \"utt\": \"delete my alarm\", \"true_intent\": \"alarm_remove\", \"in_scope\": True, \"entities\": []},\n"
    "    ]\n"
    "    answers = [\n"
    "        Prediction(\"a\", \"ok\", \"alarm_set\", [], True, True),\n"
    "        Prediction(\"b\", \"ok\", \"alarm_remove\", [], True, True),\n"
    "    ]\n"
    "    result = score(cases, answers, labels=[\"alarm_set\", \"alarm_remove\"])\n"
    "    assert result[\"primary\"][\"intent_macro_f1\"] == 1.0\n\n\n"
    "def test_our_scorer_agrees_with_sklearn_on_one_mistake():\n"
    "    cases = [\n"
    "        {\"case_id\": \"a\", \"utt\": \"set an alarm\", \"true_intent\": \"alarm_set\", \"in_scope\": True, \"entities\": []},\n"
    "        {\"case_id\": \"b\", \"utt\": \"delete my alarm\", \"true_intent\": \"alarm_remove\", \"in_scope\": True, \"entities\": []},\n"
    "        {\"case_id\": \"c\", \"utt\": \"wake me at six\", \"true_intent\": \"alarm_set\", \"in_scope\": True, \"entities\": []},\n"
    "    ]\n"
    "    answers = [\n"
    "        Prediction(\"a\", \"ok\", \"alarm_set\", [], True, True),\n"
    "        Prediction(\"b\", \"ok\", \"alarm_remove\", [], True, True),\n"
    "        Prediction(\"c\", \"ok\", \"alarm_remove\", [], True, True),  # the mistake\n"
    "    ]\n"
    "    ours = score(cases, answers, labels=[\"alarm_set\", \"alarm_remove\"])[\"primary\"][\"intent_macro_f1\"]\n"
    "    theirs = f1_score([\"alarm_set\", \"alarm_remove\", \"alarm_set\"],\n"
    "                      [\"alarm_set\", \"alarm_remove\", \"alarm_remove\"], average=\"macro\")\n"
    "    assert abs(ours - theirs) < 1e-9"
)
b.numbered(["Run it. `-vv` lists each test by name:"])
b.code("python -m pytest tests/test_my_first.py -vv")
b.image(IMG / "screen_my_first_test.png", "Both tests pass (real output).")
b.numbered([
    "**Now break it on purpose:** change `== 1.0` to `== 0.9` and run it again. The first test now says "
    "**FAILED** and shows the real value (1.0). That is how tests catch mistakes.",
    "Change it back to `1.0`. You can keep this file: it is your own test, and the total becomes 373.",
])
b.p("The second test is a small version of the project's big independent check: our scorer and scikit-learn must agree.")

b.h("B3. Run the project's own tests", 2)
b.code("python -m pytest tests                       # all 371, about 15 seconds\n"
       "python -m pytest tests/test_scorer.py -vv    # the scorer's 14 tests, by name")
b.image(IMG / "screen_scorer_tests.png", "Some of the scorer's tests. Each name says what it checks.")
b.table(["Test file", "What it checks"], [
    ["test_scorer.py", "F1 and every score, against hand-calculated examples"],
    ["test_massive.py", "the dataset's answers were converted correctly"],
    ["test_access.py", "test data really is locked before the freeze"],
    ["test_architect.py / test_architect_v2.py", "the agent can only pick real designs and never exceeds 4 tries"],
    ["test_runtime.py", "the exported package refuses to load if tampered with"],
    ["test_reproduce_metrics.py", "the reproduction check catches a hand-edited number"],
], [6.0, 10.6])
b.page_break()

# =========================================================================
b.h("Part C. Every experiment, one by one")
b.p("Each experiment below has the same layout: **the idea**, **how it was done**, **the command**, how long it "
    "takes, and **what to say**. Commands run from `D:\\MyClaudeProject\\nlp` with the Ollama app open. "
    "Most finish quickly because the model's earlier answers are saved; each run creates a new dated folder "
    "in `runs`, which shows the results repeat.")


def experiment(number, name, idea, how, command, time, say, image=None, caption=None):
    b.h(f"C{number}. {name}", 2)
    b.p(f"**Idea:** {idea}")
    b.p("**How it was done:**")
    b.numbered(how) if isinstance(how, list) else b.p(how)
    if command:
        b.code(command)
    b.p(f"**Time:** {time}", size=10)
    if image:
        b.image(IMG / image, caption)
    b.p(f"**Say:** \"{say}\"", size=10.5)


experiment(1, "The data and the splits",
           "Use real, public data, and split it once into examples, development data and locked test data.",
           ["Downloaded MASSIVE 1.1 (Amazon): 16,521 English requests with their correct intents and entities.",
            "Chose the domains for each project (P1 home assistant, P2 productivity, P3 ordering and travel).",
            "Drew 10 examples per intent, 100 development requests and 300 test requests per project, using a fixed seed so the draw is identical every time.",
            "Recorded every request ID and a fingerprint (hash) of every file, and checked no request appears in two places."],
           "python scripts/prepare_data.py --check", "a few seconds; it only checks, it changes nothing",
           "Each project's sizes are fixed and the leakage check passes: no request is shared between splits.",
           "screen_data_check.png", "The data check (real output).")

experiment(2, "Model speed and repeatability",
           "Before anything else, measure whether the AI model is fast enough and gives the same answer twice.",
           ["Sent 50 full-size requests to the model with saved answers switched off, timing each one.",
            "Sent the same 50 again and compared: 50 of 50 answers were identical.",
            "Result: 0.42 s median per request, valid JSON every time."],
           "python scripts/throughput_test.py --models qwen2.5:3b", "a few minutes (100 live requests)",
           "The model answers in under half a second and is fully repeatable, so anyone re-running our experiments gets the same answers.")

experiment(3, "B0: word matching (no AI)",
           "The simplest possible system, as a floor every AI system must beat.",
           ["Turn each example sentence into word weights (TF-IDF: words that are rare overall but frequent in a sentence weigh more).",
            "Train a standard classifier (logistic regression) on the 10 examples per intent.",
            "For off-topic requests: if a request is too unlike every example (below a threshold chosen on development data), refuse it.",
            "Score on the 100 development requests."],
           "python scripts/run_b0.py --projects P1", "a few seconds; no AI model needed",
           "A basic word-matching classifier gets 0.78 on P1; every AI system has to beat that to be worth it.")

experiment(4, "B1: one generic prompt",
           "What you get with one standard AI prompt and no design decisions.",
           ["Fixed one design in advance: joint-fixed-llm.",
            "Ran it on the 100 development requests through the recipe in Part A2."],
           "python scripts/run_design.py --systems B1 --projects P1", "under a minute",
           "One generic prompt reaches 0.927; the agent has to beat this to show its design work adds anything.")

experiment(5, "B2: a person configuring by hand",
           "Measure what a person achieves by hand, and how long it takes.",
           ["Created a worksheet with the project description and the 12 designs.",
            "A team member chose a design, wrote descriptions, timed themselves and declared any help (P2 used ChatGPT).",
            "The worksheet was checked and saved as a run, with the minutes and the help recorded."],
           "python scripts/run_b2.py check --project P1\npython scripts/run_b2.py finish --project P1",
           "the person's own time (38 min for P1, under 6 for P2)",
           "By hand, a beginner got 0.858 on P1 in 38 minutes; the agent got 0.958 with no human time.")

experiment(6, "B3: the published baseline (XLM-R)",
           "Compare with the model the MASSIVE paper itself used.",
           ["Downloaded XLM-R, a 270-million-parameter language model.",
            "Fine-tuned it: trained its internal numbers on the examples, for 30 rounds (B3-k, 10 examples per intent) or on all training data (B3-full, upper reference).",
            "Chose the off-topic threshold on development data, then scored with the same scorer as everything else."],
           "python scripts/run_b3_local.py --projects P1 --variants B3-k",
           "about 11 minutes for P1 B3-k; about 85 minutes for all four versions. Don't run it live; show the run folder instead",
           "We compared against the published baseline: with the same data our agent wins on intents, and A2 also wins on entities.")

experiment(7, "B4: random search",
           "Check whether the agent chooses designs better than luck.",
           ["Picked 4 of the 12 designs at random, with the same budget the agent gets.",
            "Scored them on development data and kept the best, by the same rule the agent uses.",
            "Repeated with 5 different random seeds, and also tried all 12 (the ceiling)."],
           "python scripts/run_design.py --systems B4-random --exhaustive --projects P1", "under a minute",
           "Random search averaged 0.959 on P1. A1 did not beat it; the improved A2 reached the best design.")

experiment(8, "A1 and A2: the agent",
           "Run the full framework: Analyzer, Architect, scoring the candidates, selection.",
           ["The Analyzer asks the AI to describe every intent and field (2 calls).",
            "The Architect asks the AI which designs to try; A2 asks it to rank each design choice separately.",
            "Each chosen design is scored on development data; after 3, the scores go back to the Architect for a 4th choice.",
            "The best-scoring design is selected; every choice and its reason are saved in the run folder."],
           "python scripts/run_design.py --systems A1 --projects P1\npython scripts/run_a2.py", "under a minute each",
           "A2 ranks every choice, tests alternatives one change at a time, and reached the best of all 12 designs on both projects.",
           "screen_run_a2.png", "The A2 run: the AI's rankings, the 4 designs it tried, and the decision (real output).")

experiment(9, "Ablations",
           "Find out which part of the agent matters by removing one part at a time.",
           ["Without the Analyzer: no descriptions written.",
            "Without the Architect's reasoning: a fixed order instead of the AI's choice.",
            "Without scored selection: take the first design, unscored.",
            "Without repair: no second chance on a badly formatted reply.",
            "Each variant scored on the same 100 requests and compared with the full system."],
           "python scripts/run_dev_analysis.py --skip-timing", "1 to 2 minutes",
           "Scoring the candidates is what helps most (+3 to +4 points); A1's reasoning did not help, which is why we built A2.")

experiment(10, "Confidence intervals (bootstrap)",
           "Check whether a difference between two systems is real or could be luck.",
           "**By hand, the idea:** imagine 5 requests. Make a \"pretend\" test set by drawing 5 of them at random, "
           "allowing repeats (e.g. #2, #2, #4, #1, #5). Score both systems on it and note the difference. Do this "
           "1,000 times. If the difference is above zero in nearly all of the 1,000 draws, it is real; if it often "
           "flips sign, it could be luck. The middle 95% of the 1,000 differences is the confidence interval. "
           "The script does this for every comparison.",
           "python scripts/run_dev_analysis.py --skip-timing", "included in C9",
           "With 100 development requests, the intervals still include zero, so we don't call any difference significant yet; the 300-request test sets will narrow them.")

experiment(11, "Real speed (timing)",
           "Measure how fast the final pipeline answers when nothing is saved in advance.",
           ["Switch off the saved answers so every request goes to the model live.",
            "Send 5 warm-up requests (not counted), then 50 development requests.",
            "Time each one with a stopwatch in the code, then report the median and the slowest 5% (p95).",
            "Requests refused before reaching the model are left out, so they cannot make a design look faster."],
           "python scripts/run_dev_analysis.py", "about 5 minutes (includes C9 and C10)",
           "Every pipeline answers in under one second, even in the slowest 5% of requests.")

experiment(12, "Error analysis",
           "Find out what kind of mistakes the agent makes, not just how many.",
           ["Look at every development request the agent got wrong.",
            "Put each mistake in one category: confused intent, wrongly refused, answered an off-topic request, missed entity, extra (spurious) entity, wrong entity type, wrong boundary (too much or too little text), or a value not in the request.",
            "Example: \"wake me at five am\" with the answer time = \"five\" is a wrong boundary (should be \"five am\").",
            "Count each category per project."],
           "python scripts/run_dev_analysis.py --skip-timing", "included in C9",
           "Most of the original agent's mistakes were extracting extra words as entities, which pointed us to the main weakness.")

experiment(13, "Robustness to messy typing",
           "Check whether the systems still work when people type carelessly.",
           ["Rewrite every development request three ways, the same way every time (fixed seed):",
            "typos: two neighbouring letters swapped, e.g. \"tunr the lights off please\";",
            "capitals: \"TURN THE LIGHTS OFF PLEASE\";",
            "filler: \"hey, could you please turn the lights off please, thanks\".",
            "Score B0, B1 and the agent on each rewritten set."],
           "python scripts/run_robustness.py", "about a minute (answers saved earlier)",
           "The AI systems lose at most about 7 points on messy input; word matching drops by up to 27.")

experiment(14, "Export and live demo",
           "Show the chosen pipeline can be saved and used by another program.",
           ["Save the selected design, the Analyzer's descriptions, the examples and the model's fingerprint as a package.",
            "Fingerprint every package file; a changed file makes the package refuse to load.",
            "Load the package in a fresh program and answer normal, off-topic and invalid requests."],
           "python scripts/demo.py --project P1\npython scripts/demo.py --project P1 --interactive\n"
           "python -m pytest tests/test_runtime.py -vv -k modified",
           "about 10 seconds each",
           "The agent's choice is exported as a package any program can load; if anyone edits it, it refuses to load, as this test shows.")

experiment(15, "Checking the results themselves",
           "Prove that no recorded number was edited or computed wrongly.",
           ["Re-score every run from its saved predictions and compare with the recorded score (reproduction check).",
            "Recompute F1, accuracy and the off-topic scores with scikit-learn, without our scorer (independent check).",
            "Both compare to 9 decimal places: 44 of 44 runs agree."],
           "python scripts/reproduce_metrics.py\npython scripts/verify_with_sklearn.py\npython scripts/show_evidence.py",
           "under a minute; the last command runs every check at once",
           "Every recorded number can be recomputed from the raw predictions, and the standard library scikit-learn gets the same numbers.")
b.page_break()

# =========================================================================
b.h("Part D. If the teacher says \"do it now\"")
b.table(["The teacher asks…", "Type this", "Time", "What appears"], [
    ["\"Show me a test running.\"", "python scripts/walkthrough.py", "5 s", "the six steps for three requests"],
    ["\"Run all your tests.\"", "python -m pytest tests", "15 s", "371 passed"],
    ["\"How do you compute F1?\"", "work Part A4 on paper, then python check_f1.py", "5 min", "0.624 by hand and by scikit-learn"],
    ["\"Write a test.\"", "the file from Part B2, then python -m pytest tests/test_my_first.py -vv", "5 min", "2 passed"],
    ["\"Run your agent.\"", "python scripts/run_a2.py", "under 1 min", "the AI's rankings, 4 designs tried, the choice"],
    ["\"Run a baseline.\"", "python scripts/run_b0.py --projects P1", "seconds", "B0 score 0.780"],
    ["\"Is the data clean?\"", "python scripts/prepare_data.py --check", "seconds", "sizes and leakage check pass"],
    ["\"Are your numbers real?\"", "python scripts/verify_with_sklearn.py", "seconds", "44 agree"],
    ["\"Show me it working.\"", "python scripts/demo.py --project P1 --interactive", "live", "answers the teacher's own sentences"],
    ["\"Show me everything.\"", "python scripts/show_evidence.py", "under 1 min", "Overall: all checks passed"],
    ["\"Retrain the published baseline.\"", "explain C6, then open runs\\20261015_2240_P1_B3-k_0", "show folder", "training too long to run live (11 min to 85 min)"],
], [3.8, 6.0, 1.7, 5.1], font=8.5)
b.callout("If something fails during a live run, it is almost always because the Ollama app is not open. "
          "Open it from the Start menu, wait 10 seconds and run the command again.", fill="FEF9C3")

# =========================================================================
b.h("Part E. 30-minute rehearsal checklist")
b.p("Do these once before presenting. Tick each one when it works on your laptop.")
b.checklist([
    "Open Ollama; in PowerShell run `cd D:\\MyClaudeProject\\nlp` and `ollama list`.",
    "Run `python scripts/walkthrough.py` and explain each of the six steps out loud.",
    "Work out the Part A4 F1 example on paper without looking, then check it with `check_f1.py`.",
    "Create `tests/test_my_first.py`, run it, break it, fix it.",
    "Run `python -m pytest tests` and say what the tests check (Part B3 table).",
    "Run `python scripts/run_a2.py` and explain the rankings and the 4 designs tried.",
    "For each experiment in Part C, say its idea in one sentence without reading.",
    "Run `python scripts/verify_with_sklearn.py` and explain why \"agrees\" matters.",
    "Run the demo in interactive mode and try three sentences of your own.",
    "Run `python scripts/show_evidence.py` and find \"Overall: all checks passed\".",
])

# =========================================================================
b.h("Part F. How to explain the AI use honestly")
b.p("Your teacher allows AI use. What matters is that you are open about it and understand the work. Something like:")
b.callout("\"We planned the project and decided how it should be tested: which baselines, which data, which scores "
          "and which checks. We used Claude Code, an AI coding assistant, to write the code and run the experiments. "
          "We checked every result, and we can explain and re-run each test, for example here is a test running step "
          "by step. The AI assistance is recorded in docs\\contributions.md, as our plan requires.\"")
b.p("Then show one or two things live from Part D. Being able to run and explain a test on the spot is the proof "
    "that you understand it.")

b.save(OUT)
print(f"wrote {OUT.relative_to(HERE.parents[1])}")
