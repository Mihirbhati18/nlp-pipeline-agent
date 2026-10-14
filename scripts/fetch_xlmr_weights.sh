#!/usr/bin/env bash
# Resumable, hash-verified download of XLM-R base weights for B3.
#
# huggingface_hub's chunked (xet) backend stalled on this connection, so this
# fetches model.safetensors with curl byte-range resume instead. Two guards
# against the corruption seen with the GGUF download on 12 Oct:
#   - `curl -C -` aborts (exit 33) rather than appending when a server ignores
#     the range request, so a full copy can never be glued onto a partial one
#   - the finished file must match the SHA-256 Hugging Face publishes (it is
#     the blob's name in the cache), or it is deleted
# The verified file is then placed in the Hugging Face cache, where
# `AutoModel.from_pretrained("xlm-roberta-base")` finds it.
set -u
SHA=6fd4797bc397c3b8b55d6bb5740366b57e6a3ce91c04c77f22aafc0c128e6feb
URL=https://huggingface.co/FacebookAI/xlm-roberta-base/resolve/main/model.safetensors
HUB="$HOME/.cache/huggingface/hub/models--xlm-roberta-base"
REV=$(cat "$HUB/refs/main")
PART="$HUB/blobs/$SHA.curlpart"

mkdir -p "$HUB/blobs" "$HUB/snapshots/$REV"
for attempt in $(seq 1 300); do
  curl -sSL -C - --retry 3 --speed-limit 1000 --speed-time 60 -o "$PART" "$URL"
  code=$?
  size=$(stat -c %s "$PART" 2>/dev/null || echo 0)
  echo "attempt $attempt: curl exit $code, $((size / 1048576)) MB on disk"
  if [ "$code" -eq 33 ]; then
    echo "server ignored the range request; refusing to append" >&2
    exit 1
  fi
  [ "$code" -eq 0 ] && break
  sleep 5
done

echo "verifying SHA-256..."
actual=$(sha256sum "$PART" | cut -d' ' -f1)
if [ "$actual" != "$SHA" ]; then
  echo "hash mismatch ($actual); deleting the corrupt file" >&2
  rm -f "$PART"
  exit 1
fi
mv "$PART" "$HUB/blobs/$SHA"
rm -f "$HUB/blobs/$SHA.incomplete"
cp "$HUB/blobs/$SHA" "$HUB/snapshots/$REV/model.safetensors"
echo "weights verified and installed"
