#!/usr/bin/env python3
"""Tool-failure recovery test: does a model fix the cause of a failed tool call, or repeat the call?

Usage:
  harness.py <base-url> <label> <out.jsonl> [--trials 20] [--scenarios two-faults,one-fault,no-fault,no-fix]

Talks to an OpenAI-compatible server (llama-server --jinja) and plays a simulated phone. Every tool is a
deterministic function of the simulated state; nothing is sent anywhere. One JSON line per run goes to <out.jsonl>:
the scenario, the seed, every assistant turn (reasoning, text, tool calls), every tool result and the outcome.

Scenarios (the user's request is the same in all four: send one message):
  two-faults  Wi-Fi is off and message storage is full. Sending fails until both are fixed (QVAC's published example).
  one-fault   Wi-Fi is off.
  no-fault    Nothing is wrong; the first send works.
  no-fix      The carrier has suspended the account. No tool can fix it; the right move is to stop and say so.

Standard library only.
"""
import argparse
import json
import time
import urllib.request

SYSTEM = ("You are an assistant running on the user's phone. Use the tools to do what the user asks. "
          "When the task is done, or you cannot complete it, tell the user in one or two sentences.")
USER = "Send a message to Maya: Running ten minutes late."
MAX_TURNS = 12
SAMPLING = {"temperature": 0.3, "top_p": 0.95, "top_k": 20, "presence_penalty": 1.5, "max_tokens": 4096}

TOOLS = [
    {"type": "function", "function": {
        "name": "send_message", "description": "Send a text message to a contact.",
        "parameters": {"type": "object", "properties": {
            "to": {"type": "string", "description": "Contact name"},
            "text": {"type": "string", "description": "Message text"}}, "required": ["to", "text"]}}},
    {"type": "function", "function": {
        "name": "set_wifi", "description": "Turn Wi-Fi on or off.",
        "parameters": {"type": "object", "properties": {
            "enabled": {"type": "boolean", "description": "true turns Wi-Fi on"}}, "required": ["enabled"]}}},
    {"type": "function", "function": {
        "name": "get_device_status", "description": "Report Wi-Fi state and message storage use.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "list_messages", "description": "List stored messages with their ids.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "delete_message", "description": "Delete one stored message by id.",
        "parameters": {"type": "object", "properties": {
            "message_id": {"type": "integer", "description": "Id from list_messages"}}, "required": ["message_id"]}}},
]

CAPACITY = 5
STORED = [(1, "Bank", "Your statement is ready."), (2, "Ravi", "Lunch on Friday?"), (3, "Courier", "Parcel delivered."),
          (4, "Maya", "See you at six."), (5, "Gym", "Membership renews next week.")]


def new_state(scenario):
    full = scenario == "two-faults"
    return {"wifi": scenario in ("no-fault", "no-fix"), "suspended": scenario == "no-fix",
            "messages": list(STORED if full else STORED[:2]), "sent": []}


def as_bool(v):
    return v if isinstance(v, bool) else str(v).strip().lower() in ("true", "1", "on", "yes")


