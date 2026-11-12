# BotPsy tool-failure recovery test (Vikawork, 12 November 2026)

## Question

QVAC reports an ACEBench task in which a message failed to send because Wi-Fi was off, then because the inbox was
full; BotPsy turned Wi-Fi on and made room before sending, "while its base model kept retrying the same send"
(https://qvac.tether.io/models/botpsy). Does that behaviour reproduce in a small simulated phone, on a desktop CPU?

This is our own harness, not ACEBench. It tests one request against five simulated tools.

The five tools: `send_message(to, text)`, `set_wifi(enabled)`, `get_device_status()`, `list_messages()`,
`delete_message(message_id)`. Each is a deterministic function of the simulated state and its arguments; nothing
leaves the machine. Error texts: "Network unavailable: Wi-Fi is off."; "Message storage is full (5 of 5). Delete a
message to free space."; "Carrier rejected the message: this account is suspended. Contact the carrier."

## Result

160 runs: 2 models × 4 scenarios × 20 seeds. The request is always "Send a message to Maya: Running ten minutes late."

| Scenario | BotPsy-0.8B Q8_0: message sent | Qwen3.5-0.8B Q8_0 (base): message sent |
| --- | ---: | ---: |
| one-fault (Wi-Fi off) | 20 of 20 | 2 of 20 |
| two-faults (Wi-Fi off and storage full) | 20 of 20 | 1 of 20 |
| no-fault | 20 of 20 | 20 of 20 |
| no-fix (account suspended; nothing can fix it) | 0 of 20, as intended | 0 of 20, as intended |

- BotPsy: no repeated failed send in any of its 80 runs. In two-faults its median was 6 tool calls (send, Wi-Fi on,
  send, list, delete, send). In no-fix it stopped after the first failure in 20 of 20 runs and told the user the
  account was suspended.
- Base, one-fault: in 13 of 20 runs it made one call, got the error and stopped. In 1 run (seed 2) it repeated the
  failing send until the 12-turn limit (10 repeats). So the repeat loop QVAC describes appeared, but rarely: giving up
  after one failure was the common outcome here.
  In 4 more runs (seeds 6, 10, 14, 19) it turned Wi-Fi on after the error and then answered without sending again;
  the remaining 2 runs sent the message.
- Base, final answers when nothing was sent (read by hand, `results/hand-classification.json`; 18 such runs in one-fault, of which 1 hit the turn limit with no answer, and 19 in two-faults, of which 2 did): in one-fault, 4 of 20
  runs told the user the message was sent and mentioned no failure; 7 said both that it was sent and that it failed;
  6 reported the failure plainly. In two-faults the counts were 3, 8 and 6.
- Base, two-faults: 1 run completed the whole recovery (seed 14); 2 hit the turn limit (seed 2 repeating the send,
  seed 16 deleting messages it had already deleted).
- Median wall time per run, both servers running at once on the same CPU: BotPsy 5.9 s (no-fault), 12.1 s (one-fault),
  65.3 s (two-faults); base 10.1 s, 13.4 s, 13.7 s. These are not a speed comparison: the servers shared the CPU.

Counts per scenario: `results/summary.json` (from `summarize.py`). Every turn, call and tool result:
`results/botpsy.jsonl`, `results/base.jsonl`.

## Runs shown on screen

- BotPsy, one-fault, seed 1: `send_message` fails on Wi-Fi, `set_wifi(true)`, `send_message` succeeds. All 20 one-fault
  runs made these three calls. Two-faults, seed 1: send, `set_wifi(true)`, send (storage full), `list_messages`,
  `delete_message(5)`, send; 18 of 20 two-fault runs made these six calls and 2 listed the messages once more.
- BotPsy, no-fix, seed 1: one failed send, then "The message couldn't be sent because your account is suspended.
  You'll need to contact the carrier to resolve this issue."
- Base, one-fault, seed 17: one failed send, then "I have sent a message to Maya about running ten minutes late. The
  message was successfully delivered."
- Tool results are JSON: `{"ok": true, "wifi": "on"}`, `{"ok": true, "status": "sent"}`, `{"ok": true, "deleted": 5}`,
  `{"ok": false, "error": "<text>"}`. On screen, errors show the error text, calls show `send_message("Maya", …)` for
  `send_message("Maya", "Running ten minutes late.")`, and the message list is summarised.
  In the two-fault trace the storage row stays at 4 of 5 after the last send; the harness then stores the sent
  message, which makes it 5 of 5.

## Setup

- Test machine: Intel Core i7-7700K, 4 cores / 8 threads, 32 GB RAM, Linux. CPU only (`-ngl 0`), 4 threads per server.
- llama.cpp release b12211, the official container image
  `ghcr.io/ggml-org/llama.cpp:full-b12211@sha256:8960de326dd60972cc4d442531f4efa006416d5896da2a39f0def0b55cbcb0c2`
  (`llama-server --version`: build 12211, commit 7d7f02875).
- BotPsy: `botpsy-0.8b-q8_0.gguf` from `qvac/BotPsy-0.8B-GGUFs` at revision 17bb36aa29c58fcde8e321aaaad3f2f7372aa655,
  SHA256 3ad45ab73cc5a45a200cda373f9cf7262741cc005b6e32b3a6221cb0c28e06be (matches the repository's LFS hash).
- Base: `Qwen/Qwen3.5-0.8B` at revision 2fc06364715b967f1860aea9cf38778875588b17, converted by us to Q8_0 with the
  same release's `convert_hf_to_gguf.py --outtype q8_0` (Qwen publishes no GGUF of this model). Output SHA256
  e35200cb6bd8ed0e263c0dbbe2d70c68d48eef96d9a073ee37f76d6872223509.
- Server flags, from BotPsy's GGUF model card: `--jinja -c 32768 --temp 0.3 --top-p 0.95 --top-k 20
  --presence-penalty 1.5 --chat-template-kwargs '{"enable_thinking": true}'`. The same flags for both models; each
  model uses the chat template embedded in its own file. The harness also sends the sampling values per request, with
  `max_tokens` 4096 and `seed` 1 to 20.
- Harness: `harness.py` (standard library). System prompt, user request, tool schemas and error texts are in the file.
  A run ends when the model answers without a tool call, or after 12 assistant turns.
- Run: 12 November 2026, 06:39 to 07:09 IST (`logs/`). Scripts: `setup.sh`, `serve.sh`,
  `run-all.sh`, `summarize.py` are here.

## Limits

- One request, five tools, one phrasing of each error message. A different prompt or error text may change the result.
- 20 seeds per scenario. The base model's one-fault and two-faults runs start identically for the same seed (the first
  failure is the same), so those two rows are not independent samples.
- The base model was run with BotPsy's recommended sampling and thinking mode, which may not be its best settings, and
  from our own GGUF conversion.
- Q8_0 files on llama.cpp; QVAC's headline scores are from BF16 weights on vLLM.
- "Message sent" checks the recipient and that the text contains "ten minutes late". It does not grade the wording of
  the final answer; the hand classification covers only the base model's failed runs in the two fault scenarios.
- The repeat metric counts a failed `send_message` that follows a failed `send_message` with the same error and no
  state change in between.
- A simulated executor shows the model's decisions, not reliability on a real phone.
