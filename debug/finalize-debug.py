#!/usr/bin/env python3
"""
Compile a JSONL debug session log into a structured JSON report.

Pairs pre/post events, detects parallel vs sequential execution,
computes durations, and builds summary statistics.

Usage: python3 finalize-debug.py <jsonl_file> [output_json]
"""

import json
import sys
import os
from collections import defaultdict
from datetime import datetime


PARALLEL_THRESHOLD_MS = 500  # events within this window are considered parallel


def load_events(path):
    events = []
    with open(path) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
                evt["_line"] = i
                events.append(evt)
            except json.JSONDecodeError as e:
                events.append({"_line": i, "_parse_error": str(e), "_raw": line})
    return events


def pair_events(events):
    """Match pre events with their corresponding post events."""
    paired = []
    pre_stack = {}  # tool_name -> list of unmatched pre events

    for evt in events:
        phase = evt.get("phase")
        tool = evt.get("tool_name", "unknown")
        key = tool

        # For Agent calls, use description to distinguish parallel agents
        if tool == "Agent":
            desc = evt.get("agent_metadata", {}).get("description", "")
            key = f"Agent:{desc}"

        if phase == "pre":
            pre_stack.setdefault(key, []).append(evt)

        elif phase == "post":
            pre_evt = None
            if key in pre_stack and pre_stack[key]:
                pre_evt = pre_stack[key].pop(0)

            duration_ms = None
            if pre_evt:
                duration_ms = evt.get("epoch_ms", 0) - pre_evt.get("epoch_ms", 0)

            paired_event = {
                "tool_name": tool,
                "start_time": pre_evt.get("timestamp") if pre_evt else None,
                "end_time": evt.get("timestamp"),
                "start_epoch_ms": pre_evt.get("epoch_ms") if pre_evt else None,
                "end_epoch_ms": evt.get("epoch_ms"),
                "duration_ms": duration_ms,
                "tool_input": evt.get("tool_input", {}),
                "tool_output": evt.get("tool_output"),
                "output_size_bytes": evt.get("output_size_bytes"),
                "execution_mode": None,  # filled in detect_parallel
                "concurrent_group": None,
                "pid": evt.get("pid"),
                "ppid": evt.get("ppid"),
            }

            # Copy any tool-specific metadata
            for meta_key in [
                "agent_metadata", "search_query", "fetch_url",
                "write_metadata", "read_metadata", "bash_metadata",
                "edit_metadata", "search_metadata", "skill_metadata",
                "question_metadata",
            ]:
                if meta_key in evt:
                    paired_event[meta_key] = evt[meta_key]
                elif pre_evt and meta_key in pre_evt:
                    paired_event[meta_key] = pre_evt[meta_key]

            paired.append(paired_event)

    # Any unmatched pre events (tool call started but no post — e.g., crash or timeout)
    for key, remaining in pre_stack.items():
        for pre_evt in remaining:
            paired.append({
                "tool_name": pre_evt.get("tool_name", "unknown"),
                "start_time": pre_evt.get("timestamp"),
                "end_time": None,
                "start_epoch_ms": pre_evt.get("epoch_ms"),
                "end_epoch_ms": None,
                "duration_ms": None,
                "tool_input": pre_evt.get("tool_input", {}),
                "tool_output": None,
                "output_size_bytes": None,
                "execution_mode": "unknown",
                "concurrent_group": None,
                "status": "unmatched_pre",
                "pid": pre_evt.get("pid"),
                "ppid": pre_evt.get("ppid"),
            })

    # Sort by start time
    paired.sort(key=lambda e: e.get("start_epoch_ms") or 0)
    return paired


def detect_parallel(paired_events):
    """
    Detect parallel vs sequential execution by analyzing overlapping time windows.
    Events whose start times fall within PARALLEL_THRESHOLD_MS of each other
    AND overlap in execution time are marked as parallel.
    """
    group_id = 0
    n = len(paired_events)

    for i in range(n):
        if paired_events[i].get("concurrent_group") is not None:
            continue

        start_i = paired_events[i].get("start_epoch_ms")
        end_i = paired_events[i].get("end_epoch_ms")
        if start_i is None:
            paired_events[i]["execution_mode"] = "unknown"
            continue

        # Find all events that overlap with this one
        group_members = [i]

        for j in range(i + 1, n):
            start_j = paired_events[j].get("start_epoch_ms")
            end_j = paired_events[j].get("end_epoch_ms")
            if start_j is None:
                continue

            # Check if j starts while i is still running, or starts very close to i
            starts_close = abs(start_j - start_i) <= PARALLEL_THRESHOLD_MS
            overlaps = (end_i is not None and start_j < end_i)

            if starts_close or overlaps:
                group_members.append(j)

        if len(group_members) > 1:
            for idx in group_members:
                paired_events[idx]["execution_mode"] = "parallel"
                paired_events[idx]["concurrent_group"] = group_id
            group_id += 1
        else:
            paired_events[i]["execution_mode"] = "sequential"

    return group_id  # number of parallel groups


