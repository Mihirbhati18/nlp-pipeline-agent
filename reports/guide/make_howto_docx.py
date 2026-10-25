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
OUT = HERE / "How_Every_Test_Was_Done_v2.docx"

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
    "**How to use it:** read Part A first, slowly: it shows where every file is and how a score is calculated from them. Then do the "
    "30-minute rehearsal in Part E once before you present."
)
b.h("Contents", 2)
b.numbered([
    "Part A. The basics: what a test is, where the files are, and how a score is calculated",
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

b.h("A3. Where everything lives: the files behind every test", 2)
b.p("Before running anything, it helps to know that the whole project is just **folders of files** on your "
    "laptop, in `D:\\MyClaudeProject\\nlp`. Open that folder in File Explorer and you will see these:")
b.table(["Folder", "What is inside", "You will use it for"], [
    ["data\\processed\\P1\\", "The requests and their correct answers for project P1", "seeing the data the systems are tested on"],
    ["scripts\\", "Small programs you run, one per job (walkthrough.py, explain_f1.py, demo.py...)", "running every test"],
    ["src\\", "The framework itself: the code the scripts use", "seeing how a step works"],
    ["runs\\", "One folder per experiment, holding its answers and its scores", "checking any result"],
    ["tests\\", "The 371 automated tests", "Part B"],
    ["reports\\", "Reports, charts and the files these tools save", "showing results"],
], [3.8, 7.6, 5.2], font=9.5)

b.h("The two files every test is built from", 3)
b.p("**File 1: the correct answers.** `data\\processed\\P1\\dev.jsonl` holds the 100 development requests for P1 "
    "and, for each one, the correct answer. These come from the MASSIVE dataset, where people labelled every "
    "request. Open it with Notepad (right-click → Open with → Notepad). Each line is one request. The second line is:")
b.code('{"case_id": "massive-24", "utt": "make a room darker", "true_intent": "iot_hue_lightdim",\n'
       ' "in_scope": true, "entities": [{"type": "house_place", "text": "room", "start": 7, "end": 11}], ...}')
b.table(["Field", "Meaning", "In this line"], [
    ["case_id", "the request's ID in the MASSIVE dataset", "massive-24"],
    ["utt", "the request, exactly as a user typed it (utterance)", "make a room darker"],
    ["true_intent", "the correct intent", "iot_hue_lightdim (dim a light)"],
    ["in_scope", "true = the app should handle it; false = off-topic, should be refused", "true"],
    ["entities", "the details to extract, with their position in the sentence (counting characters from 0)", "house_place = \"room\", characters 7 to 11"],
], [2.6, 8.4, 5.6], font=9.5)
b.p("The format is called **JSONL**: one record per line, written as `\"name\": value` pairs.", size=10.5)

b.p("**File 2: what a system answered.** Every experiment saves its answers in its own folder in `runs`. "
    "For A2 on P1 that is `runs\\20261024_1654_P1_A2-selected_0\\predictions.jsonl`. The folder name is the date "
    "and time (24 Oct, 16:54), the project (P1) and the system (A2). The line for the same request is:")
b.code('{"case_id": "massive-24", "gold_intent": "iot_hue_lightdim", "gold_in_scope": true, "status": "ok",\n'
       ' "predicted_intent": "iot_hue_lightdim", "predicted_entities": [{"type": "house_place", "text": "room"}], ...}')
b.table(["Field", "Meaning"], [
    ["gold_intent", "the correct intent, copied from File 1 (\"gold\" means correct answer)"],
    ["status", "ok = the system answered with an intent; oos = it refused the request as off-topic; invalid or error = its reply was broken"],
    ["predicted_intent", "the intent the system answered"],
    ["predicted_entities", "the details the system extracted"],
], [3.6, 13.0], font=9.5)
b.p("**Every score in this project is just these two files compared line by line.** Request massive-24: correct "
    "`iot_hue_lightdim`, answered `iot_hue_lightdim`, so it is right. Section A5 shows how all 80 lines become an F1 score.")

b.h("A4. The walkthrough script, explained", 2)
b.p("A **script** is a text file of instructions written in Python. `walkthrough.py` is one of them, in the "
    "scripts folder: `D:\\MyClaudeProject\\nlp\\scripts\\walkthrough.py`. You can open it to read it, in Notepad or "
    "in VS Code (installed on this laptop), with:")
b.code("code scripts\\walkthrough.py")
b.p("It is a teaching tool: it does what a real experiment does, but for only three requests, and prints every "
    "step instead of doing it silently. It changes nothing and saves nothing.")

b.h("What it does, step by step, and where each step's code is", 3)
b.table(["Step", "What happens", "Files it reads", "Code that does it"], [
    ["Start", "Locks the test data, then reads the project's intents, fields and description",
     "data\\manifests\\P1.json, configs\\descriptions\\P1.md", "src\\analyzer\\spec.py, src\\analyzer\\access.py"],
    ["1", "Takes a request and its correct answer", "data\\processed\\P1\\dev.jsonl (File 1)", "load_cases in src\\analyzer\\spec.py"],
    ["2", "Picks example requests to show the model (fixed, or the most similar ones)",
     "data\\processed\\P1\\kshot.jsonl (120 labelled examples)", "src\\pipelines\\examples.py"],
    ["3", "Writes the prompt: instructions, the list of intents, the examples, then the request", "—",
     "render_prompt in src\\pipelines\\catalogue.py"],
    ["4", "Sends the prompt to the AI model and receives its reply",
     "cache\\ folder (the model's saved answers), or the live model with --live",
     "src\\llm\\client.py, which talks to Ollama at http://127.0.0.1:11434"],
    ["5", "Reads the reply: is it valid JSON with a real intent? Where is each entity in the sentence?", "—",
     "src\\evaluation\\output_schema.py, src\\evaluation\\span_rule.py"],
    ["6", "Compares the answer with the correct one: right or wrong", "—", "inside walkthrough.py"],
    ["7", "Scores the requests, with our scorer and with scikit-learn", "—",
     "src\\evaluation\\scorer.py and the scikit-learn library"],
], [1.2, 5.6, 5.0, 4.8], font=8.5)
b.p("**\"From the saved cache\"** means: when the experiments ran, every answer the model gave was saved in the "
    "`cache` folder. The walkthrough reuses those saved answers, so you see exactly what the experiments saw, "
    "instantly. Add `--live` to ask the model fresh; because the model is repeatable, it gives the same answers.")

b.h("How to run it", 3)
b.numbered([
    "Open the **Ollama** app from the Start menu (it runs the AI model in the background).",
    "Open **PowerShell** (Start → type PowerShell → Enter).",
    "Go to the project folder by typing this and pressing Enter:",
])
b.code("cd D:\\MyClaudeProject\\nlp")
b.numbered(["Run the script:"])
b.code("python scripts/walkthrough.py")
b.p("It prints three requests: two the app should handle and one off-topic one. For each, steps 1 to 6 appear "
    "under it. Here is request 2, with what each part means:")
b.image(IMG / "screen_walk_request.png", "Request 2 of 3 (real output).")
b.table(["What you see", "What it means"], [
    ["1. Correct answer", "read from File 1: the dataset says this request is iot_hue_lightdim, with house_place = room"],
    ["2. Examples put in the prompt", "worked examples the model is shown first, so it learns the format (12 here: one per intent)"],
    ["3. Prompt sent to the model", "the full text the model receives: 68 lines, of which the start and end are shown"],
    ["4. Model's raw reply", "exactly what the model wrote back, as JSON"],
    ["5. Reading the reply", "the format is valid, the intent is a real one, and \"room\" is found at characters 7 to 11 of the request"],
    ["6. Verdict", "the answer matches the correct one, so it is right"],
], [4.6, 12.0], font=9.5)
b.image(IMG / "screen_walk_scores.png", "The end of the output: all three right, so every score is 1.000.")
b.p("**How this relates to the real experiments:** an experiment runs exactly these steps, with the same code, "
    "for all 100 development requests instead of 3. It saves every answer in a predictions.jsonl file (File 2) "
    "and the scores in metrics.json, inside a new run folder.")
b.p("Other things to try:")
b.code("python scripts/walkthrough.py --n 5                     # 5 requests instead of 3\n"
       "python scripts/walkthrough.py --design schema-sim-llm   # the design A2 chose\n"
       "python scripts/walkthrough.py --live                    # ask the model fresh")

b.h("A5. Work out F1 yourself, on the real results", 2)
b.p("A2's recorded intent macro-F1 on P1 is **0.974**. Here is how to get that number yourself from Files 1 and 2.")

b.h("Option 1: let the explain script show every step", 3)
b.code("python scripts/explain_f1.py")
b.p("The script `scripts\\explain_f1.py` reads File 1 and File 2, puts them side by side, does the counting, and "
    "prints each step. It also saves the side-by-side table as a spreadsheet file.")
b.image(IMG / "screen_explain_table.png", "Steps 1 to 3: the two files, and the requests side by side (real output).")
b.p("Why only 80 of the 100 requests? 20 are off-topic and have no correct intent; they are scored separately as "
    "off-topic F1. Look at request #15, \"i need some more lights\": the correct intent is iot_hue_lightup, but A2 "
    "**refused** it as off-topic. That is one of A2's 4 mistakes.")
b.image(IMG / "screen_explain_counts.png", "Steps 4 to 6: counting, the formula for each intent, and the average (real output).")
b.p("Read the alarm_query line like this: A2 got 6 alarm_query requests right (TP 6: requests #22, #34, #40, #41, "
    "#52, #64). It never said alarm_query wrongly (FP 0). It missed one, request #75 (FN 1). So precision = 6/6 = "
    "1.000, recall = 6/7 = 0.857 and F1 = 2 × 1.000 × 0.857 / (1.000 + 0.857) = 0.923. Doing this for all 12 intents "
    "and averaging gives 0.9744. That matches the number recorded in metrics.json and the one scikit-learn computes.")
b.p("Every run works the same way. For the generic prompt B1, for example:")
b.code("python scripts/explain_f1.py --run 20261013_0110_P1_B1_0")

b.h("Option 2: count it yourself in a spreadsheet", 3)
b.p("The script saved all 80 lines as `reports\\f1_explained_20261024_1654_P1_A2-selected_0.csv`. Open it in Excel, "
    "or upload it to Google Sheets (sheets.google.com → File → Import). The columns are:")
b.table(["A", "B", "C", "D", "E", "F"], [
    ["#", "case_id", "request", "correct intent", "system said", "right?"],
], [1.5, 2.8, 4.6, 2.8, 2.8, 2.1], font=9.5)
b.p("Pick one intent, for example **alarm_query**, and count three things. You can use a filter (Data → Filter), "
    "or type these formulas into any empty cell:")
b.table(["Count", "Meaning", "Formula", "Answer"], [
    ["TP", "correct intent is alarm_query AND right", "=COUNTIFS(D:D,\"alarm_query\",F:F,\"yes\")", "6"],
    ["FP", "system said alarm_query AND wrong", "=COUNTIFS(E:E,\"alarm_query\",F:F,\"no\")", "0"],
    ["FN", "correct intent is alarm_query AND wrong", "=COUNTIFS(D:D,\"alarm_query\",F:F,\"no\")", "1"],
], [1.4, 5.4, 7.0, 2.8], font=9)
b.p("Then: precision = TP / (TP + FP) = 6/6 = 1.000; recall = TP / (TP + FN) = 6/7 = 0.857; "
    "F1 = 2 × precision × recall / (precision + recall) = 0.923. Repeat for the other 11 intents (only the name in "
    "the formula changes), add the 12 F1 values and divide by 12. You get 0.974, the recorded score.")
b.callout("**A refused request** (\"REFUSED (off-topic)\" in column E) counts as wrong for its correct intent (an FN), "
          "but as an FP for no intent, because the system did not claim any intent. The scorer and scikit-learn "
          "both treat it this way.")

b.h("Option 3: a small practice example on paper", 3)
b.p("**This table is made up for practice. It is not from the project.** It has only 8 requests, so the whole "
    "calculation fits on paper. Once you can do this, you can do the real one above.")
b.table(["#", "Correct intent", "System said", "Right?"], [
    ["1", "alarm_set", "alarm_set", "yes"], ["2", "alarm_set", "alarm_set", "yes"],
    ["3", "alarm_set", "alarm_remove", "no"], ["4", "alarm_remove", "alarm_remove", "yes"],
    ["5", "alarm_remove", "alarm_set", "no"], ["6", "lights_off", "lights_off", "yes"],
    ["7", "lights_off", "lights_off", "yes"], ["8", "lights_off", "alarm_set", "no"],
], [1.0, 5.0, 5.0, 5.6], font=10)
b.p("**Step 1.** For each intent, count TP, FP and FN, exactly as in Option 2:")
b.table(["Intent", "TP", "FP", "FN", "Precision", "Recall", "F1"], [
    ["alarm_set", "2 (#1, #2)", "2 (#5, #8)", "1 (#3)", "2/4 = 0.500", "2/3 = 0.667", "0.571"],
    ["alarm_remove", "1 (#4)", "1 (#3)", "1 (#5)", "1/2 = 0.500", "1/2 = 0.500", "0.500"],
    ["lights_off", "2 (#6, #7)", "0", "1 (#8)", "2/2 = 1.000", "2/3 = 0.667", "0.800"],
], [2.6, 1.9, 1.9, 1.5, 3.1, 3.0, 2.6], font=9)
b.p("**Step 2.** F1 for alarm_set = 2 × 0.500 × 0.667 / (0.500 + 0.667) = 0.667 / 1.167 = 0.571.")
b.p("**Step 3.** Macro-F1 = (0.571 + 0.500 + 0.800) / 3 = **0.624**. Accuracy = 5 right / 8 = **0.625**.")
b.p("**Step 4.** Check with scikit-learn: save this as `check_f1.py` in the project folder and run "
    "`python check_f1.py`. It prints 0.624 and 0.625.")
b.code(
    "from sklearn.metrics import f1_score, accuracy_score\n\n"
    "gold = ['alarm_set', 'alarm_set', 'alarm_set', 'alarm_remove', 'alarm_remove',\n"
    "        'lights_off', 'lights_off', 'lights_off']\n"
    "pred = ['alarm_set', 'alarm_set', 'alarm_remove', 'alarm_remove', 'alarm_set',\n"
    "        'lights_off', 'lights_off', 'alarm_set']\n\n"
    "print('macro F1', round(f1_score(gold, pred, average='macro'), 3))\n"
    "print('accuracy', accuracy_score(gold, pred))"
)
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
b.p("Each experiment has the same seven parts: **in one sentence**, **where its files are**, **how it works**, "
    "**run it**, **what the output means**, **check it yourself** and **what to say**. All paths are inside "
    "`D:\\MyClaudeProject\\nlp`. Before running anything: open the Ollama app, open PowerShell, and type "
    "`cd D:\\MyClaudeProject\\nlp`.")
b.callout("**Three tools do the \"check it yourself\" parts for you, on the real files:**\n"
          "`python scripts/explain_f1.py --run <run folder name>`: puts the correct answers and a run's answers "
          "side by side and works out its F1 (Part A5). It works for **any** run folder that has a predictions.jsonl.\n"
          "`python scripts/explain_stats.py bootstrap | timing | errors`: shows how the confidence interval, "
          "the speed figures and the error counts were worked out.\n"
          "A **run folder name** is a folder inside `runs`, such as `20261013_0110_P1_B1_0`: the date and time "
          "(13 Oct, 01:10), the project (P1), the system (B1) and the seed (0).")


def files_table(rows):
    b.table(["What", "Where"], rows, [5.2, 11.4], font=9)


def test(number, name, sentence, files, how, command, time, meaning=None, image=None, caption=None,
         check=None, say=""):
    b.h(f"C{number}. {name}", 2)
    b.p(f"**In one sentence:** {sentence}")
    b.p("**Where its files are:**")
    files_table(files)
    b.p("**How it works:**")
    b.numbered(how)
    b.p(f"**Run it** ({time}):")
    b.code(command)
    if image:
        b.image(IMG / image, caption)
    if meaning:
        b.p("**What the output means:**")
        b.bullets(meaning)
    if check:
        b.p("**Check it yourself:**")
        b.numbered(check)
    b.p(f"**Say:** \"{say}\"", size=10.5)


test(1, "The data and the splits",
     "We used real, public data and split it once, with a fixed seed, into examples, development data and locked test data.",
     [["The original dataset (downloaded)", "data\\raw\\massive-1.1.tar.gz (Amazon MASSIVE 1.1)"],
      ["Which domains each project uses", "configs\\projects.json"],
      ["The script that builds the splits", "scripts\\prepare_data.py"],
      ["Code that turns the dataset's labels into positions", "src\\evaluation\\massive.py"],
      ["Examples, development and test files", "data\\processed\\P1\\kshot.jsonl, dev.jsonl, holdout\\test.jsonl"],
      ["The record of every split", "data\\manifests\\P1.json (counts, every request ID, file fingerprints)"],
      ["The data report", "docs\\DATA_REPORT.md"],
      ["Tests for it", "tests\\test_massive.py, tests\\test_data_splits.py"]],
     ["Download MASSIVE: 16,521 English requests, each labelled by people with its intent and entities.",
      "The dataset marks entities inside the text, like `wake me at [time : five am]`. Convert each one to its "
      "exact position: \"five am\" starts at character 11 and ends at 18. All 16,521 converted with 0 errors.",
      "For each project, keep only its domains (P1: alarms and smart-home devices).",
      "Draw, using a fixed seed so the result is identical every time: 10 examples per intent (kshot.jsonl), "
      "100 development requests (80 in scope + 20 off-topic) and 300 locked test requests.",
      "Save every request ID and a fingerprint (SHA-256 hash) of every file in the manifest, then check that no "
      "request appears in two files (the leakage check)."],
     "python scripts/prepare_data.py --check", "a few seconds; it only checks, it changes nothing",
     ["`kshot: 120`: 120 examples for P1's 12 intents (10 each).",
      "`dev_total: 100`, `test_total: 300`: the development and test sizes.",
      "`leakage id-check pass`: no request is in two files.",
      "P3's test set is smaller (200) because the original dataset has fewer requests in its domains; the plan's fallback size was used and recorded."],
     "screen_data_check.png", "The data check (real output).",
     ["Open `data\\processed\\P1\\dev.jsonl` in Notepad. The status bar shows 100 lines: one request each.",
      "Find \"make a room darker\". Its entity is `\"start\": 7, \"end\": 11`. Count the characters from 0: "
      "m=0, a=1, k=2, e=3, space=4, a=5, space=6, r=7, o=8, o=9, m=10, so characters 7 to 10 spell \"room\" (the end number is one past the last letter).",
      "Open `data\\manifests\\P1.json` and search (Ctrl+F) for `\"counts\"`: the sizes match the screen above. "
      "Search for `\"sha256\"` to see each file's fingerprint."],
     "The data is the public MASSIVE dataset. Every split is drawn with a fixed seed and checked for overlap, and the test data is locked.")

test(2, "Model speed and repeatability",
     "Before any experiment, we measured whether the AI model is fast enough and gives the same answer every time.",
     [["The script", "scripts\\throughput_test.py"],
      ["The result folder", "runs\\20261012_0020_setup_throughput_0"],
      ["Summary table", "runs\\20261012_0020_setup_throughput_0\\summary.md"],
      ["Time for every request", "runs\\20261012_0020_setup_throughput_0\\timing.jsonl"]],
     ["Switch off the saved answers, so every request really goes to the model.",
      "Send 50 full-size requests and time each one with a stopwatch in the code.",
      "Send the same 50 again and compare the two sets of answers word for word.",
      "Count how many replies were valid JSON."],
     "python scripts/throughput_test.py --models qwen2.5:3b", "a few minutes: 100 live requests",
     ["median 0.42 s: half the requests took less than 0.42 seconds.",
      "identical repeat 1.00: all 50 answers were the same the second time.",
      "JSON valid 1.00: every reply was in the right format."],
     None, None,
     ["Open `runs\\20261012_0020_setup_throughput_0\\summary.md` in Notepad and read the table.",
      "Open `timing.jsonl` in the same folder: one line per request with its time in seconds (`latency_s`)."],
     "The model answers in under half a second and gives identical answers on repeat, so anyone re-running our experiments gets the same results.")

test(3, "B0: word matching, no AI",
     "The simplest possible system, as a floor that every AI system must beat.",
     [["The code", "src\\baselines\\b0_tfidf.py"],
      ["The script", "scripts\\run_b0.py"],
      ["Result folders", "runs\\20261011_1614_P1_B0_0 (the first run) and later re-runs, e.g. runs\\20261025_1518_P1_B0_0"]],
     ["Turn every example sentence into word weights (TF-IDF: a word counts more if it is common in this sentence but rare overall).",
      "Train a standard classifier (logistic regression, from scikit-learn) on P1's 120 examples.",
      "For off-topic requests: if a request is too unlike every example, refuse it. The cut-off (0.3482) was chosen on development data.",
      "Answer the 100 development requests and score them."],
     "python scripts/run_b0.py --projects P1", "a few seconds; no AI model needed",
     ["`intent macro-F1 0.780 | accuracy 0.700`: the scores.",
      "`threshold 0.3482`: the cut-off for refusing off-topic requests.",
      "`entity F1 0.000 (none extracted)`: B0 only picks an intent; it never extracts entities."],
     None, None,
     ["Work out its F1 from the real files: `python scripts/explain_f1.py --run 20261011_1614_P1_B0_0`. It ends with 0.7801 (0.780 when rounded) and \"all three are the same\".",
      "Every re-run makes a new dated folder in `runs` with exactly the same score: that shows the result repeats."],
     "A basic word-matching classifier gets 0.78 on P1; any AI system has to beat that to be worth it.")

test(4, "B1: one generic prompt",
     "What you get from one standard AI prompt with no design decisions.",
     [["The design it uses", "joint-fixed-llm, fixed in advance (B1_CONFIG_ID in src\\pipelines\\catalogue.py)"],
      ["The script", "scripts\\run_design.py"],
      ["Result folder", "runs\\20261013_0110_P1_B1_0 (predictions.jsonl, metrics.json)"]],
     ["Use one design, chosen before any results were seen.",
      "Run it on the 100 development requests, following the recipe in Part A2.",
      "Save every answer and the scores in a new run folder."],
     "python scripts/run_design.py --systems B1 --projects P1", "under a minute",
     ["`B1  joint-fixed-llm intent 0.927 entity 0.610 oos 0.870`: its intent, entity and off-topic F1."],
     None, None,
     ["`python scripts/explain_f1.py --run 20261013_0110_P1_B1_0` shows its 80 answers, 8 of them wrong, and works out 0.9268.",
      "In the CSV file it saves, filter column F for \"no\" to see exactly which 8 requests it got wrong."],
     "One generic prompt reaches 0.927; the agent has to beat this to show its design work adds anything.")

test(5, "B2: a person configuring by hand",
     "A team member configured the pipeline by hand, timed, so we can compare the agent with a person.",
     [["The worksheets", "configs\\b2\\P1_worksheet.md, configs\\b2\\P2_worksheet.md"],
      ["The script", "scripts\\run_b2.py (start, check, finish)"],
      ["Result folders", "runs\\20261024_1622_P1_B2_0, runs\\20261024_1630_P2_B2_0"],
      ["The time and help declared", "inside each result folder's config.json (\"effort\", \"ai_assistance\")"]],
     ["`run_b2.py start` created a worksheet with the project description and the 12 designs.",
      "The person chose a design, wrote a description for every intent and field, and declared any help.",
      "`run_b2.py check` scored the choices on development data; each check is added to the worksheet.",
      "`run_b2.py finish` saved the final result with the minutes and the help recorded."],
     "python scripts/run_b2.py check --project P1", "the person's own time: 38 min for P1, under 6 min for P2",
     ["`intent macro-F1 0.858 | entity F1 0.586`: the person's scores on P1."],
     None, None,
     ["Open `configs\\b2\\P1_worksheet.md`: section 2 shows the chosen design, sections 3 and 4 the descriptions, section 5 the time and help, and the bottom shows each check's score.",
      "Open `runs\\20261024_1622_P1_B2_0\\config.json` and search for `\"ai_assistance\"`.",
      "`python scripts/explain_f1.py --run 20261024_1622_P1_B2_0` works out 0.858 from its answers."],
     "By hand, a beginner got 0.858 on P1 in 38 minutes; the agent got 0.958 with no human time. On P2, a person with ChatGPT matched the agent, and we report that too.")

test(6, "B3: the published baseline (XLM-R)",
     "We compared against the model the MASSIVE paper itself used as its baseline.",
     [["The code", "src\\baselines\\b3_encoder.py"],
      ["The script", "scripts\\run_b3_local.py"],
      ["The downloaded model", "C:\\Users\\mihir\\.cache\\huggingface\\hub\\models--xlm-roberta-base (1.1 GB)"],
      ["Result folders", "runs\\20261015_2240_P1_B3-k_0 and the B3-full and P2 folders"],
      ["Summary of each run", "summary.md inside each folder"]],
     ["Download XLM-R, a language model with 270 million parameters.",
      "Fine-tune it: show it the examples again and again (30 rounds) and adjust its internal numbers until it learns them. "
      "B3-k uses the same 10 examples per intent as everyone else; B3-full uses all the training data (10-30 times more).",
      "Choose the off-topic cut-off on development data.",
      "Answer the 100 development requests and score them with the same scorer as every other system."],
     "python scripts/run_b3_local.py --projects P1 --variants B3-k",
     "about 11 minutes for P1 B3-k; about 85 minutes for all four. Don't run it live: open the result folder instead",
     ["The summary says: fine-tuned on 120 cases for 30 epochs in 664 s, intent macro-F1 0.909, entity F1 0.650."],
     None, None,
     ["Open `runs\\20261015_2240_P1_B3-k_0\\summary.md` in Notepad.",
      "`python scripts/explain_f1.py --run 20261015_2240_P1_B3-k_0` works out 0.909 from its saved answers."],
     "With the same data, our agent beats the published baseline on intents, and A2 also beats it on entities. B3-full, with 10-30 times more data, is only a reference.")

test(7, "B4: random search",
     "We checked whether the agent chooses designs better than luck.",
     [["The code", "src\\baselines\\b4_search.py"],
      ["The script", "scripts\\run_design.py"],
      ["Random-search results", "runs\\20261013_0112_P1_B4-random_seeds (config.json, metrics.json)"],
      ["All 12 designs scored", "runs\\20261013_0112_P1_B4-exhaustive_0 (config.json)"]],
     ["Pick 4 of the 12 designs at random: the same budget the agent gets.",
      "Score each on development data and keep the best, by the same rule the agent uses.",
      "Repeat with 5 different random seeds, so the result is not one lucky or unlucky draw.",
      "Also score all 12 designs: the best possible (the ceiling)."],
     "python scripts/run_design.py --systems B4-random --exhaustive --projects P1", "under a minute",
     ["For each seed, the 4 designs drawn and the one kept; then the average over the 5 seeds."],
     None, None,
     ["Open `runs\\20261013_0112_P1_B4-random_seeds\\metrics.json` and find `\"selected_intent_macro_f1\"`: "
      "the 5 winning scores, to 4 decimals, are 0.9585, 0.9511, 0.9744, 0.9511 and 0.9585.",
      "Average them on a calculator: (0.9585 + 0.9511 + 0.9744 + 0.9511 + 0.9585) / 5 = 4.7936 / 5 = 0.9587, which rounds to **0.959**, the B4 score. (Use 4 decimals: rounding first to 3 gives 0.958.)",
      "Open `config.json` in the same folder and search for `\"attempted\"` to see which 4 designs each seed drew.",
      "Open the B4-exhaustive folder's `config.json` and search for `\"ranking\"`: all 12 designs, best first (schema-sim-llm, 0.974)."],
     "Random search averaged 0.959 on P1. A1 did not beat it; the improved A2 reached the best design, 0.974.")

test(8, "A1 and A2: the agent",
     "We ran the full framework: the Analyzer, the Architect, scoring the candidates and selecting the best.",
     [["The Analyzer", "src\\analyzer\\analyzer.py"],
      ["A1's Architect", "src\\architect\\architect.py"],
      ["A2's Architect", "src\\architect\\architect_v2.py"],
      ["Puts the steps together", "src\\architect\\design_run.py"],
      ["Scripts", "scripts\\run_design.py (A1), scripts\\run_a2.py (A2)"],
      ["Result folders", "runs\\20261013_0110_P1_A1_0, runs\\20261024_1648_P1_A2_0 (config.json, events.jsonl)"],
      ["Answers of the chosen design", "runs\\20261024_1654_P1_A1-selected_0, runs\\20261024_1654_P1_A2-selected_0"]],
     ["Analyzer: ask the AI to write a one-line description of every intent and field (2 calls).",
      "Architect: ask the AI which designs to try. A1 asks it to pick 3 at once; A2 asks it to rank each design choice separately, then builds 3 designs that each change one choice.",
      "Score each of the 3 designs on the 100 development requests.",
      "Give the scores back to the Architect, which picks a 4th design.",
      "Keep the best of the 4. Save every choice, its reason and its score in the run folder."],
     "python scripts/run_a2.py", "under a minute",
     ["`ranked extraction schema_guided > two_stage > joint`: the AI's own ranking, with its reason in brackets.",
      "`tried ... [reasoned/initial]`: the 3 first designs and their scores; `[reasoned/revision]`: the 4th, chosen after seeing the scores.",
      "`selected schema-sim-llm: intent 0.974`: the design kept."],
     "screen_run_a2.png", "The A2 run (real output).",
     ["Open `runs\\20261013_0110_P1_A1_0\\config.json` and search for `\"attempts\"`: the 4 designs A1 tried, each with a `\"rationale\"` (its reason) and `\"source\": \"reasoned\"` (the AI chose it, not a fallback).",
      "Search the same file for `\"reasoned_choices\"`: 4, so all 4 choices came from the AI.",
      "`python scripts/explain_f1.py --run 20261024_1654_P1_A2-selected_0` works out A2's 0.974 (Part A5)."],
     "The agent chooses designs itself and records a reason for each choice. A2 tests the alternatives one change at a time, and it reached the best of all 12 designs on both projects.")

test(9, "Ablations",
     "We removed one part of the agent at a time to find out which part matters.",
     [["The script", "scripts\\run_dev_analysis.py"],
      ["One result folder per variant", "runs\\20261016_0100_P1_A1-noAnalyzer_0, ...-noReasoning_0, ...-noSelection_0, ...-oneCandidate_0, ...-noRepair_0"],
      ["All numbers together", "reports\\dev_analysis.json (section \"ablations\")"],
      ["The write-up", "reports\\DEV_ANALYSIS.md, section 1"]],
     ["No Analyzer: run the agent without the AI-written descriptions.",
      "No reasoning: replace the AI's choice of designs with a fixed order.",
      "No selection: take the Architect's first design without scoring any.",
      "No repair: give no second chance when the model's reply is badly formatted.",
      "Score each variant on the same 100 requests and compare it with the full agent."],
     "python scripts/run_dev_analysis.py --skip-timing", "1 to 2 minutes",
     ["One line per variant, e.g. `A1-noReasoning joint-sim-llm intent 0.886` on P2: without the AI's reasoning, P2 scored higher than with it."],
     "../../figures/fig4_ablations.png", "Each bar removes one part of A1 (chart from the reports\\figures folder).",
     ["Pick a variant and work out its score: `python scripts/explain_f1.py --run 20261016_0102_P2_A1-noReasoning_0` gives 0.886.",
      "Compare with the full agent on P2: `python scripts/explain_f1.py --run 20261024_1654_P2_A1-selected_0` gives 0.841."],
     "Scoring the candidates helps most, by 3 to 4 points. A1's reasoning did not help, which is exactly why we built A2.")

test(10, "Confidence intervals (bootstrap)",
     "We checked whether a difference between two systems is real or could be luck.",
     [["The code", "paired_bootstrap in scripts\\run_dev_analysis.py"],
      ["The results", "reports\\dev_analysis.json (section \"bootstrap\")"],
      ["The step-by-step explainer", "scripts\\explain_stats.py"]],
     ["Take the 100 development requests and both systems' answers to them.",
      "Make a \"pretend\" set of 100 by drawing request numbers at random, allowing repeats: some requests appear twice, some not at all.",
      "Score both systems on that same pretend set and note the difference.",
      "Do this 1,000 times. Sort the 1,000 differences and keep the middle 95%: that range is the confidence interval.",
      "If the range is entirely above 0, the lead is real. If it includes 0, it could be luck."],
     "python scripts/explain_stats.py bootstrap", "about 20 seconds",
     ["Step 1: on the real 100 requests A1 leads B1 by +0.032.",
      "Step 2: three of the 1,000 pretend sets. In draw 1 B1 actually wins (-0.065): that is how luck shows up.",
      "Step 3: the interval is [-0.040, +0.121]: it includes 0.",
      "It matches the number recorded in reports\\dev_analysis.json."],
     "screen_bootstrap.png", "The bootstrap, step by step (real output).",
     ["Run it for P2: `python scripts/explain_stats.py bootstrap --project P2`.",
      "Open `reports\\dev_analysis.json` and search for `\"ci_low\"` to see every recorded interval."],
     "With 100 development requests, A1's lead over B1 could still be luck, so we don't call it significant yet. The 300-request test sets will tell.")

test(11, "Real speed (timing)",
     "We measured how fast the final pipeline answers when nothing is saved in advance.",
     [["The code", "time_requests in src\\evaluation\\runner.py"],
      ["Time for every request", "runs\\20261016_0101_P1_A1-timing_0\\timing.jsonl"],
      ["The step-by-step explainer", "scripts\\explain_stats.py"]],
     ["Switch off the saved answers so every request goes to the model live.",
      "Send 5 warm-up requests and ignore them: the first one wakes the model up and is slow.",
      "Send 50 development requests and time each one with a stopwatch in the code.",
      "Leave out requests refused before reaching the model, so they cannot make a design look faster.",
      "Sort the 50 times. The median is the middle one; p95 is the one that 95% are faster than."],
     "python scripts/explain_stats.py timing", "a second (it reads the saved times)",
     ["The 50 times sorted, numbered 1 to 50.",
      "Median = number 26 = 0.77 s. p95 = number 48 = 0.95 s.",
      "Both match what is recorded in reports\\dev_analysis.json."],
     "screen_timing.png", "How the speed figures are worked out (real output).",
     ["Open `runs\\20261016_0101_P1_A1-timing_0\\timing.jsonl` in Notepad: each line has a request and its `latency_s` (seconds). The first 5 say `\"warmup\": true`.",
      "To measure again from scratch (about 5 minutes): `python scripts/run_dev_analysis.py`."],
     "Every pipeline answers in under one second, even in the slowest 5% of requests.")

test(12, "Error analysis",
     "We looked at what kind of mistakes the agent makes, not just how many.",
     [["The code", "classify_errors in scripts\\run_dev_analysis.py"],
      ["The results", "reports\\dev_analysis.json (section \"errors\")"],
      ["The explainer", "scripts\\explain_stats.py"]],
     ["Go through every development request the agent got wrong.",
      "Put each mistake in one category: confused intent, wrongly refused, answered an off-topic request, missed entity, "
      "extra (spurious) entity, wrong entity type, wrong boundary (too much or too little text), or a value not in the request.",
      "Count each category, and keep real examples of each."],
     "python scripts/explain_stats.py errors", "a second",
     ["`spurious entity: 22`, e.g. \"turn the lights off please -> house_place='lights'\": the agent extracted \"lights\" as a place, which it is not.",
      "`missed entity: 15`, e.g. \"make a room darker\": the room was not extracted.",
      "`incorrect out-of-scope rejection: 4`, e.g. \"i need some more lights\" was refused as off-topic."],
     "screen_errors.png", "A1's mistakes by category, with real examples (real output).",
     ["Run it for P2: `python scripts/explain_stats.py errors --project P2`.",
      "Check one example against the data: find \"make a room darker\" in `data\\processed\\P1\\dev.jsonl`; the correct entity is house_place = room."],
     "Most of the original agent's mistakes were extra words extracted as entities, which showed us where it was weakest.")

test(13, "Robustness to messy typing",
     "We checked whether the systems still work when people type carelessly.",
     [["The script", "scripts\\run_robustness.py"],
      ["Result folders", "runs\\20261016_0119_P1_A1-robust-typo_0, ...-robust-caps_0, ...-robust-filler_0 (and the same for B1 and B0)"],
      ["All numbers together", "reports\\robustness.json"],
      ["The write-up", "reports\\DEV_ANALYSIS.md, section 5"]],
     ["Rewrite every development request three ways, the same way every time (fixed seed):",
      "typos: two neighbouring letters swapped (\"tunr the lights off please\");",
      "capitals: \"TURN THE LIGHTS OFF PLEASE\";",
      "filler words: \"hey, could you please turn the lights off please, thanks\".",
      "Score B0, B1 and the agent on each rewritten set, with the same correct answers as before."],
     "python scripts/run_robustness.py", "about a minute (answers saved earlier)",
     ["One line per system and version, e.g. `A1 typo intent 0.949`: with typos A1 dropped only from 0.958 to 0.949."],
     None, None,
     ["`python scripts/explain_f1.py --run 20261016_0119_P1_A1-robust-typo_0` shows the requests with their typos (\"tunr the lights off please\") next to A1's answers, and works out 0.949.",
      "Open that folder's `predictions.jsonl`: each line has the rewritten request in `\"utt\"`."],
     "The AI systems lose at most about 7 points on messy input, while word matching drops by up to 27.")

test(14, "Export and live demo",
     "We saved the chosen pipeline as a package and showed another program can load and use it.",
     [["The code", "src\\runtime\\package.py"],
      ["Scripts", "scripts\\export_pipeline.py, scripts\\demo.py"],
      ["The P1 package", "artifacts\\P1\\twostage-sim-llm-ff3d548a0af2\\ (pipeline.json, examples.jsonl, manifest.json)"],
      ["Tests for it", "tests\\test_runtime.py"]],
     ["Save the chosen design, the Analyzer's descriptions, the examples and the model's fingerprint into three files.",
      "Write a fingerprint of each file into manifest.json. If a file is changed later, the fingerprints no longer match and the package refuses to load.",
      "Load the package in a fresh program and answer normal, off-topic and invalid requests.",
      "These packages hold A1's choices; A2's will be exported at the freeze."],
     "python scripts/demo.py --project P1\npython scripts/demo.py --project P1 --interactive",
     "about 10 seconds each",
     ["`-> ok intent=alarm_set time='six thirty'`: understood, with the details extracted.",
      "`-> out_of_scope`: refused, correctly.",
      "`-> invalid_request`: an empty or too-long request, refused before the AI is even called."],
     "screen_demo.png", "The demo (real output).",
     ["Open `artifacts\\P1\\twostage-sim-llm-ff3d548a0af2\\manifest.json`: `\"files\"` lists each file's fingerprint.",
      "See the tamper protection work: `python -m pytest tests/test_runtime.py -vv -k modified`. The test edits a package file and checks it is refused (2 passed).",
      "In interactive mode, type your own requests, e.g. \"dim the kitchen lights\", then press Enter on an empty line to stop."],
     "The agent's choice is saved as a package any program can load, and if anyone edits it, it refuses to load.")

test(15, "Checking the results themselves",
     "We proved that no recorded number was edited or computed wrongly.",
     [["Re-score every run", "scripts\\reproduce_metrics.py"],
      ["Independent check with scikit-learn", "scripts\\verify_with_sklearn.py"],
      ["Every check at once", "scripts\\show_evidence.py (saves reports\\EVIDENCE_SUMMARY.md)"]],
     ["For every run folder with a predictions.jsonl, recompute its scores from the saved answers and compare with its metrics.json.",
      "Separately, recompute F1, accuracy and the off-topic scores with scikit-learn, without our scorer.",
      "Compare to 9 decimal places."],
     "python scripts/reproduce_metrics.py\npython scripts/verify_with_sklearn.py\npython scripts/show_evidence.py",
     "under a minute in total",
     ["`match` / `agrees` on every line: the recorded number is exactly what recomputation gives.",
      "`not checkable`: that folder has no answers to re-score (for example a timing run). It is not a failure."],
     "screen_sklearn.png", "The independent check (real output).",
     ["Part A5's explain_f1 does the same three-way check for one run, showing every step: our scorer, scikit-learn and the hand calculation all give 0.9744.",
      "Run `python scripts/show_evidence.py` and find \"Overall: all checks passed\" on the last line."],
     "Every recorded number can be recomputed from the raw answers, and the standard library scikit-learn gets the same numbers.")
b.page_break()

# =========================================================================
b.h("Part D. If the teacher says \"do it now\"")
b.table(["The teacher asks…", "Type this", "Time", "What appears"], [
    ["\"Show me a test running.\"", "python scripts/walkthrough.py", "5 s", "the six steps for three requests"],
    ["\"Is the difference real?\"", "python scripts/explain_stats.py bootstrap", "20 s", "the confidence interval, worked out step by step"],
    ["\"How did you measure speed?\"", "python scripts/explain_stats.py timing", "1 s", "50 times sorted, median and p95 picked out"],
    ["\"Run all your tests.\"", "python -m pytest tests", "15 s", "371 passed"],
    ["\"How do you compute F1?\"", "python scripts/explain_f1.py (Part A5)", "5 s", "every count and the average, matching metrics.json"],
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
    "Open `data\processed\P1\dev.jsonl` and a `predictions.jsonl` in Notepad and explain one line of each (Part A3).",
    "Run `python scripts/walkthrough.py` and explain each of the six steps out loud (Part A4).",
    "Run `python scripts/explain_f1.py`, then count alarm_query yourself in the CSV file (Part A5).",
    "Work out the practice example on paper without looking, then check it with `check_f1.py`.",
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
