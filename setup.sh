#!/usr/bin/env bash
# Fetches the pinned llama.cpp image and both models, then converts the base model to Q8_0 with the same release.
set -euo pipefail
cd /scratch/vikawork/demo/botpsy
UA="VikaworkDemo/0.1 (+https://vikawork.com)"
IMG=ghcr.io/ggml-org/llama.cpp:full-b12211@sha256:8960de326dd60972cc4d442531f4efa006416d5896da2a39f0def0b55cbcb0c2
BOT=17bb36aa29c58fcde8e321aaaad3f2f7372aa655
BASE=2fc06364715b967f1860aea9cf38778875588b17
docker pull -q "$IMG"
curl -fsSL -C - -A "$UA" -o models/botpsy-0.8b-q8_0.gguf "https://huggingface.co/qvac/BotPsy-0.8B-GGUFs/resolve/$BOT/botpsy-0.8b-q8_0.gguf"
echo "3ad45ab73cc5a45a200cda373f9cf7262741cc005b6e32b3a6221cb0c28e06be  models/botpsy-0.8b-q8_0.gguf" | sha256sum -c
for f in README.md LICENSE; do curl -fsSL -A "$UA" -o "models/botpsy-$f" "https://huggingface.co/qvac/BotPsy-0.8B-GGUFs/resolve/$BOT/$f"; done
for f in LICENSE README.md chat_template.jinja config.json merges.txt model.safetensors-00001-of-00001.safetensors model.safetensors.index.json tokenizer.json tokenizer_config.json vocab.json; do
  curl -fsSL -C - -A "$UA" -o "base-hf/$f" "https://huggingface.co/Qwen/Qwen3.5-0.8B/resolve/$BASE/$f"
done
docker run --rm --entrypoint python3 -v "$PWD":/w "$IMG" /app/convert_hf_to_gguf.py /w/base-hf --outtype q8_0 --outfile /w/models/qwen3.5-0.8b-q8_0.gguf
sha256sum models/*.gguf base-hf/model.safetensors-00001-of-00001.safetensors | tee logs/sha256.txt
ls -la models
