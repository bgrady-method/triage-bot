#!/usr/bin/env python3
"""Aggregate Elasticsearch logs by one or more fields to find where patterns concentrate.

Wraps POST /{index}/_search with a terms aggregation (no hits returned).
Use this BEFORE drilling into individual events with search_logs.py — it's
one round-trip that answers "where is the noise coming from".

Examples:
  # Top services emitting errors in the last hour
  python aggregate_logs.py --query "level:ERROR" --from now-1h --by fields.ServiceName

  # Error levels broken down by host
  python aggregate_logs.py --query "level:(ERROR OR FATAL)" --from now-15m \\
      --by host.name --by level --top 10

  # Time histogram of error volume (bucketed)
  python aggregate_logs.py --query "level:ERROR" --from now-6h \\
      --histogram --interval 10m
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "es-setup" / "scripts"))
from es_client import (  # noqa: E402
    es_post, resolve_index, run_or_exit, print_json, kibana_discover_url,
)


def _build_nested_terms_agg(fields: list[str], size: int) -> dict:
    """Nest terms aggs so each bucket's children are the next group-by level."""
    if not fields:
        return {}
    # Use .keyword suffix heuristic — most text fields in Logstash have a
    # .keyword subfield for aggregation. If it doesn't exist, ES will return a
    # clear error and you can re-run with the exact field name.
    field = fields[0]
    agg = {
        "terms": {
            "field": field if field.endswith(".keyword") or "." in field else f"{field}.keyword",
            "size": size,
            "missing": "(missing)",
        }
    }
    inner = _build_nested_terms_agg(fields[1:], size)
    if inner:
        agg["aggs"] = {fields[1]: inner}
    return agg


def _flatten_buckets(buckets: list, depth: int, names: list[str]) -> list[dict]:
    rows = []
    for b in buckets:
        row = {names[depth]: b.get("key"), "count": b.get("doc_count")}
        if depth + 1 < len(names):
            sub_key = names[depth + 1]
            sub = (b.get(sub_key) or {}).get("buckets", [])
            if sub:
                for child in _flatten_buckets(sub, depth + 1, names):
                    rows.append({**row, **{k: v for k, v in child.items() if k != "count"},
                                 "count": child["count"]})
                continue
        rows.append(row)
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", required=True, help="Lucene query_string filter")
    p.add_argument("--index", help="Index pattern. Default: ES_DEFAULT_INDEX")
    p.add_argument("--from", dest="frm", default="now-1h", help="Default: now-1h")
    p.add_argument("--to", default="now", help="Default: now")
    p.add_argument("--time-field", default="@timestamp", help="Default: @timestamp")
    p.add_argument("--by", action="append", default=[],
                   help="Field to group by. Repeatable for nested breakdown. "
                        "Appends .keyword automatically unless dotted.")
    p.add_argument("--top", type=int, default=10, help="Top N per level. Default: 10")
    p.add_argument("--histogram", action="store_true",
                   help="Return a date_histogram instead of terms aggregation")
    p.add_argument("--interval", default="1h",
                   help="Histogram bucket interval (e.g. 1m, 10m, 1h). Default: 1h")
    p.add_argument("--raw", action="store_true", help="Print full ES response")
    p.add_argument("--no-link", action="store_true", help="Suppress Kibana pivot link")
    args = p.parse_args()

    index = resolve_index(args.index)

    base_query = {
        "bool": {
            "must": [
                {"query_string": {"query": args.query, "analyze_wildcard": True}},
                {"range": {args.time_field: {"gte": args.frm, "lte": args.to}}},
            ]
        }
    }

    if args.histogram:
        body = {
            "size": 0,
            "query": base_query,
            "aggs": {
                "by_time": {
                    "date_histogram": {
                        "field": args.time_field,
                        "fixed_interval": args.interval,
                        "min_doc_count": 0,
                    }
                }
            },
        }
    else:
        if not args.by:
            # For Method's log shape, Context (the FQN logger) is usually the
            # most useful first grouping — it's analogous to "service" in
            # typical Logstash docs.
            args.by = ["Context"]
        body = {"size": 0, "query": base_query}
        top_field = args.by[0]
        body["aggs"] = {top_field: _build_nested_terms_agg(args.by, args.top)}

    resp = run_or_exit(lambda: es_post(f"/{index}/_search", body))

    if args.raw:
        print_json(resp)
    else:
        total = ((resp.get("hits") or {}).get("total") or {}).get("value", 0)
        if args.histogram:
            buckets = (resp.get("aggregations") or {}).get("by_time", {}).get("buckets", [])
            rows = [{"time": b.get("key_as_string"), "count": b.get("doc_count")} for b in buckets]
        else:
            top_field = args.by[0]
            buckets = (resp.get("aggregations") or {}).get(top_field, {}).get("buckets", [])
            rows = _flatten_buckets(buckets, 0, args.by)
        print_json({
            "index": index,
            "query": args.query,
            "window": f"{args.frm} -> {args.to}",
            "total_matched": total,
            "took_ms": resp.get("took"),
            "group_by": args.by if not args.histogram else [f"date_histogram({args.interval})"],
            "rows": rows,
        })

    if not args.no_link:
        sys.stderr.write(f"\nKibana: {kibana_discover_url(index, args.query, args.frm, args.to)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
