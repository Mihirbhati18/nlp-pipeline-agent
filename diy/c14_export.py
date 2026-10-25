"""C14 yourself: save a pipeline as a package, protect it with a fingerprint, load it and use it.

Needs the Ollama app open for the last step.  Run:  python diy/c14_export.py
"""

import hashlib
import json
from pathlib import Path

from mini_pipeline import answer

# 1. Export: write the chosen design into a file.
package = {"project": "P1 home assistant", "examples": "fixed", "refusal": "model", "model": "qwen2.5:3b"}
path = Path("diy/my_package.json")
path.write_text(json.dumps(package, indent=2), encoding="utf-8")

# 2. Fingerprint it: SHA-256 turns the file's exact bytes into a code. Change one letter
#    and the code changes completely.
fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
Path("diy/my_package.sha256").write_text(fingerprint, encoding="utf-8")
print("saved diy/my_package.json, fingerprint", fingerprint[:16], "...")


# 3. Load: check the fingerprint first; refuse a changed file.
def load(path):
    expected = Path("diy/my_package.sha256").read_text(encoding="utf-8")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"{path} was changed after it was saved: refusing to load it")
    return json.loads(path.read_text(encoding="utf-8"))


design = load(path)
print("loaded:", design)
for request in ["dim the kitchen lights", "who won the match yesterday"]:
    print(f"{request!r} -> {answer(request, examples=design['examples'], refusal=design['refusal'])}")

# 4. Tamper with a copy and show it is refused.
tampered = Path("diy/my_package_tampered.json")
tampered.write_text(path.read_text(encoding="utf-8").replace("fixed", "similar"), encoding="utf-8")
try:
    load(tampered)
except ValueError as error:
    print("tampered copy:", error)