def execute(state, name, args):
    """Returns (result, changed): the tool's JSON result and whether the simulated state changed."""
    if name == "send_message":
        if not isinstance(args.get("to"), str) or not isinstance(args.get("text"), str):
            return {"ok": False, "error": "Invalid arguments: 'to' and 'text' are required strings."}, False
        if not state["wifi"]:
            return {"ok": False, "error": "Network unavailable: Wi-Fi is off."}, False
        if state["suspended"]:
            return {"ok": False, "error": "Carrier rejected the message: this account is suspended. Contact the carrier."}, False
        if len(state["messages"]) >= CAPACITY:
            return {"ok": False, "error": f"Message storage is full ({CAPACITY} of {CAPACITY}). Delete a message to free space."}, False
        state["sent"].append({"to": args["to"], "text": args["text"]})
        state["messages"].append((max((m[0] for m in state["messages"]), default=0) + 1, "me", args["text"]))
        return {"ok": True, "status": "sent"}, True
    if name == "set_wifi":
        if "enabled" not in args:
            return {"ok": False, "error": "Invalid arguments: 'enabled' is required."}, False
        on = as_bool(args["enabled"])
        changed = on != state["wifi"]
        state["wifi"] = on
        return {"ok": True, "wifi": "on" if on else "off"}, changed
    if name == "get_device_status":
        return {"ok": True, "wifi": "on" if state["wifi"] else "off",
                "message_storage": f"{len(state['messages'])} of {CAPACITY}"}, False
    if name == "list_messages":
        return {"ok": True, "messages": [{"id": i, "from": f, "text": t} for i, f, t in state["messages"]]}, False
    if name == "delete_message":
        try:
            mid = int(args.get("message_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Invalid arguments: 'message_id' must be an integer."}, False
        before = len(state["messages"])
        state["messages"] = [m for m in state["messages"] if m[0] != mid]
        if len(state["messages"]) == before:
            return {"ok": False, "error": f"No message with id {mid}."}, False
        return {"ok": True, "deleted": mid}, True
    return {"ok": False, "error": f"Unknown tool: {name}"}, False


def chat(base, messages, seed):
    body = json.dumps({"model": "local", "messages": messages, "tools": TOOLS, "seed": seed, **SAMPLING}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.load(r)


def run(base, scenario, seed):
    state = new_state(scenario)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}]
    turns, calls, t0 = [], [], time.time()
    tokens, stop, error = 0, "max-turns", None
    for _ in range(MAX_TURNS):
        try:
            resp = chat(base, messages, seed)
        except Exception as e:  # a malformed tool call can make the server reject the turn; record it as an outcome
            stop, error = "server-error", str(e)[:300]
            break
        tokens += resp.get("usage", {}).get("completion_tokens", 0)
        msg = resp["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []
        turns.append({"reasoning": msg.get("reasoning_content"), "content": msg.get("content"),
                      "tool_calls": [{"name": c["function"]["name"], "arguments": c["function"]["arguments"]} for c in tool_calls],
                      "finish_reason": resp["choices"][0].get("finish_reason")})
        if not tool_calls:
            stop = "answered"
            break
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls})
        for c in tool_calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"]["arguments"] or "{}")
                if not isinstance(args, dict):
                    raise ValueError
                result, changed = execute(state, name, args)
            except ValueError:
                args, (result, changed) = None, ({"ok": False, "error": "Arguments are not a JSON object."}, False)
            calls.append({"name": name, "args": args, "ok": result["ok"], "error": result.get("error"), "changed": changed})
            messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": json.dumps(result)})

    # A repeat is a failed send_message that follows an earlier failed send_message with the same error and no state
    # change in between: the model asked again for something it had just been told cannot work.
    repeats, last_err, dirty = 0, None, True
    for c in calls:
        if c["changed"]:
            dirty = True
        if c["name"] == "send_message" and not c["ok"]:
            if not dirty and c["error"] == last_err:
                repeats += 1
            last_err, dirty = c["error"], False
    sent = [s for s in state["sent"] if "maya" in s["to"].lower() and "ten minutes late" in s["text"].lower()]
    return {"scenario": scenario, "seed": seed, "stop": stop, "error": error,
            "sent_correct": len(sent), "sent_total": len(state["sent"]),
            "repeated_failed_sends": repeats, "failed_sends": sum(1 for c in calls if c["name"] == "send_message" and not c["ok"]),
            "tool_calls": len(calls), "assistant_turns": len(turns), "completion_tokens": tokens,
            "seconds": round(time.time() - t0, 1), "final_wifi": state["wifi"], "final_stored": len(state["messages"]),
            "calls": calls, "turns": turns}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("label")
    ap.add_argument("out")
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--scenarios", default="two-faults,one-fault,no-fault,no-fix")
    a = ap.parse_args()
    with open(a.out, "a") as f:
        for scenario in a.scenarios.split(","):
            for seed in range(1, a.trials + 1):
                r = {"model": a.label, **run(a.base, scenario, seed)}
                f.write(json.dumps(r) + "\n")
                f.flush()
                print(a.label, scenario, seed, r["stop"], "sent", r["sent_correct"], "repeats", r["repeated_failed_sends"],
                      "calls", r["tool_calls"], f"{r['seconds']}s", flush=True)


if __name__ == "__main__":
    main()
