"""Download XLM-R's files before training, retrying until complete.

B3 needs `xlm-roberta-base` (about 1.1 GB). On an unreliable connection the
download breaks repeatedly, and a break during training wastes the training
too. So this fetches the weights first, in its own retrying loop, and only
reports success when the files are actually present in the cache.

`huggingface_hub` resumes from its partial files, so every attempt continues
where the last one stopped rather than starting over.

Usage:
    python scripts/prefetch_b3_model.py
    python scripts/prefetch_b3_model.py --attempts 100
"""

from __future__ import annotations

import argparse
import sys
import time

MODEL_NAME = "xlm-roberta-base"
# Only what the tokenizer and the encoder actually need.
FILES = ("config.json", "tokenizer.json", "tokenizer_config.json", "sentencepiece.bpe.model")
WEIGHTS = ("model.safetensors", "pytorch_model.bin")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prefetch the B3 encoder weights")
    parser.add_argument("--attempts", type=int, default=60)
    parser.add_argument("--model", default=MODEL_NAME)
    args = parser.parse_args()

    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import EntryNotFoundError

    print(f"prefetching {args.model} (resumes after a break)")

    for name in FILES:
        for attempt in range(1, args.attempts + 1):
            try:
                hf_hub_download(args.model, name)
                print(f"  {name}: ok")
                break
            except EntryNotFoundError:
                print(f"  {name}: not in this repository, skipping")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  {name}: attempt {attempt} failed ({type(exc).__name__}); retrying")
                time.sleep(3)
        else:
            print(f"could not fetch {name}", file=sys.stderr)
            return 1

    # Either weights file is enough; safetensors is preferred when present.
    for name in WEIGHTS:
        got = False
        for attempt in range(1, args.attempts + 1):
            try:
                path = hf_hub_download(args.model, name)
                size = __import__("os").path.getsize(path)
                print(f"  {name}: ok ({size / 1e6:.0f} MB)")
                got = True
                break
            except EntryNotFoundError:
                print(f"  {name}: not in this repository")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  {name}: attempt {attempt} failed ({type(exc).__name__}); resuming",
                      flush=True)
                time.sleep(3)
        if got:
            print(f"\nweights ready. Now run: python scripts/run_b3_local.py")
            return 0

    print("could not fetch any weights file", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
