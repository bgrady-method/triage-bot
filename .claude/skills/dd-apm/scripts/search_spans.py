#!/usr/bin/env python3
"""Search Datadog APM spans.

Wraps POST /api/v2/spans/events/search. Default window: now-15m.
Default output: trimmed JSON (timestamp, service, resource, duration_ms, error, trace_id, span_id).
Use --raw for the full payload.

Examples:
  # Slowest spans for a service
  python search_spans.py --query "service:tables-fields @duration:>1000000000" --from now-15m

  # Errored spans
  python search_spans.py --query "service:tables-fields status:error"

  # All spans in a trace
  python search_spans.py --query "trace_id:abc123def456" --limit 200
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dd-setup" / "scripts"))
from dd_client import dd_post, parse_time_iso, run_or_exit, print_json  # noqa: E402


def _trim(span: dict) -> dict:
    a = span.get("attributes", {}) or {}
    custom = a.get("custom", {}) or {}
    duration_ns = a.get("duration") or 0
    return {
        "timestamp": a.get("start_timestamp") or a.get("timestamp"),
        "service": a.get("service"),
        "resource": a.get("resource_name"),
        "operation": a.get("operation_name") or a.get("name"),
        "duration_ms": round(duration_ns / 1_000_000, 2) if duration_ns else None,
        "error": bool(a.get("status") == "error" or custom.get("error.message")),
        "error_message": (custom.get("error.message") or "")[:200] or None,
        "host": a.get("host"),
        "trace_id": a.get("trace_id"),
        "span_id": a.get("span_id"),
        "parent_id": a.get("parent_id"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", required=True, help="Datadog APM search query")
    p.add_argument("--from", dest="frm", default="now-15m", help="Start. Default: now-15m")
    p.add_argument("--to", default="now", help="End. Default: now")
    p.add_argument("--limit", type=int, default=50, help="Max spans (max 1000). Default: 50")
    p.add_argument("--sort", default="-timestamp",
                   help="'-timestamp' newest first (default), 'timestamp' oldest first")
    p.add_argument("--raw", action="store_true", help="Print full Datadog response")
    args = p.parse_args()

    body = {
        "filter": {
            "query": args.query,
            "from": parse_time_iso(args.frm),
            "to": parse_time_iso(args.to),
        },
        "page": {"limit": min(args.limit, 1000)},
        "sort": args.sort,
    }

    resp = run_or_exit(lambda: dd_post("/api/v2/spans/events/search", body))

    if args.raw:
        print_json(resp)
        return 0

    spans = [_trim(s) for s in resp.get("data", [])]
    print_json({
        "count": len(spans),
        "has_more": bool(resp.get("meta", {}).get("page", {}).get("after")),
        "spans": spans,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
