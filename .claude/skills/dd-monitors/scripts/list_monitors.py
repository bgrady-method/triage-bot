#!/usr/bin/env python3
"""List Datadog monitors, optionally filtered by name, tag, or state.

Wraps GET /api/v1/monitor/search (NOT /api/v1/monitor) because the list
endpoint's group_states param filters *groups within* each monitor, not
monitors by their overall status — so you get OK monitors back when you ask
for Alert. Search accepts a real 'status:Alert' DSL and filters properly.
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dd-setup" / "scripts"))
from dd_client import dd_get, run_or_exit, print_json, web_url  # noqa: E402


def _build_query(name: str | None, states: list[str], tags: list[str]) -> str:
    parts: list[str] = []
    if name:
        parts.append(f'name:"*{name}*"')
    if states:
        if len(states) == 1:
            parts.append(f'status:"{states[0]}"')
        else:
            inner = " OR ".join(f'status:"{s}"' for s in states)
            parts.append(f"({inner})")
    if tags:
        for tag in tags:
            parts.append(f'tag:"{tag}"')
    return " ".join(parts) if parts else "*"


def _trim(m: dict) -> dict:
    return {
        "id": m.get("id"),
        "name": m.get("name"),
        "type": m.get("type"),
        "status": m.get("status"),
        "tags": m.get("tags"),
        "last_triggered_ts": m.get("last_triggered_ts"),
        "query": (m.get("query") or "")[:200],
        "url": web_url(f"/monitors/{m.get('id')}"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", help="Substring match on monitor name")
    p.add_argument("--tag", action="append", default=[],
                   help="Tag filter, repeatable. e.g. --tag service:foo --tag env:prod")
    p.add_argument("--state", action="append", default=[],
                   choices=["Alert", "Warn", "No Data", "OK", "Ignored", "Skipped", "Unknown"],
                   help="Filter by status (repeatable, server-side)")
    p.add_argument("--top", type=int, default=50,
                   help="Page size (max 1000). Default: 50")
    p.add_argument("--page", type=int, default=0, help="Page number (0-indexed)")
    p.add_argument("--raw", action="store_true",
                   help="Print unfiltered Datadog response")
    args = p.parse_args()

    q = _build_query(args.name, args.state, args.tag)
    params = {"query": q, "per_page": min(args.top, 1000), "page": args.page}

    resp = run_or_exit(lambda: dd_get("/api/v1/monitor/search", params=params))

    if args.raw:
        print_json(resp)
        return 0

    monitors = [_trim(m) for m in (resp.get("monitors") or [])]
    counts = resp.get("counts", {}) or {}
    total = (resp.get("metadata", {}) or {}).get("total_count") \
        or sum(b.get("count", 0) for b in (counts.get("status", []) or []))
    print_json({
        "count": len(monitors),
        "total": total,
        "query": q,
        "status_breakdown": counts.get("status"),
        "monitors": monitors,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
