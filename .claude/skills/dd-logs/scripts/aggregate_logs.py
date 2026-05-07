#!/usr/bin/env python3
"""Aggregate Datadog logs to find where errors / events are concentrated.

Wraps POST /api/v2/logs/analytics/aggregate. Use this BEFORE search_logs when you
don't yet know which service / host / endpoint is producing the noise.

Examples:
  # Top services producing errors in the last hour
  python aggregate_logs.py --query "status:error" --from now-1h --by service

  # Errors broken down by service AND host (heatmap-style)
  python aggregate_logs.py --query "status:error" --from now-1h --by service --by host

  # Top 5 paths producing 5xx for one service
  python aggregate_logs.py --query "service:tables-fields status:error" \\
      --from now-30m --by "@http.url_details.path" --top 5
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dd-setup" / "scripts"))
from dd_client import dd_post, parse_time_iso, run_or_exit, print_json  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", required=True, help="Datadog log search query")
    p.add_argument("--from", dest="frm", default="now-1h",
                   help="Start time. Default: now-1h")
    p.add_argument("--to", default="now", help="End time. Default: now")
    p.add_argument("--by", action="append", default=[],
                   help="Facet to group by. Repeatable. e.g. --by service --by host. "
                        "Use '@field' for log attributes (e.g. '@http.status_code').")
    p.add_argument("--top", type=int, default=10,
                   help="Top N per group (sorted by count desc). Default: 10")
    p.add_argument("--metric", default=None,
                   help="Optional measure to aggregate (e.g. '@duration'). Default: count")
    p.add_argument("--agg", default="count",
                   choices=["count", "cardinality", "pc75", "pc90", "pc95", "pc98",
                            "pc99", "sum", "min", "max", "avg", "median"],
                   help="Aggregation function. Default: count")
    p.add_argument("--raw", action="store_true",
                   help="Print unfiltered Datadog response")
    args = p.parse_args()

    if not args.by:
        args.by = ["service"]

    compute = {"aggregation": args.agg}
    if args.metric:
        compute["metric"] = args.metric
    if args.agg == "count":
        compute["type"] = "total"

    body = {
        "filter": {
            "query": args.query,
            "from": parse_time_iso(args.frm),
            "to": parse_time_iso(args.to),
        },
        "compute": [compute],
        "group_by": [
            {
                "facet": facet,
                "limit": args.top,
                "sort": {"order": "desc", "aggregation": args.agg,
                         **({"metric": args.metric} if args.metric else {})},
            }
            for facet in args.by
        ],
    }

    resp = run_or_exit(lambda: dd_post("/api/v2/logs/analytics/aggregate", body))

    if args.raw:
        print_json(resp)
        return 0

    buckets = resp.get("data", {}).get("buckets", [])
    rows = []
    for b in buckets:
        row = {f: b.get("by", {}).get(f) for f in args.by}
        row["count"] = b.get("computes", {}).get("c0")
        rows.append(row)

    print_json({
        "query": args.query,
        "window": f"{args.frm} -> {args.to}",
        "group_by": args.by,
        "rows": rows,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
