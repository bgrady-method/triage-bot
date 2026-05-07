#!/usr/bin/env python3
"""Quick stats on one field: total matching docs, cardinality, and top N values.

Useful when you want to know "how many distinct services are emitting errors"
or "what's the set of error messages in this window". Faster than scrolling
through search_logs output.

Example:
  python field_stats.py --query "level:ERROR" --from now-1h --field fields.ServiceName
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "es-setup" / "scripts"))
from es_client import (  # noqa: E402
    es_post, resolve_index, run_or_exit, print_json,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", default="*", help="Lucene filter. Default: * (all docs)")
    p.add_argument("--index", help="Index pattern. Default: ES_DEFAULT_INDEX")
    p.add_argument("--from", dest="frm", default="now-1h", help="Default: now-1h")
    p.add_argument("--to", default="now", help="Default: now")
    p.add_argument("--time-field", default="@timestamp", help="Default: @timestamp")
    p.add_argument("--field", required=True,
                   help="Field to analyze. .keyword suffix added if not dotted.")
    p.add_argument("--top", type=int, default=20, help="Top N distinct values. Default: 20")
    p.add_argument("--raw", action="store_true", help="Print full ES response")
    args = p.parse_args()

    index = resolve_index(args.index)
    agg_field = args.field if args.field.endswith(".keyword") or "." in args.field \
        else f"{args.field}.keyword"

    body = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"query_string": {"query": args.query, "analyze_wildcard": True}},
                    {"range": {args.time_field: {"gte": args.frm, "lte": args.to}}},
                ]
            }
        },
        "aggs": {
            "cardinality": {"cardinality": {"field": agg_field}},
            "top": {"terms": {"field": agg_field, "size": args.top, "missing": "(missing)"}},
            "missing_count": {"missing": {"field": agg_field}},
        },
        "track_total_hits": True,
    }

    resp = run_or_exit(lambda: es_post(f"/{index}/_search", body))

    if args.raw:
        print_json(resp)
        return 0

    aggs = resp.get("aggregations") or {}
    total = ((resp.get("hits") or {}).get("total") or {}).get("value", 0)
    top_buckets = (aggs.get("top") or {}).get("buckets") or []
    print_json({
        "index": index,
        "query": args.query,
        "window": f"{args.frm} -> {args.to}",
        "field": args.field,
        "total_docs": total,
        "distinct_values": (aggs.get("cardinality") or {}).get("value"),
        "missing_docs": (aggs.get("missing_count") or {}).get("doc_count"),
        "other_docs": (aggs.get("top") or {}).get("sum_other_doc_count"),
        "top_values": [{"value": b.get("key"), "count": b.get("doc_count")} for b in top_buckets],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
