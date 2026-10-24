"""Build the project explanation and verification guide as a Word document.

Every number in the document is taken from the run folders and reports listed
beside it (checked on 24 Oct 2026). Images come from `reports/figures/`
(drawn from run folders by `scripts/make_figures.py`) and
`reports/guide/images/` (drawn by `make_guide_images.py`; the terminal images
are real command outputs saved in `captures/`).

Usage (from the project root):
    python reports/guide/make_guide_docx.py
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIG = ROOT / "reports" / "figures"
IMG = HERE / "images"
OUT = HERE / "Project_Explained_and_Verification_Guide.docx"

BLUE = RGBColor(0x1D, 0x4E, 0xD8)
INK = RGBColor(0x1E, 0x29, 0x3B)
GREY = RGBColor(0x47, 0x55, 0x69)

doc = Document()
for section in doc.sections:
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin = section.right_margin = Cm(2.2)
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)
normal.paragraph_format.space_after = Pt(6)
for name, size in (("Heading 1", 18), ("Heading 2", 14), ("Heading 3", 12)):
    style = doc.styles[name]
    style.font.name = "Calibri"
    style.font.size = Pt(size)
    style.font.color.rgb = BLUE if name != "Heading 3" else INK

CONTENT_WIDTH = Cm(16.6)
RUN_COUNT = sum(1 for d in (ROOT / "runs").iterdir() if d.is_dir())


# -- helpers ---------------------------------------------------------------


def add_runs(paragraph, text: str, size: float | None = None, colour=None):
    """Add text with **bold** and `code` markup."""
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("`"):
            run = paragraph.add_run(part[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt((size or 11) - 1)
        else:
            run = paragraph.add_run(part)
        if size:
            run.font.size = Pt(size) if not part.startswith("`") else run.font.size
        if colour is not None:
            run.font.color.rgb = colour
    return paragraph


def p(text: str = "", size: float | None = None, colour=None, align=None):
    para = doc.add_paragraph()
    add_runs(para, text, size, colour)
    if align:
        para.alignment = align
    return para


def h(text: str, level: int = 1):
    return doc.add_heading(text, level=level)


def bullets(items, style="List Bullet"):
    for item in items:
        add_runs(doc.add_paragraph(style=style), item)


def numbered(items):
    bullets(items, style="List Number")


def shade(cell, hex_fill: str):
    props = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    props.append(shd)


def table(header, rows, widths_cm, font=9.5, bold_first_col=False):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, text in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        add_runs(cell.paragraphs[0], f"**{text}**", font)
        shade(cell, "DBEAFE")
    for row in rows:
        cells = t.add_row().cells
        for i, text in enumerate(row):
            cells[i].text = ""
            add_runs(cells[i].paragraphs[0], f"**{text}**" if (bold_first_col and i == 0) else str(text), font)
    for row in t.rows:
        for i, width in enumerate(widths_cm):
            row.cells[i].width = Cm(width)
    doc.add_paragraph()
    return t


def callout(text: str, fill="EFF6FF"):
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    cell = t.rows[0].cells[0]
    cell.text = ""
    for i, line in enumerate(text.split("\n")):
        para = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        add_runs(para, line, 10.5)
    shade(cell, fill)
    cell.width = CONTENT_WIDTH
    doc.add_paragraph()


def command(text: str):
    t = doc.add_table(rows=1, cols=1)
    cell = t.rows[0].cells[0]
    cell.text = ""
    run = cell.paragraphs[0].add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(10.5)
    run.font.color.rgb = RGBColor(0xF8, 0xFA, 0xFC)
    shade(cell, "0F172A")
    cell.width = CONTENT_WIDTH
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def image(path: Path, caption: str, width_cm: float = 16.6):
    doc.add_picture(str(path), width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = p(caption, size=9, colour=GREY, align=WD_ALIGN_PARAGRAPH.CENTER)
    cap.paragraph_format.space_after = Pt(12)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# -- title -----------------------------------------------------------------

title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run("Automatic NLP Pipeline Design with an AI Agent")
run.bold = True
run.font.size = Pt(24)
run.font.color.rgb = BLUE
p("What we built, every test we ran, and how anyone can verify the results",
  size=13, colour=INK, align=WD_ALIGN_PARAGRAPH.CENTER)
p("Mihir Bhati (24BCE5341)  ·  Ahana Sharan (24BCE5334)", size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
p("Status as of 24 October 2026  ·  Project folder: `D:\\MyClaudeProject\\nlp`", size=10, colour=GREY,
  align=WD_ALIGN_PARAGRAPH.CENTER)

callout(
    "**How to read this document**\n"
    "Section 1 explains the project in plain words. Section 2 explains every technical term. "
    "Sections 3 and 4 describe what we built and what we compared it against. Section 5 lists every test "
    "with its result and where the proof is. Section 6 explains why the results can be trusted. "
    "Section 7 is a step-by-step guide to checking everything yourself, with what your screen should show. "
    "Section 8 answers questions a teacher is likely to ask."
)

h("Contents", 2)
numbered([
    "The project in one page",
    "Key terms explained simply",
    "What we built",
    "What we compared it against",
    "Every test we ran, and the results",
    "Why the results can be trusted",
    "How to verify everything yourself, step by step",
    "Questions a teacher may ask, with answers",
    "Honest limitations",
    "Where everything is",
])
page_break()

# -- 1 ---------------------------------------------------------------------

h("1. The project in one page")
p("**The problem.** Every app that understands what users type or say, such as a home assistant or a booking "
  "bot, needs a language-understanding pipeline. A developer must decide how to ask the AI model, which "
  "examples to show it, and how to reject requests the app cannot handle. Today that takes hours of trial "
  "and error for every new project.")
p("**Our solution.** A framework that makes those decisions automatically. You give it a written description "
  "of the app and its list of request types; an AI agent analyses the project, decides which pipeline designs "
  "to test, tests them on real data, picks the best and exports it as a package any program can use.")
image(IMG / "how_it_works.png", "Figure 1. How the framework works. Blue boxes are the steps where the AI agent makes decisions.")
p("**Why it is called agentic:** the AI does not just answer questions. It makes design decisions, looks at "
  "the results of its own choices, and revises them, with no human configuring anything.")
p("**The main result (development data, intent macro-F1, higher is better):**")
table(["System", "P1 Home assistant", "P2 Productivity assistant"], [
    ["B1 one generic prompt", "0.927", "0.804"],
    ["B2 a person configuring by hand", "0.858", "0.861 (with ChatGPT's help)"],
    ["B3-k published model (XLM-R), same data", "0.909", "0.833"],
    ["B4 random search, same budget (average of 5)", "0.959", "0.878"],
    ["A1 our original agent", "0.958", "0.841"],
    ["**A2 our improved agent**", "**0.974**", "**0.898**"],
    ["Best of all 12 designs (the ceiling)", "0.974", "0.898"],
], [8.6, 3.8, 4.2])
p("In plain words: the improved agent found the best possible design on both projects and beat every "
  "comparison system on these development scores. The original agent did not beat random search, and we "
  "report that too. These are development scores; the final, reportable numbers come from locked test data "
  "after the freeze (Section 9).", size=10.5)
page_break()

# -- 2 ---------------------------------------------------------------------

h("2. Key terms explained simply")
p("You already know accuracy and F1. Here is every term this project uses, with an example.")
table(["Term", "What it means", "Example"], [
    ["Intent", "What the user wants to do. Every request has exactly one.", "\"wake me at 7\" → alarm_set"],
    ["Entity (field)", "A detail inside the request that the system must pull out.", "\"7\" is the time"],
    ["Out-of-scope (OOS)", "A request the app cannot handle. It must be refused, not forced into a wrong action.",
     "\"who won the match?\" to a home assistant"],
    ["Accuracy", "Share of requests whose intent was right.", "75 of 80 right = 0.9375"],
    ["Precision", "Of the answers the system gave for a label, how many were right.", "said alarm_set 10 times, 9 right = 0.9"],
    ["Recall", "Of the requests that truly had a label, how many the system found.", "12 real alarm_set, found 9 = 0.75"],
    ["F1", "One number combining precision and recall (their harmonic mean). Punishes a system that is good at one and bad at the other.",
     "precision 0.9, recall 0.75 → F1 0.818"],
    ["Macro-F1", "F1 worked out for each intent separately, then averaged. Every intent counts equally, so rare intents matter.",
     "12 intents → average of 12 F1 scores"],
    ["Entity span F1", "F1 for details: a detail counts as right only if its type AND its exact position in the sentence are right.",
     "\"seven am\" as time, characters 17-25"],
    ["Development (dev) data", "Data we were allowed to look at while building and choosing designs.", "100 requests per project"],
    ["Test data", "Data locked away and used only once at the end, so the final score is honest.", "300 requests per project"],
    ["Baseline", "A simpler system we compare against, to show our system is actually better.", "B0 to B4"],
    ["Ablation", "Removing one part of the system to see how much that part contributes.", "the agent without its Analyzer"],
    ["Confidence interval", "A range showing how much a score could change by chance. If it includes 0, a difference may be luck.",
     "+0.032 [-0.040, +0.121]"],
    ["Robustness", "Whether the system still works on messy input.", "typos, CAPITALS, filler words"],
    ["Reproduction", "Recomputing a result from saved raw data to check it was not changed.", "44 of 44 runs match"],
    ["LLM / model", "Large language model: the AI that reads and writes text. Ours is qwen2.5:3b, run locally.", "3 billion parameters"],
    ["Prompt / few-shot", "The text sent to the model; few-shot means it includes a few worked examples.", "10 examples per intent"],
    ["Fine-tuning", "Training a model's internal numbers on your data. B3 does this; our agent does not.", "XLM-R trained on examples"],
    ["Seed", "A fixed starting number for anything random, so the same split or draw happens every time.", "seed 20261016"],
], [3.3, 8.3, 5.0], font=9)
page_break()

# -- 3 ---------------------------------------------------------------------

h("3. What we built")
h("3.1 The parts of the framework", 2)
table(["Part", "What it does", "Code"], [
    ["LLM client", "Talks to the local AI model; saves every answer so it is never paid for twice; counts every call", "src/llm/client.py"],
    ["Data preparation", "Downloads MASSIVE, builds the three projects, fixes the splits with a seed", "scripts/prepare_data.py"],
    ["Scorer", "One scoring code for every system, so no system gets friendlier rules", "src/evaluation/scorer.py"],
    ["Catalogue", "The 12 pipeline designs and the code that runs them", "src/pipelines/catalogue.py"],
    ["Analyzer", "AI writes a description of each intent and field; checks the project for contradictions", "src/analyzer/analyzer.py"],
    ["Architect (A1)", "AI picks 3 designs, sees their scores, picks a 4th", "src/architect/architect.py"],
    ["Architect (A2)", "Improved: AI ranks each design choice separately; the search tests alternatives one change at a time", "src/architect/architect_v2.py"],
    ["Selector", "Picks the best tested design by a fixed rule shared with random search", "src/evaluation/selection.py"],
    ["Export and runtime", "Saves the chosen pipeline as a hash-protected package and answers live requests", "src/runtime/package.py"],
    ["Test-data lock", "Code that refuses to hand out test data before the freeze", "src/analyzer/access.py"],
], [3.2, 9.3, 4.1], font=9)
h("3.2 The 12 pipeline designs", 2)
p("Every design combines three choices. The agent's job is to pick which combinations to test.")
table(["Choice", "Options", "Trade-off"], [
    ["How the AI extracts", "joint (one call) · twostage (intent first, then details) · schema (one call that includes written descriptions)",
     "twostage costs two calls; schema is the only one that uses the descriptions"],
    ["Which examples it sees", "fixed (always the same) · sim (most similar to the request)", "similar examples help with unusual wording"],
    ["How it rejects off-topic requests", "llm (the AI may answer none_of_the_above) · tfidf (a word-similarity cut-off before the AI)",
     "tfidf saves calls but is crude"],
], [3.6, 7.0, 6.0], font=9.5)
p("3 × 2 × 2 = 12 designs, named like `schema-sim-llm`.", size=10.5)
h("3.3 The data", 2)
p("**MASSIVE** (Amazon, ACL 2023): 16,521 real English requests, 18 domains, 60 intents, 55 field types, "
  "free under the CC BY 4.0 licence. We built three projects from it:")
table(["Project", "App", "Domains", "Role"], [
    ["P1", "Home assistant", "alarms, smart lights and devices", "development"],
    ["P2", "Productivity assistant", "calendar, email, lists", "development"],
    ["P3", "Ordering and travel", "takeaway, transport", "held out, never seen until the end"],
], [2.0, 4.0, 6.0, 4.6])
p("All 16,521 entity annotations were converted to exact character positions with **0 mismatches** "
  "(checked by `tests/test_massive.py`).", size=10.5)
page_break()

# -- 4 ---------------------------------------------------------------------

h("4. What we compared it against")
p("A demo shows that something runs. Comparisons show whether it is better. Each baseline answers one question:")
table(["System", "What it is", "Question it answers"], [
    ["B0", "Word-matching classifier, no AI model", "Does an AI model help at all?"],
    ["B1", "One generic AI prompt, no design choices", "Does project-specific design beat a generic setup?"],
    ["B2", "A team member configures the pipeline by hand, timed", "Does the agent match a person, for less effort?"],
    ["B3-k", "XLM-R fine-tuned on the same 10 examples per intent (the MASSIVE paper's baseline)", "How does it compare with published work?"],
    ["B3-full", "XLM-R trained on all training data (10-30× more)", "An upper reference, not a fair comparison"],
    ["B4", "Random search: 4 of the 12 designs drawn at random, 5 different seeds", "Does the agent choose better than luck?"],
    ["A1", "Our original agent", ""],
    ["A2", "Our improved agent (better search, same model)", ""],
], [2.2, 8.0, 6.4], font=9.5, bold_first_col=True)
image(IMG / "fair_comparison.png", "Figure 2. Every system shares the data, the AI model and the scorer, so differences come only from the design method.")
page_break()

# -- 5 ---------------------------------------------------------------------

h("5. Every test we ran, and the results")
p("Each row is a separate test. \"Proof\" is the file or command that shows it.")
table(["#", "Test", "Question it answers", "How it was done", "Result", "Proof"], [
    ["1", "Automated tests", "Does every part work as designed?", "371 small programs check the code, including hand-calculated scores", "371 passed", "python -m pytest tests"],
    ["2", "Data conversion check", "Are the gold answers correct?", "Every annotation converted and re-checked against the sentence", "16,521 / 16,521, 0 errors", "docs/DATA_REPORT.md"],
    ["3", "Speed and repeatability of the model", "Is the model fast and does it give the same answer twice?", "50 full-size requests, run twice, saved answers switched off", "0.42 s median; 50 / 50 identical", "runs/20261012_0020_setup_throughput_0"],
    ["4", "All 12 designs run", "Does every design work on real data?", "Each design run on real P1 and P2 requests", "12 / 12 ran; 2 bugs found and fixed", "docs/EVIDENCE_LOG.md (S04)"],
    ["5", "Main comparison", "Which system is best?", "Every system scored on the same 100 dev requests per project", "A2 best: 0.974 / 0.898", "docs/FINDINGS.md"],
    ["6", "Random search (B4)", "Does the agent beat luck?", "5 random draws of 4 designs, same scorer", "A1 no; A2 yes", "FINDINGS F1, F8"],
    ["7", "Published baseline (B3)", "How does it compare with published work?", "XLM-R fine-tuned locally on the same data", "Agent wins intent; A2 also wins entities", "FINDINGS F4"],
    ["8", "Human baseline (B2)", "Is the agent as good as a person?", "Team member configured each project by hand, timed, help declared", "P1: agent +10 points; P2: tie with ChatGPT-assisted human", "FINDINGS F7"],
    ["9", "Ablations", "Which part of the agent matters?", "Each part removed in turn and re-scored", "Scored selection matters most", "reports/DEV_ANALYSIS.md §1"],
    ["10", "Confidence intervals", "Are the differences real or luck?", "1,000 paired bootstrap resamples", "Not significant at 100 cases yet", "DEV_ANALYSIS §2"],
    ["11", "Real speed", "How fast is the final pipeline?", "50 live requests with saved answers off", "under 1 s at p95", "DEV_ANALYSIS §3"],
    ["12", "Error analysis", "What mistakes does it make?", "Every dev error put in one of 9 categories", "mostly entity over-extraction", "DEV_ANALYSIS §4"],
    ["13", "Robustness", "Does it cope with messy typing?", "Requests rewritten with typos, capitals, filler words", "AI systems hold up; word matching drops up to 27 points", "DEV_ANALYSIS §5"],
    ["14", "Export and demo", "Can the chosen pipeline be reused?", "Saved package loaded by a fresh program; tampered package refused", "works; normal, off-topic and invalid requests handled", "python scripts/demo.py"],
    ["15", "Reproduction check", "Was any number changed by hand?", "Every result re-scored from its saved predictions", "44 / 44 match", "python scripts/reproduce_metrics.py"],
    ["16", "Independent check", "Is our F1 calculated the standard way?", "scikit-learn recomputes F1, accuracy and OOS scores", "44 / 44 agree", "python scripts/verify_with_sklearn.py"],
    ["17", "Improved agent (A2)", "Can the agent's weak search be fixed?", "New search design, same model, keep-or-drop rule fixed in advance", "reached the best design on both projects", "FINDINGS F8"],
], [0.6, 2.5, 3.2, 4.2, 3.2, 2.9], font=8)

h("5.1 Full results (development data)", 2)
table(["System", "P1 intent", "P1 entity", "P1 OOS", "P2 intent", "P2 entity", "P2 OOS"], [
    ["B0 word matching", "0.780", "0.000", "0.510", "0.730", "0.000", "0.510"],
    ["B1 generic prompt", "0.927", "0.610", "0.870", "0.804", "0.451", "0.691"],
    ["B2 manual (P2: with ChatGPT)", "0.858", "0.586", "0.588", "0.861", "0.394", "0.783"],
    ["B3-k published, matched", "0.909", "0.650", "0.739", "0.833", "0.448", "0.605"],
    ["B3-full, all data (reference)", "0.936", "0.768", "0.579", "0.923", "0.797", "0.432"],
    ["A1 original agent", "0.958", "0.597", "0.909", "0.841", "0.365", "0.735"],
    ["**A2 improved agent**", "**0.974**", "**0.707**", "**0.909**", "**0.898**", "**0.483**", "**0.776**"],
], [5.0, 1.9, 1.9, 1.9, 1.9, 1.9, 2.1], font=9)
p("B0 extracts no entities by design, so its entity score is 0. B3-full trains on far more data and is shown "
  "only as a reference.", size=10)
image(FIG / "fig1_main_comparison.png", "Figure 3. Intent macro-F1 for every system. The dashed line is the best of all 12 designs.")
image(FIG / "fig2_intent_vs_entity.png", "Figure 4. Intent and entity scores side by side.")
image(FIG / "fig4_ablations.png", "Figure 5. Ablations: each bar removes one part of the original agent (A1).")
image(FIG / "fig6_robustness.png", "Figure 6. Robustness to messy requests.")
page_break()

# -- 6 ---------------------------------------------------------------------

h("6. Why the results can be trusted")
callout("**About verification websites.** There is no website that certifies machine-learning results. "
        "In research, proof means that **anyone can re-run the work and get the same numbers**. That is the "
        "standard every published paper is judged by, and this project is built for it. Uploading the project "
        "to GitHub would add a public, dated copy, but the real proof is the re-running described in Section 7.",
        fill="FEF9C3")
p("Ten reasons a sceptical reader can believe the numbers:")
numbered([
    "**Public data.** MASSIVE is a published Amazon dataset anyone can download. Its file fingerprint (SHA-256) is recorded, so anyone can check they have the same file.",
    "**Fixed splits.** Every split is drawn with a fixed seed, so it comes out identical every time.",
    "**Every answer is saved.** Each run folder keeps every individual prediction (`predictions.jsonl`), not just the final score.",
    "**Every result is recomputed.** `reproduce_metrics.py` re-scores all 44 checkable runs from their saved predictions: 44 of 44 match exactly.",
    "**An independent library agrees.** scikit-learn, the standard machine-learning library used worldwide, recomputes F1, accuracy and OOS scores without our code: 44 of 44 agree to 9 decimal places.",
    "**The scorer is tested against hand calculations.** Every expected number in `tests/test_scorer.py` was worked out by hand.",
    "**Every run records its exact setup.** `manifest.json` stores the code version (git commit), the AI model's fingerprint and the data fingerprints.",
    "**The model is repeatable.** Asked the same 50 questions twice, it gave 50 identical answers, so a re-run gives the same results.",
    "**The test data is locked by code.** The program refuses to hand out test data before the freeze; a test checks this.",
    "**Bad results are reported, not hidden.** The original agent losing to random search, the ChatGPT-assisted human tying the agent on P2 and every bug found are all in `docs/FINDINGS.md`. A record that only showed wins would be less believable.",
])
image(IMG / "verification.png", "Figure 7. How each result is checked three ways.")
page_break()

# -- 7 ---------------------------------------------------------------------

h("7. How to verify everything yourself, step by step")
p("Each step gives the command to type, what it does, and what your screen should show. All of it works offline. "
  "The screen images were made from the actual output of each command, run on 24 October 2026; "
  "small details such as timings will differ slightly on a re-run.")

h("Step 0. Get ready (2 minutes)", 2)
numbered([
    "Open a terminal: press Start, type **PowerShell**, press Enter.",
    "Start the AI model: open the **Ollama** app from the Start menu (or type `ollama serve` in a second terminal).",
    "Go to the project folder:",
])
command("cd D:\\MyClaudeProject\\nlp")
p("Check the model is there; you should see `qwen2.5:3b` in the list:")
command("ollama list")

h("Step 1. Run every check at once", 2)
command("python scripts/show_evidence.py")
p("This runs the tests, the reproduction check, the scikit-learn check and the demo, then prints a summary "
  "and saves it to `reports\\EVIDENCE_SUMMARY.md`. The last line should read **Overall: all checks passed**.")
image(IMG / "screen_summary.png", "What the summary lines look like.")

h("Step 2. The automated tests", 2)
command("python -m pytest tests")
p("Runs all 371 tests in about 15 seconds. Each dot is one passed test. The last line should be **371 passed**.")
image(IMG / "screen_tests.png", "Expected output.")
p("To see each test by name, add `-v`. Good ones to show: `python -m pytest tests/test_scorer.py -v` (hand-calculated scores).", size=10.5)

h("Step 3. Recompute every result from saved predictions", 2)
command("python scripts/reproduce_metrics.py")
p("Every line should say **match**. \"not checkable\" means that run folder holds no predictions to re-score "
  "(for example the speed measurements), never a failure.")
image(IMG / "screen_reproduce.png", "Expected output (a selection of lines plus the final count).")

h("Step 4. Independent check with scikit-learn", 2)
command("python scripts/verify_with_sklearn.py")
p("Every line should say **agrees**: scikit-learn computed exactly the number our scorer recorded.")
image(IMG / "screen_sklearn.png", "Expected output.")

h("Step 5. Check one result by hand", 2)
p("Open the folder `runs\\20261024_1654_P1_A2-selected_0` in File Explorer. It holds:")
table(["File", "What it shows"], [
    ["predictions.jsonl", "One line per request: the correct answer (gold_intent) and the system's answer (predicted_intent)"],
    ["metrics.json", "The scores: look for \"intent_macro_f1\": 0.974..."],
    ["manifest.json", "Code version (git commit), model fingerprint, data fingerprints"],
    ["config.json", "Which design was used and why"],
], [4.0, 12.6])
p("Open `predictions.jsonl` in Notepad and compare `gold_intent` with `predicted_intent` on a few lines. They "
  "should match on most lines. That is what the score summarises.")

h("Step 6. Live demo", 2)
command("python scripts/demo.py --project P1")
image(IMG / "screen_demo.png", "Expected output: normal, off-topic and invalid requests.")
p("To type your own requests, add `--interactive`. A teacher can try anything, e.g. \"dim the kitchen lights\".")

h("Step 7. The dated history of the work", 2)
command("git log --reverse --format=\"%ad  %s\" --date=format:\"%d %b %H:%M\"")
p("Shows every saved step from 11 October, oldest first: setup, data, scorer, the 12 designs, Analyzer, "
  "Architect, export, baselines and tests.")
image(IMG / "screen_gitlog.png", "The project history.")
page_break()

# -- 8 ---------------------------------------------------------------------

h("8. Questions a teacher may ask, with answers")
qa = [
    ("How did you build this?",
     "We planned the project (the plan with gates G0-G12 is in `docs\\PROJECT_PLAN.md`), made the design "
     "decisions, checked every result, and used Claude Code, an AI coding assistant, to write much of the code "
     "and run the experiments. That assistance is recorded in `docs\\contributions.md`, as the plan requires."),
    ("Why is it agentic and not just a script?",
     "A script follows fixed rules. Here the AI reads the project, decides which designs to test, gives a reason "
     "for each, sees the scores and revises its choice. The reasons are saved in each run's `config.json`."),
    ("What is F1 and why not just accuracy?",
     "Accuracy can look good while a rare request type is always missed. Macro-F1 scores every request type "
     "separately and averages them, so a system cannot hide its failures on rare ones."),
    ("Why did the original agent not beat random search?",
     "Its AI kept choosing one kind of example and never tried the best design. Six of the 12 designs score "
     "within 6 points of the best, so random picks usually include a good one. The improved agent fixes this "
     "with a better search structure, using the same model."),
    ("How do we know you did not tune on the test data?",
     "The test data is locked by code until the freeze, and project P3 is fully hidden. A test checks that the "
     "design run never touches the test split. All results so far are on development data."),
    ("Can I see it run again?",
     "Yes, Section 7. Every result can be recomputed, and the model gives identical answers on repeat."),
    ("Which model did you use and why?",
     "qwen2.5:3b, run locally with Ollama. It fits our 4 GB graphics card, answers in about 0.4 s, always "
     "returned valid output and gave identical answers on repeat."),
    ("Is B2 fair, given you built the agent?",
     "It is a single, non-blind measurement, and we say so. On P1 the person worked by hand; on P2 they used "
     "ChatGPT and declared it. Both are reported separately with their caveats."),
]
for question, answer in qa:
    para = doc.add_paragraph()
    add_runs(para, f"**Q: {question}**")
    para.paragraph_format.space_after = Pt(2)
    p(f"A: {answer}", size=10.5)

# -- 9 ---------------------------------------------------------------------

h("9. Honest limitations")
bullets([
    "**All results here are development scores.** The final numbers come from the locked test data after the freeze. The improved agent (A2) was designed after seeing development results, so only its test result counts as evidence.",
    "**Small development sets (100 cases per project)**: the confidence intervals show most differences could still be chance.",
    "**One small model (3B)** for every AI-based system; a larger model was not tested because of the 4 GB graphics card.",
    "**B2 is one person per project**, a beginner on the team that built the agent; P2 used ChatGPT.",
    "**Two development projects**; the held-out project P3 is still to be run.",
    "**Entity extraction remains the weakest area**, mainly extracting words that are not fields.",
])

# -- 10 --------------------------------------------------------------------

h("10. Where everything is")
table(["What", "Where"], [
    ["The plan", "docs\\PROJECT_PLAN.md"],
    ["Day-by-day progress", "docs\\PROGRESS_TRACKER.md"],
    ["Every design decision, with reasons", "docs\\decisions.md"],
    ["Findings with caveats", "docs\\FINDINGS.md"],
    ["Full analysis report", "reports\\DEV_ANALYSIS.md"],
    ["One-command evidence summary", "reports\\EVIDENCE_SUMMARY.md"],
    ["Charts and their sources", "reports\\figures\\ (SOURCES.md lists the run behind every value)"],
    ["Every experiment run", f"runs\\ ({RUN_COUNT} folders)"],
    ["Demo presentation guide", "the \"NLP Project: Demo and Proof Guide\" document"],
    ["Team and AI-assistance record", "docs\\contributions.md"],
], [6.0, 10.6])

doc.save(OUT)
print(f"wrote {OUT.relative_to(ROOT)}")
