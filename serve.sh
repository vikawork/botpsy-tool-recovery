#!/usr/bin/env bash
# serve.sh <name> <gguf> <port>: llama-server on the CPU with the settings from BotPsy's GGUF model card.
set -euo pipefail
name=$1 gguf=$2 port=$3
IMG=ghcr.io/ggml-org/llama.cpp:full-b12211@sha256:8960de326dd60972cc4d442531f4efa006416d5896da2a39f0def0b55cbcb0c2
MODELS=${MODELS:-/scratch/vikawork/demo/botpsy/models}
docker rm -f "vk-$name" >/dev/null 2>&1 || true
docker run -d --name "vk-$name" -p "127.0.0.1:$port:8080" -v "$MODELS":/models:ro "$IMG" \
  --server -m "/models/$gguf" --jinja -c 32768 --temp 0.3 --top-p 0.95 --top-k 20 --presence-penalty 1.5 \
  --chat-template-kwargs '{"enable_thinking": true}' -t 4 -ngl 0 --parallel 1 --host 0.0.0.0 --port 8080
for _ in $(seq 90); do curl -sf "localhost:$port/health" >/dev/null && { echo "$name ready on $port"; exit 0; }; sleep 2; done
echo "$name did not become ready" >&2; docker logs --tail 20 "vk-$name" >&2; exit 1
