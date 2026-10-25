"""C2 yourself: is the AI model fast, and does it give the same answer twice?

Needs the Ollama app open.  Run:  python diy/c02_speed.py
"""

import statistics
import time

from helpers import ask_model, load_jsonl

requests = load_jsonl("data/processed/P1/dev.jsonl")[:10]   # the first 10 development requests

first_answers, times = [], []
for r in requests:
    prompt = f'Which smart-home action is this? Reply as JSON {{"intent": "..."}}. Request: {r["utt"]}'
    start = time.perf_counter()                 # start the stopwatch
    reply = ask_model(prompt)
    times.append(time.perf_counter() - start)   # stop it: seconds this request took
    first_answers.append(reply)

# Ask exactly the same 10 again and compare the answers word for word.
second_answers = [ask_model(f'Which smart-home action is this? Reply as JSON {{"intent": "..."}}. Request: {r["utt"]}')
                  for r in requests]
same = sum(a == b for a, b in zip(first_answers, second_answers))

print("seconds per request:", [round(t, 2) for t in times])
print("median:", round(statistics.median(times), 2), "s  (the first request is slower: it wakes the model up)")
print("identical answers on repeat:", same, "of", len(requests))
