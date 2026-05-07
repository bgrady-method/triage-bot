#!/usr/bin/env python3
"""Describe the field mapping of an Elasticsearch index.

Wraps GET /{index}/_mapping and flattens the (potentially deeply nested)
properties tree into a sorted list of {path, type, aggregatable, sub_fields}.
Answers "what can I query / aggregate on" without needing to scroll the
Kibana UI.

For index patterns that match many indices (e.g. logstash-*), pass a
concrete index (e.g. logstash-2026.04.15) or narrow further — the mapping
is per-index.
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "es-setup" / "scripts"))
from es_client import es_get, resolve_index, run_or_exit, print_json  # noqa: E402


def _flatten(props: dict, prefix: str = "", out: list | None = None) -> list[dict]:
    if out is None:
        out = []
    for name, meta in (props or {}).items():
        if not isinstance(meta, dict):
            continue
        path = f"{prefix}.{name}" if prefix else name
        entry = {
            "path": path,
            "type": meta.get("type"),
            "sub_fields": sorted((meta.get("fields") or {}).keys()) or None,
        }
        # A field is aggregatable if it's keyword/date/numeric/boolean/ip,
        # or if it has a .keyword sub-field.
        aggregatable_types = {"keyword", "date", "boolean", "ip", "long", "integer",
                              "short", "byte", "double", "float", "half_float",
                              "scaled_float"}
        is_agg = (entry["type"] in aggregatable_types
                  or (entry["sub_fields"] and "keyword" in entry["sub_fields"]))
        entry["aggregatable"] = bool(is_agg)
        out.append(entry)
        if "properties" in meta:
            _flatten(meta["properties"], path, out)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index",
                   help="Index or pattern. Default: ES_DEFAULT_INDEX from .env. "
                        "For patterns, the mapping of each matching index is merged.")
    p.add_argument("--filter", dest="filt",
                   help="Case-insensitive substring match on field path")
    p.add_argument("--type", dest="ftype",
                   help="Filter by field type (keyword, text, date, long, etc.)")
    p.add_argument("--top", type=int, default=500,
                   help="Max fields to print. Default: 500")
    p.add_argument("--raw", action="store_true",
                   help="Print full _mapping response")
    args = p.parse_args()

    index = resolve_index(args.index)
    resp = run_or_exit(lambda: es_get(f"/{index}/_mapping"))

    if args.raw:
        print_json(resp)
        return 0

    # Response shape: {index_name: {mappings: {properties: {...}}}, ...}
    merged_fields: dict[str, dict] = {}
    for idx_name, payload in (resp or {}).items():
        props = (payload.get("mappings") or {}).get("properties") or {}
        for field in _flatten(props):
            # Later mappings overwrite earlier ones for the same path. ES
            # enforces mapping consistency across aliased indices, so this
            # should be idempotent in practice.
            merged_fields[field["path"]] = field

    fields = list(merged_fields.values())

    if args.filt:
        n = args.filt.lower()
        fields = [f for f in fields if n in f["path"].lower()]
    if args.ftype:
        fields = [f for f in fields if f["type"] == args.ftype]

    fields.sort(key=lambda f: f["path"])
    fields = fields[: args.top]

    type_counts: dict[str, int] = {}
    for f in merged_fields.values():
        t = f["type"] or "(composite)"
        type_counts[t] = type_counts.get(t, 0) + 1

    print_json({
        "index": index,
        "matched_indices": list((resp or {}).keys()),
        "total_fields": len(merged_fields),
        "type_counts": dict(sorted(type_counts.items(), key=lambda kv: -kv[1])),
        "filter": args.filt,
        "type_filter": args.ftype,
        "returned": len(fields),
        "fields": fields,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
