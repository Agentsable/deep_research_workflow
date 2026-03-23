#!/usr/bin/env python3
"""
Generate a timestamp-sorted CSV report from a finalized debug JSON file.

Produces two CSV files:
  1. <name>-events.csv   — every tool call, one row per event, sorted by timestamp
  2. <name>-summary.csv  — aggregated stats by tool, agent, and parallel group

Columns track: timestamps, durations, execution mode (parallel/sequential),
agent context, token estimates, input/output sizes, and tool-specific details.

Usage: python3 generate-csv.py <debug.json> [output_dir]
  If output_dir is omitted, CSVs are written next to the JSON file.
"""

import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime

# ── Token estimation ────────────────────────────────────────────────
# Claude tokenizer averages ~4 chars per token for English text.
# We use this as a rough estimate since we don't have the real tokenizer.
CHARS_PER_TOKEN = 4


def estimate_tokens(text):
    """Estimate token count from text length."""
    if text is None:
        return 0
    if not isinstance(text, str):
        text = json.dumps(text, default=str)
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def safe_str(val, max_len=500):
    """Safely convert a value to a truncated string for CSV cells."""
    if val is None:
        return ""
    s = str(val)
    if len(s) > max_len:
        return s[:max_len] + f"...[{len(s)} chars]"
    return s


