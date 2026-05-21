#!/usr/bin/env python3
"""Search Elasticsearch logs via POST /{index}/_search.

Default window: now-15m to now. Default output: trimmed JSON with total,
timing, and one row per hit containing {timestamp, host, service/app, level,
message, _index, _id} plus a `rest` bag for any non-trimmed fields present.

Use --raw for the unfiltered Elasticsearch response, --fields to restrict the
_source projection, --no-trim to keep the full _source on every hit.

Examples:
  # Recent errors across everything
  python search_logs.py --query "level:ERROR" --from now-15m --limit 20

  # Errors for one service
  python search_logs.py --query 'level:ERROR AND fields.ServiceName:"tables-fields"'

  # Trace one request
  python search_logs.py --query "fields.RequestId:abc-123"
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "es-setup" / "scripts"))
from es_client import (  # noqa: E402
    es_post, resolve_index, run_or_exit, print_json, kibana_discover_url,
)


# Field probe lists, ordered by Method's actual shape first, then common
# conventions (logstash / filebeat / serilog) as fallbacks for non-Method logs.
_TIMESTAMP_KEYS = ["@timestamp", "timestamp", "time"]
_HOST_KEYS = ["host.name", "hostname", "host", "beat.hostname"]
_SERVICE_KEYS = ["Context", "type", "service", "service.name", "app",
                 "application", "logger_name"]
_LEVEL_KEYS = ["Level", "level", "log.level", "log_level", "severity", "@l"]
_MESSAGE_KEYS = ["message", "Error", "@m", "msg", "log.message"]
_TRACE_KEYS = ["trace.id", "trace_id", "correlation_id", "request_id", "x-request-id"]
_ACCOUNT_KEYS = ["Account", "account", "tenant", "tenant_id"]


def _get_nested(doc: dict, dotted: str):
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _first_non_null(doc: dict, keys: list[str]):
    for k in keys:
        v = _get_nested(doc, k)
        if v is not None and v != "":
            return v, k
    return None, None


def _trim_hit(hit: dict, message_truncate: int = 800) -> dict:
    src = hit.get("_source", {}) or {}
    ts, _ = _first_non_null(src, _TIMESTAMP_KEYS)
    host, _ = _first_non_null(src, _HOST_KEYS)
    svc, _ = _first_non_null(src, _SERVICE_KEYS)
    lvl, _ = _first_non_null(src, _LEVEL_KEYS)
    msg, _ = _first_non_null(src, _MESSAGE_KEYS)
    trace, _ = _first_non_null(src, _TRACE_KEYS)
    account, _ = _first_non_null(src, _ACCOUNT_KEYS)
    action = _get_nested(src, "Action")
    exception = _get_nested(src, "Exception")
    if isinstance(msg, str) and len(msg) > message_truncate:
        msg = msg[:message_truncate] + f"... [+{len(msg) - message_truncate} chars]"
    if isinstance(exception, str) and len(exception) > message_truncate:
        exception = exception[:message_truncate] + f"... [+{len(exception) - message_truncate} chars]"
    return {
        "timestamp": ts,
        "level": lvl,
        "host": host,
        "service": svc,
        "action": action,
        "account": account,
        "trace": trace,
        "message": msg,
        "exception": exception,
        "_index": hit.get("_index"),
        "_id": hit.get("_id"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", required=True,
                   help="Lucene query_string syntax. e.g. 'level:ERROR AND host:web-*'")
    p.add_argument("--index", help="Index pattern. Default: ES_DEFAULT_INDEX from .env")
    p.add_argument("--from", dest="frm", default="now-15m",
                   help="Start time (ES date math). Default: now-15m")
    p.add_argument("--to", default="now", help="End time. Default: now")
    p.add_argument("--time-field", default="@timestamp",
                   help="Time field to range-filter on. Default: @timestamp")
    p.add_argument("--limit", type=int, default=50,
                   help="Max hits (server cap 10,000). Default: 50")
    p.add_argument("--sort", default="desc", choices=["desc", "asc"],
                   help="Sort by time field. Default: desc (newest first)")
    p.add_argument("--fields", nargs="+",
                   help="Restrict _source to these fields (e.g. --fields @timestamp level message)")
    p.add_argument("--raw", action="store_true",
                   help="Print full Elasticsearch response")
    p.add_argument("--no-trim", action="store_true",
                   help="Keep full _source on each hit instead of trimming")
    p.add_argument("--no-link", action="store_true",
                   help="Suppress Kibana Discover pivot link on stderr")
    args = p.parse_args()

    index = resolve_index(args.index)

    body: dict = {
        "size": min(args.limit, 10_000),
        "sort": [{args.time_field: {"order": args.sort}}],
        "query": {
            "bool": {
                "must": [
                    {"query_string": {"query": args.query, "analyze_wildcard": True}},
                    {"range": {args.time_field: {"gte": args.frm, "lte": args.to}}},
                ]
            }
        },
        "track_total_hits": True,
    }
    if args.fields:
        body["_source"] = args.fields

    resp = run_or_exit(lambda: es_post(f"/{index}/_search", body))

    if args.raw:
        print_json(resp)
    else:
        hits_obj = resp.get("hits", {}) or {}
        total = (hits_obj.get("total") or {}).get("value", 0)
        hits = hits_obj.get("hits", []) or []
        rows = [(h.get("_source", {}) | {"_index": h.get("_index"), "_id": h.get("_id")})
                if args.no_trim else _trim_hit(h)
                for h in hits]
        print_json({
            "index": index,
            "query": args.query,
            "window": f"{args.frm} -> {args.to}",
            "total": total,
            "returned": len(rows),
            "took_ms": resp.get("took"),
            "timed_out": resp.get("timed_out"),
            "hits": rows,
        })

    if not args.no_link:
        sys.stderr.write(f"\nKibana: {kibana_discover_url(index, args.query, args.frm, args.to)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
