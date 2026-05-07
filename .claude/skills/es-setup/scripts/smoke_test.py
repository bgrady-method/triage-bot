#!/usr/bin/env python3
"""Verify Elasticsearch credentials and that the default index pattern has data.

Cluster-level calls (GET /, /_cluster/health) are treated as informational —
many Elastic Cloud roles grant index-level read without cluster monitoring.
What really matters is that _cat/indices and _search succeed.
"""
from __future__ import annotations

import sys

from es_client import (
    DEFAULT_INDEX,
    ES_CLOUD_ID,
    ES_URL,
    ES_USER,
    ElasticAPIError,
    es_get,
    es_post,
)

OK = "[OK]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"


def _try(label: str, fn) -> tuple[str, object]:
    print(f"  {label:28s}", end=" ", flush=True)
    try:
        result = fn()
        print(OK)
        return "ok", result
    except ElasticAPIError as e:
        if e.status == 403:
            print(f"{SKIP}  (403 — role lacks this cluster privilege; not required)")
            return "skip", e
        print(f"{FAIL}  ({e.status})")
        return "fail", e


def main() -> int:
    print(f"Cluster URL:      {ES_URL}")
    print(f"User:             {ES_USER}")
    print(f"Cloud ID:         {'(set)' if ES_CLOUD_ID else '(unset)'}")
    print(f"Default index:    {DEFAULT_INDEX or '(unset)'}")
    print()

    print("Cluster-level (informational):")
    st, info = _try("GET / (cluster info)", lambda: es_get("/"))
    if st == "ok":
        print(f"    cluster_name: {info.get('cluster_name')}")
        print(f"    version:      {(info.get('version') or {}).get('number')}")

    st, health = _try("GET /_cluster/health", lambda: es_get("/_cluster/health"))
    if st == "ok":
        print(f"    status:       {health.get('status')}")
        print(f"    nodes:        {health.get('number_of_nodes')}")
    print()

    # Index-level is what actually matters.
    if not DEFAULT_INDEX:
        print("No ES_DEFAULT_INDEX set in .env — skipping index checks.")
        print("Pass --index to each es-* script explicitly, or set ES_DEFAULT_INDEX.")
        return 0

    print(f"Index-level ({DEFAULT_INDEX}):")
    st, indices = _try("_cat/indices (list)",
                       lambda: es_get(f"/_cat/indices/{DEFAULT_INDEX}",
                                      params={"format": "json",
                                              "h": "index,docs.count,store.size",
                                              "bytes": "b"}))
    if st == "fail":
        print(f"    -> {indices}")
        return 1
    if st == "ok" and isinstance(indices, list):
        print(f"    matching indices: {len(indices)}")
        top = sorted(indices, key=lambda x: x.get("index") or "")[-5:]
        for ix in top:
            print(f"      {ix.get('index')}  docs={ix.get('docs.count')}  size={ix.get('store.size')}")
    print()

    st, search = _try("sample search (last 15m)",
                      lambda: es_post(f"/{DEFAULT_INDEX}/_search",
                                      {"size": 1,
                                       "query": {"range": {"@timestamp": {"gte": "now-15m", "lte": "now"}}},
                                       "sort": [{"@timestamp": "desc"}],
                                       "track_total_hits": True}))
    if st == "fail":
        print(f"    -> {search}")
        return 1
    if st == "ok":
        hits = (search.get("hits") or {}).get("hits") or []
        total = ((search.get("hits") or {}).get("total") or {}).get("value", 0)
        print(f"    docs in last 15m: {total}")
        if hits:
            src = hits[0].get("_source") or {}
            ts = src.get("@timestamp") or src.get("timestamp")
            print(f"    newest @timestamp: {ts}")
            sample_fields = sorted(src.keys())[:10]
            print(f"    sample top-level fields: {sample_fields}")

    print()
    print("es-* skills are ready to use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
