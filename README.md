# What a 0.8B model does when a tool call fails

A measurement by [Vikawork](https://vikawork.com/): when a tool call fails, does a small model fix the cause, stop,
or ask again? We compared [BotPsy-0.8B](https://huggingface.co/qvac/BotPsy-0.8B) with the model it is built on,
[Qwen3.5-0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B), on a simulated phone with five tools.

The request is always "Send a message to Maya: Running ten minutes late." 20 seeds per scenario, per model.

| Scenario | BotPsy-0.8B Q8_0: message sent | Qwen3.5-0.8B Q8_0: message sent |
| --- | ---: | ---: |
| Wi-Fi off | 20 of 20 | 2 of 20 |
| Wi-Fi off and message storage full | 20 of 20 | 1 of 20 |
| Nothing wrong | 20 of 20 | 20 of 20 |
| Account suspended (no tool can fix it) | 0 of 20, as intended | 0 of 20, as intended |

In the Wi-Fi-off scenario the base model usually made one call, got the error and stopped (13 of 20 runs). In 4 of
20 runs its final answer said the message was sent and mentioned no failure, although nothing was sent.

This is one request on our own harness, run once on 12 November 2026 (IST). It is not ACEBench and not a general
ranking of the two models. [REPORT.md](REPORT.md) has the full results, the setup and the limits.

## Run it

Needs Docker, Python 3 and about 4 GB of disk. CPU only.

```sh
./setup.sh      # pulls llama.cpp b12211 by digest, downloads both models, converts the base model to Q8_0
./run-all.sh    # starts two llama-server containers and runs 160 trials into results/
python3 summarize.py results > results/summary.json
```

`setup.sh`, `serve.sh` and `run-all.sh` contain the test machine's path (`/scratch/vikawork/demo/botpsy`); change it
to your own. To test another model, start it with `serve.sh` and point `harness.py` at its port.

## Files

| File | Contents |
| --- | --- |
| [REPORT.md](REPORT.md) | Results, setup, provenance and limits |
| [harness.py](harness.py) | The simulated phone, the tools, the prompts and the run loop (standard library only) |
| [results/botpsy.jsonl](results/botpsy.jsonl), [results/base.jsonl](results/base.jsonl) | Every run: each turn's reasoning text, tool calls, tool results and outcome |
| [results/summary.json](results/summary.json) | Counts per model and scenario |
| [results/hand-classification.json](results/hand-classification.json) | The base model's final answers in failed runs, classified by hand |
| [logs/](logs/) | llama.cpp version, file hashes, start and finish times |