def build_summary(paired_events, raw_events):
    """Build aggregate statistics."""
    tool_stats = defaultdict(lambda: {"count": 0, "total_ms": 0, "errors": 0})
    agent_runs = []

    for evt in paired_events:
        tool = evt.get("tool_name", "unknown")
        dur = evt.get("duration_ms") or 0
        tool_stats[tool]["count"] += 1
        tool_stats[tool]["total_ms"] += dur

        if evt.get("tool_output") and "error" in str(evt["tool_output"]).lower()[:200]:
            tool_stats[tool]["errors"] += 1

        if tool == "Agent":
            meta = evt.get("agent_metadata", {})
            agent_runs.append({
                "subagent_type": meta.get("subagent_type", "unknown"),
                "description": meta.get("description", ""),
                "model": meta.get("model"),
                "start_time": evt.get("start_time"),
                "end_time": evt.get("end_time"),
                "duration_ms": evt.get("duration_ms"),
                "execution_mode": evt.get("execution_mode"),
                "concurrent_group": evt.get("concurrent_group"),
                "prompt_length": meta.get("prompt_length", 0),
            })

    # Count parallel groups
    groups = set()
    for evt in paired_events:
        g = evt.get("concurrent_group")
        if g is not None:
            groups.add(g)

    parallel_count = sum(1 for e in paired_events if e.get("execution_mode") == "parallel")
    sequential_count = sum(1 for e in paired_events if e.get("execution_mode") == "sequential")

    # Timeline: first and last timestamps
    timestamps = [e.get("epoch_ms", 0) for e in raw_events if e.get("epoch_ms")]
    start_ms = min(timestamps) if timestamps else 0
    end_ms = max(timestamps) if timestamps else 0

    return {
        "total_tool_calls": len(paired_events),
        "total_raw_events": len(raw_events),
        "parallel_groups": len(groups),
        "parallel_tool_calls": parallel_count,
        "sequential_tool_calls": sequential_count,
        "session_duration_ms": end_ms - start_ms,
        "tools": {k: dict(v) for k, v in sorted(tool_stats.items())},
        "agent_runs": agent_runs,
    }


def build_timeline(paired_events):
    """Build a human-readable timeline of key events."""
    timeline = []
    for evt in paired_events:
        entry = {
            "time": evt.get("start_time", ""),
            "tool": evt.get("tool_name", ""),
            "duration_ms": evt.get("duration_ms"),
            "mode": evt.get("execution_mode", ""),
        }

        tool = evt.get("tool_name", "")
        if tool == "Agent":
            meta = evt.get("agent_metadata", {})
            entry["detail"] = f"[{meta.get('subagent_type', '')}] {meta.get('description', '')}"
        elif tool == "WebSearch":
            entry["detail"] = evt.get("search_query", "")
        elif tool == "WebFetch":
            entry["detail"] = evt.get("fetch_url", "")
        elif tool == "Write":
            meta = evt.get("write_metadata", {})
            entry["detail"] = f"{meta.get('file_path', '')} ({meta.get('content_length', 0)} chars)"
        elif tool == "Read":
            meta = evt.get("read_metadata", {})
            entry["detail"] = meta.get("file_path", "")
        elif tool == "Bash":
            meta = evt.get("bash_metadata", {})
            entry["detail"] = meta.get("command", "")[:200]
        elif tool == "Skill":
            meta = evt.get("skill_metadata", {})
            entry["detail"] = f"/{meta.get('skill', '')} {meta.get('args', '')}"
        elif tool == "AskUserQuestion":
            meta = evt.get("question_metadata", {})
            entry["detail"] = meta.get("question", "")[:200]
        else:
            entry["detail"] = ""

        timeline.append(entry)

    return timeline


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 finalize-debug.py <session.jsonl> [output.json]")
        sys.exit(1)

    jsonl_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else jsonl_path.replace(".jsonl", ".json")

    if not os.path.exists(jsonl_path):
        print(f"Error: {jsonl_path} not found")
        sys.exit(1)

    print(f"Loading events from {jsonl_path}...")
    raw_events = load_events(jsonl_path)
    print(f"  {len(raw_events)} raw events loaded")

    print("Pairing pre/post events...")
    paired = pair_events(raw_events)
    print(f"  {len(paired)} tool calls paired")

    print("Detecting parallel execution...")
    num_groups = detect_parallel(paired)
    print(f"  {num_groups} parallel groups detected")

    print("Building summary...")
    summary = build_summary(paired, raw_events)

    print("Building timeline...")
    timeline = build_timeline(paired)

    # Session metadata
    timestamps = [e.get("epoch_ms", 0) for e in raw_events if e.get("epoch_ms")]
    session = {
        "log_file": jsonl_path,
        "start_time": raw_events[0].get("timestamp") if raw_events else None,
        "end_time": raw_events[-1].get("timestamp") if raw_events else None,
        "duration_ms": (max(timestamps) - min(timestamps)) if timestamps else 0,
    }

    result = {
        "session": session,
        "summary": summary,
        "timeline": timeline,
        "tool_calls": paired,
        "raw_events": raw_events,
    }

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"\nDebug report written to: {output_path}")
    print(f"  Session duration: {summary['session_duration_ms'] / 1000:.1f}s")
    print(f"  Tool calls: {summary['total_tool_calls']}")
    print(f"  Parallel groups: {summary['parallel_groups']}")
    print(f"  Agent runs: {len(summary['agent_runs'])}")
    print()

    # Print tool breakdown
    print("  Tool breakdown:")
    for tool, stats in summary["tools"].items():
        avg = stats["total_ms"] / stats["count"] if stats["count"] else 0
        err = f" ({stats['errors']} errors)" if stats["errors"] else ""
        print(f"    {tool:20s}  {stats['count']:3d} calls  {stats['total_ms']:8d}ms total  {avg:7.0f}ms avg{err}")


if __name__ == "__main__":
    main()
