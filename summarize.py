#!/usr/bin/env python3
"""summarize.py <results-dir>: per model and scenario counts from harness.py output, as JSON on stdout."""
import collections
import json
import statistics as st
import sys

out = {}
for model in ("botpsy", "base"):
    by = collections.defaultdict(list)
    for line in open(f"{sys.argv[1]}/{model}.jsonl"):
        r = json.loads(line)
        by[r["scenario"]].append(r)
    for scenario, rs in by.items():
        out[f"{model}/{scenario}"] = {
            "runs": len(rs),
            "message_sent": sum(r["sent_correct"] > 0 for r in rs),
            "sent_more_than_once": sum(r["sent_total"] > 1 for r in rs),
            "runs_with_a_repeated_failed_send": sum(r["repeated_failed_sends"] > 0 for r in rs),
            "repeated_failed_sends": sum(r["repeated_failed_sends"] for r in rs),
            "stopped_after_first_failure": sum(r["failed_sends"] == 1 and r["tool_calls"] == 1 and r["stop"] == "answered" for r in rs),
            "stop": dict(collections.Counter(r["stop"] for r in rs)),
            "median_tool_calls": st.median(r["tool_calls"] for r in rs),
            "median_seconds": st.median(r["seconds"] for r in rs),
            "median_completion_tokens": st.median(r["completion_tokens"] for r in rs),
        }
json.dump(out, sys.stdout, indent=1)
