"""Three small helpers used by every "do it yourself" script.

These are deliberately simple, so you can read and explain every line.
They do the same jobs as the project's own code, in the plainest way.
"""

import json
import urllib.request

# The AI model runs inside the Ollama app on this laptop, at this address.
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5:3b"


def load_jsonl(path):
    """Read a .jsonl file: one JSON record per line. Returns a list of dictionaries."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def ask_model(prompt):
    """Send one prompt to the AI model and return its reply as text.

    temperature 0 and seed 0 make the model give the same answer every time;
    format "json" asks it to reply in JSON.
    """
    request_body = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "seed": 0},
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())["response"]


def read_intent(reply_text):
    """Get the intent out of the model's JSON reply. Returns None if the reply is broken."""
    try:
        return json.loads(reply_text).get("intent")
    except (json.JSONDecodeError, AttributeError):
        return None
