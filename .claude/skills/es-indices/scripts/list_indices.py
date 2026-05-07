#!/usr/bin/env python3
"""List Elasticsearch indices matching a pattern.

Prefers GET /_resolve/index/{pattern} (needs only view_index_metadata). If that
403s, falls back to GET /{pattern}/_mapping and pulls index names from the
response keys. Both paths work for editor-level users who can't call
_cat/indices (which needs the cluster `monitor` privilege).

Because neither fallback exposes doc counts or sizes cheaply, this script only
returns index names and (when available) attributes / aliases / data_stream
membership. For counts, run a targeted `search_logs.py --query "*" --limit 1`.
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "es-setup" / "scripts"))
from es_client import es_get, run_or_exit, print_json, DEFAULT_INDEX, ElasticAPIError  # noqa: E402


def _via_resolve(pattern: str) -> dict | None:
    """Returns {'source': 'resolve', 'indices': [...], 'aliases': [...], 'data_streams': [...]} or None on 403."""
    try:
        resp = es_get(f"/_resolve/index/{pattern}")
    except ElasticAPIError as e:
        if e.status == 403:
            return None
        raise
    return {
        "source": "_resolve/index",
        "indices": [
            {"index": i.get("name"), "attributes": i.get("attributes"),
             "data_stream": i.get("data_stream"), "aliases": i.get("aliases")}
            for i in (resp.get("indices") or [])
        ],
        "aliases": [{"alias": a.get("name"), "indices": a.get("indices")}
                    for a in (resp.get("aliases") or [])],
        "data_streams": [{"name": d.get("name"), "backing_indices": d.get("backing_indices"),
                          "timestamp_field": d.get("timestamp_field")}
                         for d in (resp.get("data_streams") or [])],
    }


def _via_mapping(pattern: str) -> dict:
    resp = es_get(f"/{pattern}/_mapping")
    names = sorted((resp or {}).keys(), reverse=True)
    return {
        "source": "_mapping (fallback)",
        "indices": [{"index": n} for n in names],
        "aliases": [],
        "data_streams": [],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pattern",
                   help=f"Index name pattern, wildcards OK. "
                        f"Default: ES_DEFAULT_INDEX ({DEFAULT_INDEX or 'unset'}) or '*'.")
    p.add_argument("--top", type=int, default=30,
                   help="Max indices to print. Default: 30")
    args = p.parse_args()

    pattern = args.pattern or DEFAULT_INDEX or "*"

    def _run():
        resolved = _via_resolve(pattern)
        if resolved is not None:
            return resolved
        return _via_mapping(pattern)

    result = run_or_exit(_run)
    indices = result.get("indices") or []
    indices.sort(key=lambda r: (r.get("index") or ""), reverse=True)
    result["indices"] = indices[: args.top]
    result["pattern"] = pattern
    result["matched"] = len(indices)
    result["note"] = (
        "_cat/indices returns doc counts + sizes but needs the cluster "
        "'monitor' privilege. This endpoint only needs 'view_index_metadata', "
        "so it works under the editor role — but doesn't include counts."
    )
    print_json(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
