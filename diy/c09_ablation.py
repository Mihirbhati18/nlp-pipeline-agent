"""C9 yourself: an ablation. Remove one part of the pipeline and see how much the score drops.

Needs the Ollama app open. About a minute.  Run:  python diy/c09_ablation.py
"""

from mini_pipeline import DEV, evaluate

requests = DEV  # all 100 development requests

# 1. The full pipeline: fixed examples in the prompt, the model may refuse.
full, _ = evaluate(requests, examples="fixed", refusal="model")
print(f"full pipeline:            intent macro-F1 {full:.3f}")

# 2. Remove the examples from the prompt; everything else stays the same.
no_examples, _ = evaluate(requests, examples="fixed", refusal="model", show_examples=False)
print(f"without examples:         intent macro-F1 {no_examples:.3f}   (change {no_examples - full:+.3f})")

# 3. Swap the model's own refusal for the simple similarity cut-off.
cutoff, _ = evaluate(requests, examples="fixed", refusal="cutoff")
print(f"cut-off instead of model: intent macro-F1 {cutoff:.3f}   (change {cutoff - full:+.3f})")

print("\nA part that matters makes the score drop when it is removed.")
