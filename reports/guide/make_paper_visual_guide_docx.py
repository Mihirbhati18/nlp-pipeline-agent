"""Build "The Paper, Piece by Piece": a screenshot of each part of the paper with a short, simple explanation.

Screenshots come from reports/guide/make_paper_shots.py (run it first). For each part: the picture, "In short"
(what that part says) and "Words used here" (every term in it, in plain words).
Writes paper/Paper_Piece_by_Piece.docx and .pdf.

    python reports/guide/make_paper_shots.py
    python reports/guide/make_paper_visual_guide_docx.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from docx_helpers import Builder  # noqa: E402

ROOT = HERE.parents[1]
SHOTS = HERE / "paper_shots"
OUT = ROOT / "paper" / "Paper_Piece_by_Piece.docx"
WIDE = {"title", "table1", "fig1", "table3"}

b = Builder()


def part(name: str, label: str, short: str, words: list[str] | None = None) -> None:
    """One piece of the paper: heading, screenshot, short meaning, terms."""
    b.html.append('<div style="break-inside: avoid; page-break-inside: avoid">')  # heading stays with its picture
    b.h(label, 2)
    b.image(SHOTS / f"{name}.png", "From the paper", width_cm=16.6 if name in WIDE else 12.5)
    b.html.append("</div>")
    b.callout(f"**In short:** {short}")
    if words:
        b.html.append('<div style="break-inside: avoid; page-break-inside: avoid">')
        b.p("**Words used here:**")
        b.bullets(words)
        b.html.append("</div>")


b.title(
    "The Paper, Piece by Piece",
    "A screenshot of every part of our research paper, each followed by what it means in simple words",
    ["Mihir Bhati (24BCE5341)  ·  Ahana Sharan (24BCE5334)  ·  Guide: Vijayaprabakaran K", "VIT Chennai"],
)
b.callout("**How to read this.** Each box is cut straight from the paper. Under it: **In short** says what that "
          "part is telling the reader, and **Words used here** explains every technical word in it. A dashed line "
          "inside a picture means the text continues in the next column or on the next page. For the longer, "
          "section-by-section explanation and the teacher questions, see `Research_Paper_Explained.pdf`.")
b.h("Five ideas to keep in your head while reading", 2)
b.numbered([
    "**The task:** turn a sentence into an **intent** (what the user wants) and **entities** (the details), or say "
    "\"not supported\".",
    "**The design:** there are 12 ways (designs) to set up the AI for this. Choosing well matters (13–16 points difference).",
    "**Our agent:** tries only 4 of the 12 on 100 practice sentences and keeps the best by a fixed rule.",
    "**Fair testing:** everything was frozen before the real test; P3 was a whole project kept secret until then.",
    "**The result:** best design found every time; wins on P1 and P2; on P3 slightly worse on intents (could be luck) "
    "but much better on entities.",
])
b.page_break()

# ---------------------------------------------------------------------------
b.h("Page 1: title, abstract, introduction")
part("title", "Title and authors",
     "What the paper is about in one line: a small AI agent that automatically designs the part of an assistant that "
     "understands requests (intents and slots), tested carefully on the MASSIVE dataset. Then who wrote it. The * "
     "means Mihir and Ahana contributed equally.",
     ["**Automated design:** the computer makes the design choices, not a person.",
      "**Task-specific:** built for one particular app (e.g. a smart-home app).",
      "**Intent and slot:** intent = what the user wants (`alarm_set`); slot = a detail (time = \"seven\").",
      "**Pipeline:** the full chain from the user's sentence to the final answer.",
      "**Small language-model agent:** a program that uses a small AI model (3 billion parameters) to make decisions.",
      "**Controlled evaluation:** a fair test with fixed rules decided in advance.",
      "**MASSIVE:** a public dataset of assistant requests from Amazon."])
part("abstract", "Abstract and index terms",
     "The whole paper in 198 words: the problem (choosing prompt, examples and rejection by trial and error), what we "
     "built (an agent that does it automatically), how it works (check, rank, test 4 of 12, revise, select, export) "
     "and the main numbers. Index terms are search keywords.",
     ["**Project specification:** what the agent is given: description, list of intents, list of entity types, 10 "
      "example sentences per intent.",
      "**Utterance:** one user sentence.",
      "**Validates and enriches:** checks the input for mistakes, then writes a short description of every label.",
      "**Design factor:** one of the three choices (how to extract, which examples, how to reject).",
      "**Development utterances:** practice sentences used to choose (100 per project).",
      "**Schema validity:** the AI's reply is in the required format.",
      "**Latency:** how long one request takes.",
      "**Hash-verified package:** the saved pipeline, with fingerprints that prove nothing was changed.",
      "**Held out until the protocol was frozen:** P3 stayed locked until all rules and choices were fixed.",
      "**Development-optimal design:** the best of all 12 designs on the practice set.",
      "**Macro-F1, points:** the accuracy score (0 to 1); 1 point = 0.01.",
      "**Preregistered success rule:** the pass/fail rule we fixed before testing.",
      "**Not significant:** the difference is small enough that it could be luck.",
      "**k-shot XLM-R:** a trained model (XLM-R) given the same 10 examples per intent."])
part("intro1", "Introduction, paragraph 1: the problem",
     "Explains the task with an example and why it is hard for a new app: every app has different intents, and "
     "trained models need thousands of labelled sentences (MASSIVE has 1,159 for alarms and smart home alone).",
     ["**Task-oriented assistant:** an assistant built to do jobs (alarms, emails), not to chat.",
      "**Refuse requests it was not built for:** say \"not supported\" for out-of-scope requests.",
      "**Inventory:** the list of intents one app supports.",
      "**Fine-tuned encoders:** models such as BERT or XLM-R that learn by training on many labelled examples.",
      "**[1], [2], [3]:** reference numbers; the full papers are listed at the end."])
part("intro2", "Introduction, paragraph 2: why design matters",
     "Small AI models need no training and run on a laptop, but someone must still decide how to use them. Those "
     "decisions change accuracy a lot: the 12 designs range from 0.839 to 0.974 on P1 and 0.738 to 0.898 on P2.",
     ["**Instruction-tuned language model (LM):** an AI trained to follow written instructions.",
      "**3-billion-parameter, quantised to 4 bits:** a small model, compressed so it fits in 4 GB of laptop memory.",
      "**Label inventory:** the list of intents.",
      "**Demonstrations:** solved example sentences placed in the prompt.",
      "**Out-of-scope (OOS):** a request the app does not support.",
      "**Similarity threshold:** reject a request if it is not similar enough to any example.",
      "**Span 13.5 points:** best minus worst design = 0.974 − 0.839 = 0.135."])
part("intro3", "Introduction, paragraph 3: what others did and what is missing",
     "Other work rewrites instructions, tunes examples or trains a small model, but none outputs intent + entities + "
     "rejection under real limits, and they are rarely compared with random choice. Without that comparison you "
     "can't tell if the AI's reasoning helped.",
     ["**Fixed program:** a pipeline whose structure a person already wrote.",
      "**Joint intent and span output:** giving the intent and the entity positions together.",
      "**Deployment constraints:** limits a real app has (format must be valid, must be fast).",
      "**Random search:** trying options chosen at random; the fair baseline for any smart search.",
      "**Adaptive search:** a search that uses results so far to choose what to try next."])
part("contrib", "Introduction, paragraph 4 and the three contributions",
     "The research question (can a 4-try agent beat a generic prompt, random search, a human and a trained model?) "
     "and what the paper adds: (1) the method and agent, (2) the factor-wise planning idea that found the best design "
     "every time, (3) a careful test on three projects.",
     ["**Candidate evaluations:** designs actually tested; the budget is 4.",
      "**Generic prompt:** the default setup with no design effort (our B1).",
      "**Constrained selection over a factorised discrete design space:** pick the best from a fixed list of "
      "combinations of 3 choices, while obeying rules.",
      "**Verifiable package:** an output whose files can be checked for changes.",
      "**Factor-wise planning:** decide each of the 3 choices separately, then test them in a fixed pattern.",
      "**Baseline families:** the different kinds of systems we compare against.",
      "**Matched-budget random search:** random search allowed the same 4 tries.",
      "**Paired bootstrap confidence intervals:** a statistics method to tell real differences from luck."])
b.page_break()

# ---------------------------------------------------------------------------
b.h("Pages 2–3: literature survey (15 papers)")
b.p("Each paragraph is one earlier paper: what it did, then (last sentence) how it connects to our work.")
part("s_massive", "Survey intro and A. MASSIVE [3]",
     "MASSIVE is our dataset: 1 million requests in 51 languages, 60 intents, 18 topics, 55 slot types. We use only "
     "English and split it into small apps.",
     ["**Survey:** a review of earlier research.",
      "**Localised by professional translators:** translated and adapted for each language by humans.",
      "**SLURP corpus [10]:** the English collection MASSIVE was built from.",
      "**Scenario:** a topic group, like alarm or email.",
      "**Span annotations:** markings of exactly which words are each slot.",
      "**mT5:** another model used as a baseline by MASSIVE's authors.",
      "**Single-product inventories:** intent lists for one app each."])
part("s_larson", "Larson et al. [11]: out-of-scope requests",
     "A dataset with off-topic questions showed models that are accurate on normal requests still miss most off-topic "
     "ones. That is why rejection is one of our three design choices and why we report OOS F1 separately.",
     ["**CLINC150:** their dataset (150 intents).",
      "**In-scope accuracy:** accuracy on requests the app does support.",
      "**Recall few out-of-scope queries:** they catch only a small share of off-topic requests.",
      "**Confidence threshold:** reject if the model is not confident enough.",
      "**OOS F1:** our score for how well a system refuses off-topic requests."])
part("s_chen", "Chen et al. [1]: BERT for intent and slots",
     "One BERT model with two outputs (one for the intent, one for each word's slot), trained together, beat older "
     "models. Our XLM-R baseline uses the same two-output design.",
     ["**BERT:** a famous encoder model from Google.",
      "**Sentence representation / token representations:** the model's summary of the whole sentence / of each word.",
      "**Objectives:** what the model is trained to get right.",
      "**ATIS and Snips:** two older intent-and-slot datasets.",
      "**Two-head design:** one model, two outputs."])
part("s_conneau", "Conneau et al. [2]: XLM-R",
     "XLM-R is a big encoder trained on web text in 100 languages. We train its base version as baseline B3, on our "
     "10 examples per intent and on the full training data.",
     ["**Masked language model:** learns by guessing hidden words in sentences.",
      "**2.5 TB of filtered web text:** an enormous amount of training text.",
      "**Cross-lingual transfer:** learning in one language helps in others.",
      "**Named entity recognition:** finding names of people, places etc.",
      "**Fine-tune:** train an existing model further on your own data."])
part("s_brown", "B. Brown et al. [12]: GPT-3 and in-context learning",
     "A big AI can do a new task just from instructions and a few examples in the prompt, with no training. Once the "
     "prompt is the program, what goes in it becomes a design decision, which is what our 12 designs are.",
     ["**In-context learning:** learning a task from examples inside the prompt.",
      "**Autoregressive LM:** a model that writes text one piece at a time.",
      "**Weight update:** changing the model's numbers (training). Not needed here.",
      "**Enumerates:** lists all the options."])
part("s_liu", "Liu et al. [13]: choosing good examples",
     "Putting the examples most similar to the question into the prompt works better than random examples. Our "
     "\"similarity examples\" option does the same with a cheap word-matching method (TF-IDF).",
     ["**Sentence-encoder space:** sentences turned into numbers so similar ones are close together.",
      "**Nearest-neighbour demonstrations:** the most similar examples.",
      "**TF-IDF index:** a word-based way to measure how similar two sentences are; rare shared words count more."])
part("s_zhou", "C. Zhou et al. [4]: APE (automatic prompt engineer)",
     "An AI writes many possible instructions, each is scored, and the best is kept; often as good as human-written "
     "ones. But it produces one prompt for simple tasks, not a full pipeline.",
     ["**Input–output pairs:** example questions with their answers.",
      "**Held-out examples:** examples kept aside for scoring.",
      "**Resampled:** generate more candidates around the good ones.",
      "**Instruction-induction tasks:** tasks where the model must work out the instruction from examples."])
part("s_pryzant", "Pryzant et al. [5]: fixing prompts from their mistakes",
     "Describe a prompt's errors in words, edit the prompt to fix them, keep the best edits. Our revision step also "
     "shows the AI an error report, but allows only one move from a fixed list, so a bad suggestion can't break anything.",
     ["**Minibatch:** a small group of examples.",
      "**\"Gradient\":** here, a written description of what is wrong (borrowed from training maths).",
      "**Beam search, bandit procedure:** ways of keeping the most promising options while searching.",
      "**Binary classification:** yes/no tasks.",
      "**Discrete space:** a fixed list of options (our 12 designs)."])
part("s_yang", "Yang et al. [6]: OPRO (AI as optimiser)",
     "Show the AI earlier attempts with their scores and ask for a better one, over many rounds. We can only afford "
     "one round of revision because each test costs about 100 AI calls.",
     ["**Meta-prompt:** a prompt that contains past attempts and scores.",
      "**Travelling-salesman, GSM8K, Big-Bench Hard:** standard test problems (route planning, maths, hard reasoning)."])
part("s_khattab", "Khattab et al. [7]: DSPy",
     "Write an AI pipeline as building blocks; a tool automatically picks good examples and instructions. DSPy tunes "
     "what is inside a structure you wrote; our agent picks the structure itself.",
     ["**Declarative modules:** blocks that say what to do, not how.",
      "**Compiler bootstraps demonstrations:** automatically creates good examples.",
      "**Multi-hop question answering:** questions that need several facts combined."])
part("s_prompt2model", "D. Viswanathan et al. [8]: Prompt2Model",
     "From a task description, finds data, makes more data and trains a small model to deploy. Closest to our goal "
     "(description → working system), but needs training and was not tested on slots or rejection.",
     ["**Deployable artefact:** something ready to use in a real app.",
      "**Pretrained model:** a model already trained on general data."])
part("s_madaan", "E. Madaan et al. [14]: Self-Refine",
     "The AI writes an answer, criticises it and rewrites it. We use a small version: if a reply breaks the format, "
     "the AI gets one chance to repair it.",
     ["**Self-correction:** the model fixing its own output.",
      "**Schema:** the required reply format.",
      "**Violation:** the specific way the reply broke the format."])
part("s_yao", "Yao et al. [15]: ReAct",
     "The AI alternates thinking and acting and learns from what it observes. Our agent does the same at design level: "
     "think, test a design, look at the scores, act once more.",
     ["**Reasoning traces:** the model writing out its thinking.",
      "**Actions / observations:** doing something (like a search) and seeing the result.",
      "**Hallucination:** the AI making things up."])
part("s_bergstra", "F. Bergstra and Bengio [9]: random search",
     "Random search finds good settings faster than trying everything in a grid. It is the baseline any smart search "
     "must beat, so we compare the agent with 5 runs of random search using the same 4 tries and the same rule.",
     ["**Hyper-parameters:** settings you choose before training.",
      "**Grid search:** trying every combination in a table.",
      "**Adaptive optimiser:** a search that learns from results as it goes.",
      "**Seed:** a starting number that makes a random choice repeatable."])
part("s_he", "He et al. [16]: AutoML survey",
     "Automated machine learning searches over data steps, features, settings and network designs. In those terms, "
     "ours has a small hand-made search space, an AI as the search method, and practice-set testing as the costly step.",
     ["**AutoML:** automating the choices in building machine-learning systems.",
      "**Neural architecture search:** automatically designing neural networks.",
      "**Search space / search strategy / evaluation cost:** what you search over / how / how expensive each try is."])
part("gap", "G. Research gap",
     "What is missing in earlier work, in one sentence: nobody tested whether a small local AI agent with a fixed "
     "budget picks better complete intent + slot pipelines than random choice, a generic prompt and a human, under "
     "frozen rules. That is exactly what we test.",
     ["**Research gap:** the open question a paper answers.",
      "**Character-level slots:** entities given as exact character positions.",
      "**Frozen protocol:** all rules fixed before the final test."])
part("table1", "Table I: comparison with related work",
     "A side-by-side summary of 8 earlier works and ours. Only our system outputs slot spans, handles out-of-scope "
     "requests, gives a verified package and is compared with random search over the same space.",
     ["**What is searched or learned:** what each method changes (model weights, instruction text, examples, or our "
      "pipeline design).",
      "**Labelled data needed:** how many labelled examples it needs.",
      "**Slot spans:** does it output entities with positions?",
      "**OOS rejection:** does it refuse off-topic requests?",
      "**Deployable artefact:** what you get at the end.",
      "**Random-search control:** was it compared against random choice?"])
b.page_break()

# ---------------------------------------------------------------------------
b.h("Pages 3–5: proposed methodology")
part("formulation", "III-A. Problem formulation",
     "Describes the task in symbols: a project P is made of a description D, intents I, entity schema E, example pool "
     "K and constraints C, plus a practice set V. The goal: pick the design θ from the 12 that will work best on new "
     "requests, testing at most 4 and obeying the constraints.",
     ["**Tuple P = (D, I, E, K, C):** a bundle of the five inputs.",
      "**S_min:** minimum share of valid replies (0.98).",
      "**L_max:** maximum allowed slow-case time per request.",
      "**95th-percentile latency (p95):** 95% of requests are faster than this.",
      "**î (i-hat), Ŝ (S-hat):** the predicted intent and predicted spans; the hat means \"predicted\".",
      "**θ (theta) and Θ (Theta):** one design, and the set of all 12.",
      "**B = 4:** the budget of designs to test."])
part("fig1", "Figure 1: system architecture",
     "The picture of the whole system. Left to right: project input → 1 Analysis → 2 Planning → 3 Evaluation → "
     "5 Selection → 6 Export. Below: 4 Revision loops back with evaluation (3 tries + 1 revised try). Grey boxes use "
     "the AI. The design space box lists the 3 choices; the runtime box shows what happens to one request.",
     ["**Shaded phases:** the steps where the AI model is called.",
      "**c1, c2, c3, c4:** the four candidate designs tested.",
      "**Lexicographic rule:** compare by intent score first, then entity score, then speed.",
      "**Θ = X × S × O (|Θ| = 12):** 3 extraction × 2 example × 2 rejection options = 12 designs.",
      "**Span location:** turning the entity text into its position in the sentence."])
part("design_space", "III-B. Design space: extraction and example selection, equation (1)",
     "The 12 designs come from 3 choices. Extraction: joint (one call), two-stage (intent first, then its details), "
     "or schema-guided (one call with a description of every label). Examples: fixed (same one per intent) or "
     "similarity (16 most similar). Equation (1) measures how similar two sentences are.",
     ["**Trusted component:** pre-written, tested code; the agent never writes code.",
      "**Cosine similarity:** a 0-to-1 score of how much two sentences use the same words (1 = same).",
      "**φ (phi), TF-IDF map:** turns a sentence into a list of word weights.",
      "**Unigram, bigram:** single words, and pairs of words next to each other.",
      "**Sublinear term frequency:** a word repeated many times does not count proportionally more."])
part("rejection", "Rejection policy, equation (2) and the prompt limit",
     "Two ways to refuse off-topic requests: let the AI answer `none_of_the_above`, or refuse before calling the AI "
     "if the request is not similar enough to any example. Equation (2) picks that cut-off (τ*) on practice data. "
     "Prompts may hold at most 16 examples and 2,000 tokens.",
     ["**τ\\* (tau-star):** the best similarity cut-off.",
      "**arg max:** \"the value that gives the highest score\".",
      "**I ∪ {OOS}:** all intents plus the off-topic class.",
      "**Ties go to the lower threshold:** if two cut-offs score the same, choose the one that refuses fewer real requests.",
      "**Token:** a piece of a word (about 4 characters).",
      "**Truncated:** cut short."])
part("phase1", "III-C/D. Phase 1 (analysis) and start of Phase 2",
     "Phase 1 checks the input for problems without the AI (duplicate names, unknown labels, too few examples), then "
     "uses 2 AI calls to write a one-line description of every intent and entity type. The AI may only describe "
     "existing names, never add or rename.",
     ["**Deterministic:** always gives the same result; no AI involved.",
      "**Coverage findings:** notes such as \"this entity type never appears in the examples\".",
      "**Enrichment:** adding the descriptions.",
      "**Takes precedence:** the given schema always wins over what the AI writes."])
part("phase2", "Phase 2: the two planners (A1 and A2), equation (3)",
     "A1 just asks the AI to name 3 designs. A2 asks the AI to rank the options of each choice separately, then "
     "builds: c1 = all favourites, c2 = favourites but the other example option, c3 = favourites but the second-best "
     "extraction. So the alternatives are always tested, even if the AI's favourites are wrong.",
     ["**Planner:** the part that decides which designs to try.",
      "**x1 ≻ x2 ≻ x3:** x1 is preferred to x2, which is preferred to x3.",
      "**Runner-up:** second choice.",
      "**Fallback:** a fixed default used when the AI's answer is unusable."])
part("phase3", "Phase 3: evaluation",
     "Each candidate design is run on all 100 practice requests and scored. An error report lists each candidate's "
     "scores, share of valid replies, share of real requests wrongly refused, and share of invented entity values.",
     ["**Error report:** the summary shown to the AI before revision.",
      "**Wrongly rejected:** a supported request the system refused.",
      "**Not found in the utterance:** the AI returned a detail that is not in the sentence (invented)."])
part("phase4", "Phase 4: revision, equation (4)",
     "The AI sees the error report and picks one change from the best design so far; it may change only one of the "
     "three choices and only to an untried design. That design is the 4th and last test. The limit of 4 is enforced "
     "by our code, not left to the AI.",
     ["**ĉ (c-hat):** the best candidate so far.",
      "**N(ĉ), neighbourhood:** untried designs that differ from ĉ in exactly one choice.",
      "**Θ \\ ℰ:** all designs minus the ones already tested."])
part("phase5", "Phase 5: selection, equations (5) and (6)",
     "First remove candidates that break a rule (too many invalid replies, entity score too low, too slow). Then pick "
     "the highest intent score; on a tie the higher entity score; then the faster one. No weighted average, and if "
     "nothing qualifies the agent says so. Random search uses this same rule.",
     ["**𝒞_ok:** the eligible candidates.",
      "**SV(c) ≥ S_min:** valid-reply share at least the minimum.",
      "**arg lexmax:** pick the best by comparing criteria in order, like sorting words alphabetically.",
      "**Weighted average:** mixing scores with weights; avoided so trade-offs can't be hidden.",
      "**L̂95:** an estimate of the slow-case time (cached runs have no real timing)."])
part("phase6", "Phase 6: export, and what happens at runtime",
     "The final pipeline is saved with a fingerprint of every file and the model's identity; it refuses to run if "
     "anything changed. At runtime: optionally refuse by threshold, build the prompt, ask the AI, check the reply's "
     "format, allow one repair, and turn entity text into positions.",
     ["**SHA-256 hash:** a file fingerprint; changes if even one character changes.",
      "**Weights digest:** the fingerprint of the AI model itself.",
      "**Temperature zero:** the AI always gives its single most likely answer (repeatable).",
      "**Structured output:** the AI must reply in JSON format.",
      "**Repair call:** one extra try, telling the AI exactly what was wrong.",
      "**Kept in every denominator:** a failed reply still counts against the score; nothing is hidden."])
part("span_rule", "The span-location rule",
     "The AI returns entity text (\"seven\"), not positions. We find that exact text in the sentence (first exactly, "
     "then ignoring capitals). If it is not there, it counts as wrong. No near-matches are accepted, and every AI "
     "system uses this same rule.",
     ["**Offsets:** character positions (start and end).",
      "**Case-sensitive / case-insensitive:** capitals must match / capitals ignored.",
      "**Unsupported:** an entity text that is not in the sentence (invented).",
      "**False positive:** a wrong answer the system gave.",
      "**Fuzzy-matched:** accepting a similar but not exact spelling (we never do this)."])
part("metrics", "III-J. Evaluation metrics, equations (7) and (8)",
     "How we score. Intent macro-F1: F1 per intent, then averaged. Entity F1: a hit only if type, start and end all "
     "match, counted over all requests together. OOS F1: how well refusals are caught. Plus valid-reply share and "
     "speed.",
     ["**Precision (P):** of the answers given, how many were right.",
      "**Recall (R):** of the right answers, how many were found.",
      "**F1 = 2PR / (P + R):** one number combining both; 1 is perfect.",
      "**Macro (averaged per intent):** rare intents count as much as common ones.",
      "**Micro-averaged:** all hits and misses counted together.",
      "**G ∩ Ŝ:** spans in both the true set and the predicted set (the hits).",
      "**Wall-clock time:** real seconds measured by a clock.",
      "**Uncached runs:** the AI really called, not a saved answer replayed."])
b.page_break()

# ---------------------------------------------------------------------------
b.h("Pages 5–6: implementation (data, model, baselines, statistics)")
part("dataset", "IV-A. Dataset and projects",
     "We use the English part of MASSIVE (16,521 sentences) and build three apps from it. Each gets 10 examples per "
     "intent, 100 practice requests and 300 test requests (P3: 200), with off-topic requests from 11 unrelated topics. "
     "The entity list comes only from training data, like a real developer.",
     ["**CC BY 4.0:** a free licence: you may use it if you credit the authors.",
      "**Official training / development / test split:** MASSIVE's own division of its data.",
      "**Fixed seed:** the random sampling can be repeated exactly.",
      "**Gold entities:** the correct, human-labelled entities."])
part("table2", "Table II: the three projects",
     "Each project's topics, number of intents |I|, number of entity types |E|, number of examples |K|, and test size "
     "(in-scope + off-topic).",
     ["**P1 home assistant:** alarms and smart devices; 12 intents.",
      "**P2 productivity:** calendar, email, lists; 10 intents.",
      "**P3 ordering, travel:** takeaway food and transport; 6 intents; held out.",
      "**|…|:** \"the number of\"."])
part("heldout_lock", "How P3 was kept secret",
     "P3's data was locked by code that raises an error unless the freeze commit's fingerprint is given. All "
     "development used only P1 and P2. Everything was frozen in one commit before test data and P3 were opened.",
     ["**Data-access object:** the piece of code that guards the data.",
      "**Freeze commit:** the single saved version (in git) where all rules and choices were locked."])
part("model", "IV-B. Model and environment",
     "Which AI and computer: Qwen2.5-3B-Instruct, compressed to 4 bits, run by Ollama on a laptop with an RTX 3050 "
     "(4 GB). Settings make it give the same answer every time (50 of 50 identical). One call takes 0.42 s typically.",
     ["**Qwen2.5-3B-Instruct [17]:** the AI model (by Alibaba's Qwen team).",
      "**Q4_K_M:** the 4-bit compression format.",
      "**Ollama:** the free program that runs the model on the laptop.",
      "**Seed 0:** fixed randomness setting.",
      "**Deterministic:** same input, same output, every time.",
      "**Cached by prompt hash:** answers saved so experiments can be replayed; never used for timing."])
part("baselines", "IV-C. Baselines (the systems we compare against)",
     "B0 = simple word-based classifier. B1 = generic prompt (no design effort). B2 = a person choosing the design. "
     "B3 = XLM-R trained on the same 10 examples (B3-k) or all training data (B3-full). B4 = 4 random designs "
     "(5 times); B4-best = best of all 12 on practice data.",
     ["**Logistic regression:** a simple, classic classifier.",
      "**Bare specification:** the input without the AI-written descriptions.",
      "**Worksheet:** the form the person used to choose a design.",
      "**Epochs:** passes over the training data.",
      "**Learning rate 3×10⁻⁵, batch size 16:** training settings (step size; 16 sentences at a time).",
      "**Maximum softmax probability:** the trained model's top confidence; low means maybe off-topic."])
part("stats", "IV-D. Statistics and the success rule",
     "How we decide if a difference is real: resample the test set 1,000 times (paired bootstrap) and look at the "
     "middle 95% of differences. The success rule (fixed in advance): +2.0 points intent, at most −2.0 entity, valid "
     "replies ≥ 0.98, and no slower than twice B1. Timing alternates systems request by request so it is fair.",
     ["**Paired bootstrap [18]:** draw test sets with replacement, score both systems on the same draw, repeat.",
      "**Percentile:** the value below which that share of results lies.",
      "**95% interval:** the range where the true difference probably is.",
      "**Significant:** the interval does not include zero.",
      "**Warm-up requests:** first requests not timed, so start-up slowness doesn't count.",
      "**Interleaved:** B1, A1, A2, B1, A1, A2… in turn."])
b.page_break()

# ---------------------------------------------------------------------------
b.h("Pages 6–8: results")
part("table3", "Table III: the main test results",
     "The most important table. Each cell is intent F1 / entity F1 / OOS F1 on locked test data. Bold = best AI-based "
     "result per column. A2 has the best entity score of the AI systems on all three projects; B1 has the best intent "
     "score on P3; B3-full (lots of training data) has the best entities overall but weak refusal.",
     ["**–:** B0 does not predict entities.",
      "**Mean (range):** average of 5 random-search runs, with lowest and highest.",
      "**Held out:** P3, never used during development."])
part("overall", "IV-E. Overall results: which designs were chosen",
     "A2 chose schema-guided + similarity examples + AI rejection on P1 and P2, and joint + similarity + AI rejection "
     "on P3. Each time this equals the best of all 12 on practice data.",
     ["**B4-best:** the best of all 12 designs on practice data (the ceiling)."])
part("fig2", "Figure 2: intent scores as bars",
     "The intent numbers of Table III as a bar chart. Each pattern is one system. On P1 and P2 the agents (A1, A2) "
     "are among the tallest bars; on P3, B1 and the random-search average are slightly taller. The gap on P3 is B2 "
     "(not run there).",
     ["**Intent macro-F1 (test):** the vertical axis; higher is better."])
part("success", "The success rule result",
     "Compared with B1: A2 gained +2.2/+7.3 points (intent/entity) on P1, +4.9/+5.5 on P2, and −1.3/+14.6 on P3. So "
     "both agents pass on P1 and P2 and fail on P3. Valid replies ≥ 0.997, speed within the limit.",
     ["**Pass / fail:** whether all four conditions of the rule were met.",
      "**Median latency:** typical time per request (A2 0.68 s vs B1 0.45 s on P1)."])
part("significance", "Significance: which differences are real",
     "A2's intent gain over B1 is real (significant) on P2, not proven on P1, and the P3 loss is not significant. "
     "A2's entity gains are significant on all three. With only 200–300 test requests the intervals are about ±3 "
     "points wide, so a 2-point gain can pass the rule without being provable.",
     ["**CI [+1.1, +8.9]:** the 95% interval of the difference in points.",
      "**n.s.:** not significant."])
part("fig3", "Figure 3: confidence intervals",
     "Each line is one comparison. The dot is the measured difference; the line is the 95% range. If the line does "
     "not cross the dashed zero line (filled square), the difference is real. Only P1 \"A2 vs B2\" and P2 \"A2 vs B1\" "
     "clear zero for intent.",
     ["**Δ (delta):** difference.",
      "**Filled square / open circle:** significant / not significant."])
part("vs_random", "IV-F. Agent vs random search",
     "Random search averaged 0.893, 0.854, 0.894. A2 was above that on P1, at the top on P2, at the bottom on P3. "
     "Random search finds the best practice design only by luck (1 of 5 runs on P1/P2, 2 of 5 on P3); A2 found it "
     "every time.",
     ["**Probability 4/12:** chance that 4 random picks include one specific design."])
part("vs_human", "Agent vs the human designer",
     "A2 beat the person by 6.1 points on P1 (real) and 2.1 on P2 (not proven). On P1 the person chose threshold "
     "rejection, which made refusals much worse (0.471). On practice data every AI-rejection design beat every "
     "threshold design, so the agent never kept a threshold design.",
     [])
part("vs_xlmr", "IV-G. Agent vs trained XLM-R",
     "With the same 10 examples, XLM-R was 7–11 points worse on intents, worse on entities and much worse at "
     "refusing. With 10–32 times more data, XLM-R wins on entities but still refuses badly. So: few examples → use "
     "our pipeline; thousands of labelled sentences → a trained model is better at entities.",
     ["**10 to 32 times more labelled data:** 1,159 / 3,180 / 828 training sentences vs 120 / 100 / 60."])
part("why", "IV-H. Why factor-wise planning worked",
     "The key story. The AI's favourite options (fixed examples, threshold rejection) were both wrong, and the first "
     "three tries scored 0.76–0.87. But c2 always tests the other example option (similarity won), and the revision "
     "switched rejection to the AI label: +10.5 and +9.6 points, the best of all 12. A1 never found it. The structure, "
     "not the AI's guesses, made the difference.",
     ["**Unrestricted revision:** A1 could pick any untried design, and picked a poor one."])
part("table4", "Table IV: A2's four tries on practice data",
     "The scores of c1, c2, c3 and the revised c4 on P1 and P2. c4 (schema, similarity, AI label) is the best and "
     "equals the top of the range of all 12 designs.",
     ["**Range over all 12 designs:** worst to best when every design is tested."])
part("honesty", "Honesty note",
     "A2 was designed after we studied A1's practice results, so A2's practice scores are not independent proof. "
     "Its test scores and all of P3 are, because everything was frozen before those were opened.",
     ["**Independent evidence:** results not influenced by the people who built the system.",
      "**Keep-or-drop rule:** a rule fixed in advance for whether A2 would be tested at all."])
part("p3", "IV-I. Held-out project P3",
     "On P3 A2 again picked the best practice design, but on test it was 1.3 points below B1. P3's practice set had "
     "only about 13 requests per intent and the designs were very close (0.882–0.909), so the practice ranking did "
     "not carry over. Entities improved strongly (+14.6 over B1).",
     [])
part("ablations", "IV-J. Ablations",
     "Remove one part of A1 at a time to see what matters. Removing selection hurts most (−2.7, −2.9). Removing the "
     "descriptions hurts P2 entities a lot (−7.4) because some entity types have no examples. Removing repair barely "
     "matters because the AI rarely broke the format.",
     ["**Ablation:** removing a component to measure its value.",
      "**Without selection:** just use the first candidate (which is B1's design)."])
part("table5", "Table V: ablation scores",
     "Intent F1 on test for A1 and each variant with one part removed, on all three projects.",
     ["**Planner reasoning:** the AI's choice of designs (replaced by a fixed order in that variant)."])
part("cost", "IV-K. Cost and reproducibility",
     "Designing one project costs A2 about 397 AI calls (about 3 minutes), against 38 minutes for the person. Every "
     "number was recomputed from saved answers (99 of 99 runs matched), checked by an independent library to 9 "
     "decimal places, and B0 retrained from scratch gave identical results.",
     ["**Logical model calls:** calls the method needs (counting cached ones too).",
      "**Exhaustive evaluation:** testing all 12 designs.",
      "**Reproduced exactly:** same numbers when recomputed."])
b.page_break()

# ---------------------------------------------------------------------------
b.h("Page 8: conclusion, acknowledgment, references")
part("conclusion", "V. Conclusion",
     "A short restatement of what was built and found: best practice design on all three projects, success on P1 and "
     "P2, significant entity gains everywhere, the honest P3 result, better than XLM-R on the same data, and why it "
     "worked. No limitations or future work here (our teacher's rule).",
     [])
part("ack", "Acknowledgment",
     "Thanks the guide, states the dataset licence, and declares the use of an AI assistant.",
     [])
b.page_break()  # the reference list is taller than a page, so start it on a fresh one
part("refs", "References",
     "The 18 papers cited, in IEEE style, numbered in the order they first appear in the text. Each entry gives "
     "authors, title, where it was published, year and pages.",
     ["**arXiv preprint:** a paper posted online before or without formal publication.",
      "**Proceedings of …:** the book of papers from a conference (ACL, EMNLP, ICLR, NeurIPS are top AI/NLP conferences).",
      "**vol., pp.:** volume and page numbers."])

b.save(OUT)
b.save_pdf(OUT.with_suffix(".pdf"))
print(f"wrote {OUT.name} and {OUT.with_suffix('.pdf').name}")
