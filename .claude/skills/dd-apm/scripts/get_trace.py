#!/usr/bin/env python3
"""Fetch all spans for one trace and render them as a tree.

Wraps POST /api/v2/spans/events/search filtered by trace_id. Prints a tree
showing span hierarchy, durations, and errors. Use --raw for raw spans JSON.

Note: the "logs to traces" pivot — copy the trace_id from a log event in
dd-logs and pass it here.
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dd-setup" / "scripts"))
from dd_client import dd_post, parse_time_iso, run_or_exit, print_json, web_url  # noqa: E402


def _build_tree(spans: list[dict]) -> tuple[list, dict]:
    by_id = {s["span_id"]: s for s in spans}
    children: dict[str, list[str]] = {}
    roots: list[str] = []
    for s in spans:
        parent = s.get("parent_id")
        if parent and parent in by_id and parent != s["span_id"]:
            children.setdefault(parent, []).append(s["span_id"])
        else:
            roots.append(s["span_id"])
    for sids in children.values():
        sids.sort(key=lambda i: by_id[i].get("timestamp_ns") or 0)
    roots.sort(key=lambda i: by_id[i].get("timestamp_ns") or 0)
    return roots, children


def _format_tree(roots, children, by_id, prefix: str = "", lines=None) -> list[str]:
    if lines is None:
        lines = []
    for i, span_id in enumerate(roots):
        is_last = i == len(roots) - 1
        connector = "+-- " if is_last else "|-- "
        s = by_id[span_id]
        err = " [ERROR]" if s["error"] else ""
        dur = f" {s['duration_ms']:>7.1f}ms" if s["duration_ms"] is not None else "      n/a"
        lines.append(
            f"{prefix}{connector}{dur}  {s['service']} {s['operation']}  "
            f"{s['resource'][:60] if s['resource'] else ''}{err}"
        )
        new_prefix = prefix + ("    " if is_last else "|   ")
        _format_tree(children.get(span_id, []), children, by_id, new_prefix, lines)
    return lines


def _trim(span: dict) -> dict:
    a = span.get("attributes", {}) or {}
    custom = a.get("custom", {}) or {}
    duration_ns = a.get("duration") or 0
    return {
        "span_id": a.get("span_id"),
        "parent_id": a.get("parent_id"),
        "trace_id": a.get("trace_id"),
        "service": a.get("service"),
        "operation": a.get("operation_name") or a.get("name"),
        "resource": a.get("resource_name"),
        "timestamp_ns": a.get("start_timestamp_ns") or a.get("start_timestamp"),
        "duration_ns": duration_ns,
        "duration_ms": round(duration_ns / 1_000_000, 2) if duration_ns else None,
        "error": bool(a.get("status") == "error" or custom.get("error.message")),
        "error_message": (custom.get("error.message") or "")[:300] or None,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trace-id", required=True, help="Trace ID to fetch")
    p.add_argument("--from", dest="frm", default="now-1h",
                   help="Search window start. Default: now-1h. Widen if no spans found.")
    p.add_argument("--to", default="now", help="End. Default: now")
    p.add_argument("--limit", type=int, default=500,
                   help="Max spans to fetch (max 1000). Default: 500")
    p.add_argument("--raw", action="store_true", help="Print spans as JSON instead of tree")
    args = p.parse_args()

    body = {
        "filter": {
            "query": f"trace_id:{args.trace_id}",
            "from": parse_time_iso(args.frm),
            "to": parse_time_iso(args.to),
        },
        "page": {"limit": min(args.limit, 1000)},
        "sort": "timestamp",
    }
    resp = run_or_exit(lambda: dd_post("/api/v2/spans/events/search", body))

    spans = [_trim(s) for s in resp.get("data", [])]
    if not spans:
        sys.stderr.write(
            f"No spans found for trace_id={args.trace_id} in window {args.frm} -> {args.to}.\n"
            "  -> Trace may have aged out of the search index (default retention is 15 days).\n"
            "  -> Or the window is too narrow. Try --from now-24h.\n"
        )
        return 1

    by_id = {s["span_id"]: s for s in spans}
    roots, children = _build_tree(spans)
    total_dur_ms = max((s["duration_ms"] for s in spans if s["duration_ms"] is not None), default=0)
    error_count = sum(1 for s in spans if s["error"])

    if args.raw:
        print_json({
            "trace_id": args.trace_id,
            "span_count": len(spans),
            "error_count": error_count,
            "total_duration_ms": total_dur_ms,
            "spans": spans,
        })
    else:
        print(f"Trace {args.trace_id}")
        print(f"  spans:    {len(spans)}")
        print(f"  errors:   {error_count}")
        print(f"  total:    {total_dur_ms:.1f}ms (root span)")
        print(f"  url:      {web_url(f'/apm/trace/{args.trace_id}')}")
        print()
        for line in _format_tree(roots, children, by_id):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
