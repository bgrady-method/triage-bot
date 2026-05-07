#!/usr/bin/env python3
"""Query a Datadog metric and return its timeseries.

Wraps GET /api/v1/query. Returns trimmed JSON with summary stats per series
(min/max/avg/last), and a sample of points. Use --raw for full point arrays.

Examples:
  # Per-service request rate
  python query_timeseries.py --query "sum:trace.web.request.hits{service:tables-fields}.as_rate()"

  # p95 latency by endpoint over the last 4h
  python query_timeseries.py --from now-4h \\
    --query "p95:trace.web.request.duration{service:tables-fields} by {resource_name}"

  # Error rate
  python query_timeseries.py --query "sum:trace.web.request.errors{service:tables-fields}.as_rate()"
"""
from __future__ import annotations

import argparse
import statistics
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dd-setup" / "scripts"))
from dd_client import dd_get, parse_time_unix, run_or_exit, print_json  # noqa: E402


def _stats(points: list) -> dict:
    """Datadog v1 returns points as [[ts_ms, value], ...]. NaN/None values are common."""
    vals = [p[1] for p in points if p[1] is not None]
    if not vals:
        return {"count": 0, "min": None, "max": None, "avg": None, "last": None}
    return {
        "count": len(vals),
        "min": min(vals),
        "max": max(vals),
        "avg": statistics.fmean(vals),
        "last": points[-1][1] if points else None,
    }


def _trim(series: dict, sample_size: int = 5) -> dict:
    points = series.get("pointlist", []) or []
    sample = points[:sample_size] + ["..."] + points[-sample_size:] if len(points) > 2 * sample_size else points
    return {
        "expression": series.get("expression"),
        "scope": series.get("scope"),
        "metric": series.get("metric"),
        "display_name": series.get("display_name"),
        "unit": series.get("unit"),
        "interval": series.get("interval"),
        "length": series.get("length"),
        "stats": _stats(points),
        "sample_points": sample,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", required=True,
                   help="Metric query string, e.g. 'avg:system.cpu.user{*}'")
    p.add_argument("--from", dest="frm", default="now-1h",
                   help="Start time. 'now-1h', ISO 8601, or unix epoch. Default: now-1h")
    p.add_argument("--to", default="now", help="End time. Default: now")
    p.add_argument("--raw", action="store_true",
                   help="Print full Datadog response with all points")
    p.add_argument("--sample-size", type=int, default=5,
                   help="Points to show at head and tail when not --raw. Default: 5")
    args = p.parse_args()

    params = {
        "query": args.query,
        "from": parse_time_unix(args.frm),
        "to": parse_time_unix(args.to),
    }
    resp = run_or_exit(lambda: dd_get("/api/v1/query", params=params))

    if args.raw:
        print_json(resp)
        return 0

    series = [_trim(s, args.sample_size) for s in (resp.get("series") or [])]
    print_json({
        "query": args.query,
        "status": resp.get("status"),
        "from_date": resp.get("from_date"),
        "to_date": resp.get("to_date"),
        "series_count": len(series),
        "message": resp.get("message"),
        "error": resp.get("error"),
        "series": series,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
