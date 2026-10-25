"""Build "Presentation Script": a step-by-step demo for the teacher, with lines to say.

Every command was run during the project and its output is shown in the other
guides. Usage (from the project root):
    python reports/guide/make_demo_script_docx.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from docx_helpers import Builder  # noqa: E402

IMG = HERE / "images"
FIG = HERE.parents[0] / "figures"
OUT = HERE / "Presentation_Script.docx"

b = Builder()
b.title(
    "Presentation Script",
    "What to show, what to type and what to say, step by step",
    ["Mihir Bhati (24BCE5341)  ·  Ahana Sharan (24BCE5334)", "About 20 minutes, plus questions"],
)
b.callout("**How to use this script.** Each step has: **show** (what is on screen), **type** (the command, if any), "
          "**say** (lines you can speak; use your own words once you know them) and **if asked** (a likely question). "
          "Steps marked *optional* can be skipped if time is short. Rehearse the whole thing once before the real demo.")

# ---------------------------------------------------------------------------
b.h("Before the demo (10 minutes earlier)")
b.checklist([
    "Laptop plugged in; Wi-Fi not needed (everything runs offline).",
    "Open the **Ollama** app from the Start menu (it runs the AI model).",
    "Open **PowerShell** and type `cd D:\\MyClaudeProject\\nlp`.",
    "Type `ollama list` and check `qwen2.5:3b` is listed.",
    "Run `python scripts/demo.py --project P1` once, so the model is warmed up (the first answer is slow).",
    "Open in File Explorer: `reports\\figures` (the charts) and `reports\\guide` (the documents).",
    "Keep **How Our System Works.pdf** open in a second window as your backup notes.",
])
b.callout("**If any command fails during the demo**, it is almost always because Ollama is closed. Open it, wait "
          "10 seconds and run the command again. Say: \"The AI model runs locally in Ollama; let me start it.\"",
          fill="FEF9C3")

b.h("The flow at a glance", 2)
b.table(["#", "Step", "Time", "What it proves"], [
    ["1", "The problem and the idea", "2 min", "you understand what you built"],
    ["2", "How the system works", "3 min", "the agent, the 12 designs, qwen's role"],
    ["3", "Live demo of the finished pipeline", "2 min", "it works"],
    ["4", "One test, step by step (walkthrough)", "3 min", "how every test is done"],
    ["5", "The agent choosing a design", "2 min", "the agentic part"],
    ["6", "The results and the comparisons", "4 min", "it is better, and where it is not"],
    ["7", "Proof the numbers are real", "2 min", "results can be checked independently"],
    ["8", "Built it yourself (optional)", "2 min", "you understand it well enough to rebuild it"],
    ["9", "Honest limits and next step", "1 min", "maturity and honesty"],
    ["10", "Close, then questions", "1 min", ""],
], [0.8, 6.6, 1.8, 7.4], font=9.5)
b.page_break()

# ---------------------------------------------------------------------------
def step(n, title, show, say, type_=None, asked=None, note=None, image=None, caption=None):
    b.h(f"Step {n}. {title}")
    b.p(f"**Show:** {show}")
    if image:
        b.image(image, caption)
    if type_:
        b.p("**Type:**")
        b.code(type_)
    b.p("**Say:**")
    b.callout("\n".join(f"\"{line}\"" for line in say))
    if note:
        b.p(f"**Point at:** {note}")
    if asked:
        b.p("**If asked:**")
        b.table(["Question", "Answer"], asked, [5.6, 11.0], font=9.5)


step(1, "The problem and the idea (2 min)",
     "the first page of How Our System Works.pdf, or just talk.",
     ["Every app that understands users, like a home assistant or a hospital bot, needs an NLP pipeline. It turns a "
      "sentence like 'turn off the bedroom lights' into something a program can act on: the intent, lights off, and "
      "the detail, bedroom.",
      "There are two ways to build that. You can train a model on examples, like XLM-R, the model the MASSIVE dataset "
      "paper used. Or you can give a ready-made AI, like qwen, a well-written prompt.",
      "Writing that prompt well takes trial and error for every new app. Our framework automates it: from a "
      "description of the app, an AI agent designs the pipeline, tests it and delivers the best one."],
     asked=[["What is an intent?", "What the user wants to do. 'Turn off the lights' has the intent iot_hue_lightoff."],
            ["What is NLP?", "Natural language processing: getting computers to work with human language."]])

step(2, "How the system works (3 min)",
     "the diagram below (also in How Our System Works, section 9).",
     ["You give the framework a description of the app, its list of intents and about 10 example sentences per intent.",
      "First the Analyzer: the AI writes a short description of every intent.",
      "Then the Architect: there are 12 ways to write the prompt, which we call designs. The AI picks 3 it thinks will "
      "work, our program tests each on 100 practice sentences, the AI sees the scores and picks a 4th.",
      "The best of the 4 is kept and saved as a package any app can load.",
      "Important: qwen itself never changes. We are not training it. We only choose the best way to ask it."],
     image=IMG / "how_it_works.png", caption="The framework's steps. Blue = where the AI decides.",
     asked=[["Is this training?", "No. Training changes the model, like XLM-R. Here the model stays the same; we only choose the best prompt."],
            ["Who makes the pipeline, qwen?", "No. Our Python program builds and tests it. qwen gives advice on which designs to try, and later answers each request."],
            ["What are the 12 designs?", "3 ways to ask × 2 ways to choose examples × 2 ways to refuse off-topic requests."]])

step(3, "Live demo of the finished pipeline (2 min)",
     "PowerShell.",
     ["This is the pipeline our agent chose for the home-assistant project, loaded fresh as a saved package.",
      "It handles normal requests, refuses off-topic ones, and rejects invalid input before even calling the AI."],
     type_="python scripts/demo.py --project P1",
     note="'-> ok intent=alarm_set time=six thirty' (understood, with the detail extracted); '-> out_of_scope' "
          "(correctly refused); '-> invalid_request' (empty input refused).",
     asked=[["Can I try my own sentence?", "Yes: run python scripts/demo.py --project P1 --interactive and let the teacher type. Press Enter on an empty line to stop."],
            ["Does it need the internet?", "No. The AI model runs locally on this laptop."]])

step(4, "One test, step by step (3 min)",
     "PowerShell.",
     ["This shows exactly how every test works, for three requests.",
      "Step 1 is the correct answer, from the dataset, labelled by people. Step 3 is the prompt we send to the AI. "
      "Step 4 is its raw reply. Step 5 is how we read and check it. Step 6 is whether it was right.",
      "A real experiment does exactly this for all 100 practice requests, saves every answer, and computes the F1 score."],
     type_="python scripts/walkthrough.py",
     asked=[["Where does the correct answer come from?", "data\\processed\\P1\\dev.jsonl: the MASSIVE dataset, labelled by people."],
            ["How is F1 computed?", "Run python scripts/explain_f1.py: it puts the correct answers and the system's answers side by side and shows every count and the formula. Ours gives 0.974, the same as the recorded result and scikit-learn."]])

step(5, "The agent choosing a design (2 min)",
     "PowerShell.",
     ["Here the agent designs the pipeline itself. First the AI ranks each design choice and gives its reasons.",
      "Our program builds 3 designs from that, tests them, shows the AI the scores, and the AI changes one thing.",
      "Notice the AI's first preferences were partly wrong, but testing caught that: the 4th design scored 0.974, the "
      "best of all 12 designs, while testing only 4."],
     type_="python scripts/run_a2.py",
     note="the 'ranked' lines (the AI's reasoning), the 'tried' lines with their scores, and 'selected schema-sim-llm: intent 0.974'.",
     asked=[["What makes it agentic?", "The AI makes design decisions, sees the results of its own choices, and revises them, with no human configuring anything."]])

step(6, "The results and the comparisons (4 min)",
     "reports\\figures\\fig1_main_comparison.png, then fig2_intent_vs_entity.png.",
     ["To prove it is better, we compared it with other ways of building the pipeline, all on the same requests, "
      "with the same AI model and the same scorer.",
      "B0 is simple word matching. B1 is one standard prompt for every app. B2 is a person doing it by hand. B3 is "
      "XLM-R trained on the same examples, the published baseline. B4 picks designs at random.",
      "Our improved agent, A2, scored 0.974 and 0.898: the best of all 12 designs on both projects. It beats the "
      "generic prompt, the person working alone, the published baseline, and random search.",
      "We also report where it was weaker: our first version, A1, did not beat random search, and that is why we built A2."],
     image=FIG / "fig1_main_comparison.png", caption="Intent scores for every system on both projects.",
     asked=[["Why compare with random search?", "To check the agent's choices are smart, not lucky. A1 was no better than random; A2 is."],
            ["What is XLM-R?", "A language model that has to be trained on examples. With only 10 examples per intent it scored 0.909; ours scored 0.974 without any training."],
            ["Are these final results?", "These are development scores. The final ones come from 300 locked test requests per project, after we freeze the settings."]])

step(7, "Proof the numbers are real (2 min)",
     "PowerShell.",
     ["Every answer the systems gave is saved, so any result can be recomputed.",
      "This script recomputes our scores with scikit-learn, the standard library, without using our own scoring code. "
      "Every run agrees, to 9 decimal places."],
     type_="python scripts/verify_with_sklearn.py",
     note="every line says 'agrees'. For everything at once: python scripts/show_evidence.py (ends with 'Overall: all checks passed').",
     asked=[["How do I know you did not edit the numbers?", "reproduce_metrics.py re-scores every run from its saved answers, and a test proves it catches a hand-edited number."],
            ["Did you tune on the test data?", "No. The code locks the test data until the freeze, and a test checks it."]])

step(8, "Built it yourself (optional, 2 min)",
     "diy\\c04_b1.py open in VS Code, then PowerShell.",
     ["To make sure we understand it, we also wrote small versions of each test from scratch.",
      "This 40-line script builds a prompt, asks the AI about every request and scores it. It gets 0.927, the same as "
      "the project's B1 baseline."],
     type_="python diy/c04_b1.py",
     asked=[["Can you change something?", "Yes: in diy\\c03_b0.py change 0.35 to 0.5 and run it again; the score changes because more requests are refused."]])

step(9, "Honest limits and next step (1 min)",
     "How Our System Works, sections 14 and 15.",
     ["The final pipeline is always one of the 12 designs, customised for the project. That keeps it safe and lets us "
      "prove whether the agent is smart.",
      "Limits: one small model, development data so far, and the human baseline is one beginner per project.",
      "Next, we plan A3: the agent will start from the best design and rewrite its own prompt from its mistakes, keeping "
      "only changes that improve the score."],
     asked=[["Why not let it design anything?", "Then generated code would run, we could not compare it fairly, and our small 3B model already makes mistakes. Prompt refinement (A3) keeps it safe and measurable."]])

step(10, "Close (1 min)",
     "nothing; look at the teacher.",
     ["To sum up: our framework automates designing an NLP pipeline for any new app. It is tested against a generic "
      "prompt, a person, random search and the published baseline, and the results can be recomputed by anyone.",
      "We used Claude Code, an AI coding assistant, to write the code and run the experiments; we planned it, checked "
      "the results, and can explain and re-run every step. That is recorded in docs\\contributions.md.",
      "Thank you. We are happy to answer questions or run anything again."])
b.page_break()

# ---------------------------------------------------------------------------
b.h("Quick answers for questions")
b.table(["If the teacher asks...", "Say", "Show"], [
    ["What did you build?", "A framework that automatically designs, tests and delivers an NLP pipeline for any new app.", "How Our System Works, section 1"],
    ["How is it different from XLM-R?", "XLM-R learns by training; our framework designs the best prompt for a model that never changes.", "section 4 diagram"],
    ["What does qwen do?", "Gives advice while designing, and answers each request once the pipeline runs.", "section 6"],
    ["What is in the prompt?", "The intent list, short descriptions, real example sentences and the request.", "section 7"],
    ["How was each test done?", "Same 100 requests, same model, same scorer; every answer saved.", "python scripts/walkthrough.py"],
    ["Show me F1 by hand.", "Correct vs system answers, counted per intent, averaged.", "python scripts/explain_f1.py"],
    ["Is the difference real?", "Not yet certain on 100 requests; the test set will tell.", "python scripts/explain_stats.py bootstrap"],
    ["How fast is it?", "Under one second per request.", "python scripts/explain_stats.py timing"],
    ["What mistakes does it make?", "Mostly extracting extra words as details.", "python scripts/explain_stats.py errors"],
    ["Run all your tests.", "371 automated tests.", "python -m pytest tests"],
    ["Is it innovative?", "It automates the whole design and is rigorously compared; A2 shows structured search matters. Next: A3 refinement.", "section 14"],
    ["Did you use AI?", "Yes, Claude Code wrote the code; we planned, checked and can explain everything. It is recorded.", "docs\\contributions.md"],
], [4.4, 7.4, 4.8], font=9)

b.h("Backup if the live demo fails", 2)
b.bullets([
    "Open the documents instead: **How_Every_Test_Was_Done_v2.pdf** shows the real output of every command.",
    "Open **reports\\EVIDENCE_SUMMARY.md**: the saved output of all checks.",
    "Charts are in **reports\\figures**; they do not need the model.",
])

b.save(OUT)
b.save_pdf(OUT.with_suffix(".pdf"))
print(f"wrote {OUT.name} and {OUT.with_suffix('.pdf').name}")
