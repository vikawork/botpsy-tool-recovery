#!/usr/bin/env bash
# The whole measurement: both servers, 20 trials of each scenario per model, raw results in results/.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p results logs
rm -f results/botpsy.jsonl results/base.jsonl
./serve.sh botpsy botpsy-0.8b-q8_0.gguf 8091
./serve.sh base qwen3.5-0.8b-q8_0.gguf 8092
docker exec vk-botpsy /app/llama-server --version > logs/llama-version.txt 2>&1 || true
date -Is > logs/started.txt
python3 harness.py http://127.0.0.1:8091 botpsy results/botpsy.jsonl > logs/run-botpsy.log 2>&1 &
python3 harness.py http://127.0.0.1:8092 base results/base.jsonl > logs/run-base.log 2>&1 &
wait
date -Is > logs/finished.txt
docker rm -f vk-botpsy vk-base >/dev/null
wc -l results/botpsy.jsonl results/base.jsonl