def format_ts(iso_str):
    """Format ISO timestamp to readable form."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    except Exception:
        return iso_str


def elapsed_since_start(epoch_ms, session_start_ms):
    """Seconds elapsed since session start."""
    if not epoch_ms or not session_start_ms:
        return ""
    return round((epoch_ms - session_start_ms) / 1000, 2)


def get_detail(evt):
    """Extract a human-readable detail string for the event."""
    tool = evt.get("tool_name", "")

    if tool == "Agent":
        meta = evt.get("agent_metadata", {})
        return f"[{meta.get('subagent_type', '')}] {meta.get('description', '')}"
    if tool == "WebSearch":
        return evt.get("search_query", "")
    if tool == "WebFetch":
        return evt.get("fetch_url", "")
    if tool == "Write":
        meta = evt.get("write_metadata", {})
        return meta.get("file_path", "")
    if tool == "Read":
        meta = evt.get("read_metadata", {})
        return meta.get("file_path", "")
    if tool == "Bash":
        meta = evt.get("bash_metadata", {})
        return meta.get("command", "")[:300]
    if tool == "Edit":
        meta = evt.get("edit_metadata", {})
        return meta.get("file_path", "")
    if tool in ("Glob", "Grep"):
        meta = evt.get("search_metadata", {})
        return f"{meta.get('pattern', '')} in {meta.get('path', '')}"
    if tool == "Skill":
        meta = evt.get("skill_metadata", {})
        return f"/{meta.get('skill', '')} {meta.get('args', '')}"
    if tool == "AskUserQuestion":
        meta = evt.get("question_metadata", {})
        return meta.get("question", "")[:300]

    return ""


def compute_input_size(evt):
    """Compute total input size in bytes."""
    tool_input = evt.get("tool_input", {})
    if not tool_input:
        return 0
    return len(json.dumps(tool_input, default=str).encode("utf-8"))


def compute_output_size(evt):
    """Compute total output size in bytes."""
    if evt.get("output_size_bytes"):
        return evt["output_size_bytes"]
    output = evt.get("tool_output")
    if output is None:
        return 0
    if isinstance(output, str):
        return len(output.encode("utf-8"))
    return len(json.dumps(output, default=str).encode("utf-8"))


def classify_event(evt):
    """Classify event into high-level category."""
    tool = evt.get("tool_name", "")
    if tool == "Agent":
        return "agent_call"
    if tool in ("WebSearch", "WebFetch"):
        return "web_io"
    if tool in ("Read", "Write", "Edit", "Glob", "Grep", "Bash"):
        return "local_tool"
    if tool == "Skill":
        return "skill"
    if tool == "AskUserQuestion":
        return "user_interaction"
    return "other"


def get_agent_context(evt):
    """Determine which agent context this event belongs to."""
    tool = evt.get("tool_name", "")
    if tool == "Agent":
        meta = evt.get("agent_metadata", {})
        return f"orchestrator→{meta.get('subagent_type', 'unknown')}"
    # For non-Agent tools, we use PID to group — the CSV consumer can
    # correlate PIDs with agent launches from the Agent rows.
    return ""


def generate_events_csv(data, output_path):
    """Generate the main events CSV sorted by timestamp."""
    tool_calls = data.get("tool_calls", [])
    session = data.get("session", {})

    # Find session start for elapsed time calculation
    session_start_ms = None
    if tool_calls:
        starts = [e.get("start_epoch_ms") for e in tool_calls if e.get("start_epoch_ms")]
        if starts:
            session_start_ms = min(starts)

    fields = [
        "row",
        "timestamp",
        "elapsed_sec",
        "tool_name",
        "category",
        "execution_mode",
        "concurrent_group",
        "duration_ms",
        "duration_sec",
        "agent_type",
        "agent_description",
        "agent_model",
        "agent_prompt_length",
        "input_size_bytes",
        "output_size_bytes",
        "tokens_sent_est",
        "tokens_received_est",
        "tokens_total_est",
        "pid",
        "ppid",
        "detail",
        "start_time",
        "end_time",
        "status",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()

        for i, evt in enumerate(tool_calls, 1):
            input_bytes = compute_input_size(evt)
            output_bytes = compute_output_size(evt)
            tokens_sent = estimate_tokens(json.dumps(evt.get("tool_input", {}), default=str))
            tokens_recv = estimate_tokens(evt.get("tool_output", ""))
            duration_ms = evt.get("duration_ms")

            agent_meta = evt.get("agent_metadata", {})

            row = {
                "row": i,
                "timestamp": format_ts(evt.get("start_time")),
                "elapsed_sec": elapsed_since_start(
                    evt.get("start_epoch_ms"), session_start_ms
                ),
                "tool_name": evt.get("tool_name", ""),
                "category": classify_event(evt),
                "execution_mode": evt.get("execution_mode", ""),
                "concurrent_group": evt.get("concurrent_group", ""),
                "duration_ms": duration_ms if duration_ms is not None else "",
                "duration_sec": round(duration_ms / 1000, 2) if duration_ms else "",
                "agent_type": agent_meta.get("subagent_type", ""),
                "agent_description": agent_meta.get("description", ""),
                "agent_model": agent_meta.get("model", ""),
                "agent_prompt_length": agent_meta.get("prompt_length", ""),
                "input_size_bytes": input_bytes,
                "output_size_bytes": output_bytes,
                "tokens_sent_est": tokens_sent,
                "tokens_received_est": tokens_recv,
                "tokens_total_est": tokens_sent + tokens_recv,
                "pid": evt.get("pid", ""),
                "ppid": evt.get("ppid", ""),
                "detail": safe_str(get_detail(evt), 500),
                "start_time": format_ts(evt.get("start_time")),
                "end_time": format_ts(evt.get("end_time")),
                "status": evt.get("status", "ok"),
            }

            writer.writerow(row)

    return len(tool_calls)


def generate_summary_csv(data, output_path):
    """Generate a multi-section summary CSV with aggregate stats."""
    summary = data.get("summary", {})
    tool_calls = data.get("tool_calls", [])
    session = data.get("session", {})

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)

        # ── Section 1: Session overview ──
        writer.writerow(["=== SESSION OVERVIEW ==="])
        writer.writerow(["metric", "value"])
        writer.writerow(["start_time", format_ts(session.get("start_time"))])
        writer.writerow(["end_time", format_ts(session.get("end_time"))])
        writer.writerow(["duration_sec", round(summary.get("session_duration_ms", 0) / 1000, 1)])
        writer.writerow(["total_tool_calls", summary.get("total_tool_calls", 0)])
        writer.writerow(["total_raw_events", summary.get("total_raw_events", 0)])
        writer.writerow(["parallel_groups", summary.get("parallel_groups", 0)])
        writer.writerow(["parallel_tool_calls", summary.get("parallel_tool_calls", 0)])
        writer.writerow(["sequential_tool_calls", summary.get("sequential_tool_calls", 0)])

        # Total tokens
        total_sent = 0
        total_recv = 0
        total_input_bytes = 0
        total_output_bytes = 0
        for evt in tool_calls:
            total_input_bytes += compute_input_size(evt)
            total_output_bytes += compute_output_size(evt)
            total_sent += estimate_tokens(json.dumps(evt.get("tool_input", {}), default=str))
            total_recv += estimate_tokens(evt.get("tool_output", ""))

        writer.writerow(["total_input_bytes", total_input_bytes])
        writer.writerow(["total_output_bytes", total_output_bytes])
        writer.writerow(["total_tokens_sent_est", total_sent])
        writer.writerow(["total_tokens_received_est", total_recv])
        writer.writerow(["total_tokens_est", total_sent + total_recv])
        writer.writerow([])

        # ── Section 2: Per-tool breakdown ──
        writer.writerow(["=== TOOL BREAKDOWN ==="])
        writer.writerow([
            "tool", "call_count", "total_ms", "avg_ms", "min_ms", "max_ms",
            "total_input_bytes", "total_output_bytes",
            "tokens_sent_est", "tokens_recv_est",
            "errors", "parallel_pct",
        ])

        tool_events = defaultdict(list)
        for evt in tool_calls:
            tool_events[evt.get("tool_name", "unknown")].append(evt)

        for tool in sorted(tool_events.keys()):
            evts = tool_events[tool]
            durations = [e.get("duration_ms", 0) or 0 for e in evts]
            t_input = sum(compute_input_size(e) for e in evts)
            t_output = sum(compute_output_size(e) for e in evts)
            t_sent = sum(estimate_tokens(json.dumps(e.get("tool_input", {}), default=str)) for e in evts)
            t_recv = sum(estimate_tokens(e.get("tool_output", "")) for e in evts)
            errors = sum(1 for e in evts if e.get("tool_output") and "error" in str(e["tool_output"]).lower()[:200])
            par = sum(1 for e in evts if e.get("execution_mode") == "parallel")
            par_pct = round(par / len(evts) * 100) if evts else 0

            writer.writerow([
                tool,
                len(evts),
                sum(durations),
                round(sum(durations) / len(evts)) if evts else 0,
                min(durations) if durations else 0,
                max(durations) if durations else 0,
                t_input,
                t_output,
                t_sent,
                t_recv,
                errors,
                f"{par_pct}%",
            ])

        writer.writerow([])

        # ── Section 3: Agent runs ──
        writer.writerow(["=== AGENT RUNS ==="])
        writer.writerow([
            "agent_num", "subagent_type", "description", "model",
            "start_time", "end_time", "duration_sec",
            "execution_mode", "concurrent_group",
            "prompt_tokens_est",
        ])

        agent_runs = summary.get("agent_runs", [])
        for i, agent in enumerate(agent_runs, 1):
            dur_ms = agent.get("duration_ms") or 0
            writer.writerow([
                i,
                agent.get("subagent_type", ""),
                safe_str(agent.get("description", ""), 200),
                agent.get("model", ""),
                format_ts(agent.get("start_time")),
                format_ts(agent.get("end_time")),
                round(dur_ms / 1000, 1),
                agent.get("execution_mode", ""),
                agent.get("concurrent_group", ""),
                estimate_tokens("x" * agent.get("prompt_length", 0)),
            ])

        writer.writerow([])

        # ── Section 4: Parallel groups ──
        writer.writerow(["=== PARALLEL GROUPS ==="])
        writer.writerow([
            "group_id", "member_count", "tools_in_group",
            "group_start", "group_end", "wall_time_ms",
            "cumulative_ms", "parallelism_factor",
        ])

        groups = defaultdict(list)
        for evt in tool_calls:
            g = evt.get("concurrent_group")
            if g is not None:
                groups[g].append(evt)

        for gid in sorted(groups.keys()):
            members = groups[gid]
            tools = ", ".join(sorted(set(e.get("tool_name", "") for e in members)))
            starts = [e.get("start_epoch_ms", 0) for e in members if e.get("start_epoch_ms")]
            ends = [e.get("end_epoch_ms", 0) for e in members if e.get("end_epoch_ms")]
            wall = (max(ends) - min(starts)) if starts and ends else 0
            cumulative = sum(e.get("duration_ms", 0) or 0 for e in members)
            factor = round(cumulative / wall, 2) if wall > 0 else 0

            writer.writerow([
                gid,
                len(members),
                tools,
                format_ts(members[0].get("start_time")) if members else "",
                format_ts(members[-1].get("end_time")) if members else "",
                wall,
                cumulative,
                f"{factor}x",
            ])

        writer.writerow([])

        # ── Section 5: Time distribution ──
        writer.writerow(["=== TIME DISTRIBUTION ==="])
        writer.writerow(["category", "total_ms", "pct_of_session", "call_count"])

        session_ms = summary.get("session_duration_ms", 1)
        cat_stats = defaultdict(lambda: {"ms": 0, "count": 0})

        for evt in tool_calls:
            cat = classify_event(evt)
            cat_stats[cat]["ms"] += evt.get("duration_ms", 0) or 0
            cat_stats[cat]["count"] += 1

        for cat in sorted(cat_stats.keys()):
            st = cat_stats[cat]
            pct = round(st["ms"] / session_ms * 100, 1) if session_ms else 0
            writer.writerow([cat, st["ms"], f"{pct}%", st["count"]])

        writer.writerow([])

        # ── Section 6: Slowest calls ──
        writer.writerow(["=== TOP 20 SLOWEST CALLS ==="])
        writer.writerow(["rank", "tool_name", "duration_sec", "execution_mode", "detail"])

        by_duration = sorted(
            tool_calls,
            key=lambda e: e.get("duration_ms", 0) or 0,
            reverse=True,
        )

        for i, evt in enumerate(by_duration[:20], 1):
            dur = evt.get("duration_ms", 0) or 0
            writer.writerow([
                i,
                evt.get("tool_name", ""),
                round(dur / 1000, 2),
                evt.get("execution_mode", ""),
                safe_str(get_detail(evt), 200),
            ])

    return len(tool_calls)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate-csv.py <debug.json> [output_dir]")
        print()
        print("Generates two CSV files from a finalized debug JSON report:")
        print("  *-events.csv   — every tool call, timestamp-sorted")
        print("  *-summary.csv  — aggregate stats, agent runs, parallel groups")
        sys.exit(1)

    json_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(json_path)

    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading debug report from {json_path}...")
    with open(json_path) as f:
        data = json.load(f)

    basename = os.path.splitext(os.path.basename(json_path))[0]
    events_csv = os.path.join(output_dir, f"{basename}-events.csv")
    summary_csv = os.path.join(output_dir, f"{basename}-summary.csv")

    print(f"Generating events CSV...")
    n_events = generate_events_csv(data, events_csv)
    print(f"  {events_csv} ({n_events} rows)")

    print(f"Generating summary CSV...")
    generate_summary_csv(data, summary_csv)
    print(f"  {summary_csv}")

    # Print quick stats to terminal
    summary = data.get("summary", {})
    tool_calls = data.get("tool_calls", [])
    session = data.get("session", {})

    total_sent = sum(
        estimate_tokens(json.dumps(e.get("tool_input", {}), default=str))
        for e in tool_calls
    )
    total_recv = sum(
        estimate_tokens(e.get("tool_output", ""))
        for e in tool_calls
    )

    print()
    print("Quick stats:")
    print(f"  Session duration:     {summary.get('session_duration_ms', 0) / 1000:.1f}s")
    print(f"  Total tool calls:     {summary.get('total_tool_calls', 0)}")
    print(f"  Parallel groups:      {summary.get('parallel_groups', 0)}")
    print(f"  Agent launches:       {len(summary.get('agent_runs', []))}")
    print(f"  Est. tokens sent:     {total_sent:,}")
    print(f"  Est. tokens received: {total_recv:,}")
    print(f"  Est. tokens total:    {total_sent + total_recv:,}")


if __name__ == "__main__":
    main()
