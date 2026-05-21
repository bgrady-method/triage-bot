#!/usr/bin/env python3
"""Search Datadog logs.

Wraps POST /api/v2/logs/events/search. Default window: now-15m to now.
Default output: a compact JSON array of {timestamp, service, host, status, trace_id, message}.
Pass --raw for the unfiltered Datadog response.
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dd-setup" / "scripts"))
from dd_client import dd_post, parse_time_iso, run_or_exit, print_json, web_url  # noqa: E402


def _trim(event: dict) -> dict:
    a = event.get("attributes", {}) or {}
    attrs = a.get("attributes", {}) or {}
    return {
        "timestamp": a.get("timestamp"),
        "service": a.get("service"),
        "host": a.get("host"),
        "status": a.get("status"),
        "trace_id": attrs.get("trace_id") or attrs.get("dd", {}).get("trace_id"),
        "message": (a.get("message") or "")[:500],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", required=True,
                   help="Datadog log search query, e.g. 'service:tables-fields status:error'")
    p.add_argument("--from", dest="frm", default="now-15m",
                   help="Start time. 'now-15m', ISO 8601, or unix epoch. Default: now-15m")
    p.add_argument("--to", default="now",
                   help="End time. Same formats. Default: now")
    p.add_argument("--limit", type=int, default=50,
                   help="Max events to return (max 1000). Default: 50")
    p.add_argument("--sort", default="-timestamp",
                   help="'-timestamp' newest-first (default), 'timestamp' oldest-first")
    p.add_argument("--indexes", nargs="+",
                   help="Restrict to specific log indexes (default: all)")
    p.add_argument("--raw", action="store_true",
                   help="Print unfiltered Datadog response instead of trimmed events")
    p.add_argument("--no-link", action="store_true",
                   help="Suppress the trailing UI pivot link on stderr")
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
    if args.indexes:
        body["filter"]["indexes"] = args.indexes

    resp = run_or_exit(lambda: dd_post("/api/v2/logs/events/search", body))

    if args.raw:
        print_json(resp)
    else:
        events = [_trim(e) for e in resp.get("data", [])]
        print_json({
            "count": len(events),
            "has_more": bool(resp.get("meta", {}).get("page", {}).get("after")),
            "events": events,
        })

    if not args.no_link:
        from urllib.parse import quote
        url = web_url(
            f"/logs?query={quote(args.query)}"
            f"&from_ts={parse_time_iso(args.frm)}&to_ts={parse_time_iso(args.to)}"
        )
        sys.stderr.write(f"\nUI: {url}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
