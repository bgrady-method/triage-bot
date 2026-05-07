"""Elasticsearch / Logstash REST wrapper.

Three subcommands cover the es-investigate playbook:
  - search       : POST logstash-*/_search
  - aggregate    : terms aggregation by a field
  - mapping      : GET _mapping for an index, optionally filtered

Auth via env vars (process env wins; .env files are fallbacks):
  ELK_BASE_URL    or ES_SEARCH_ENDPOINT / ES_URL  — e.g. https://logstash.method.internal:9243
  ELK_USER        or ES_USERNAME / ES_USER         — basic-auth user
  ELK_PASS        or ES_PASSWORD                   — basic-auth password
  ELK_INDEX_GLOB  or ES_DEFAULT_INDEX              — default index glob (default: "logstash-*")

If the vars are absent, this script also tries to load `<repo>/.env` and
`~/.claude/skills/es-setup/.env` so it works outside `invoke-routine.ps1`.

Output: JSON to stdout. Errors: JSON to stderr + non-zero exit.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _maybe_load_dotenv() -> None:
    """Best-effort load of .env if python-dotenv is available. Process env wins."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return
    repo_env = Path(__file__).resolve().parents[1] / ".env"
    home_env = Path.home() / ".claude" / "skills" / "es-setup" / ".env"
    for path in (repo_env, home_env):
        if path.exists():
            load_dotenv(path, override=False)


_maybe_load_dotenv()


def _base_url() -> str:
    url = (
        os.environ.get("ELK_BASE_URL")
        or os.environ.get("ES_SEARCH_ENDPOINT")
        or os.environ.get("ES_URL")
    )
    if not url:
        die("ELK_BASE_URL (or ES_SEARCH_ENDPOINT / ES_URL) must be set")
    return url.rstrip("/")


def _index() -> str:
    return (
        os.environ.get("ELK_INDEX_GLOB")
        or os.environ.get("ES_DEFAULT_INDEX")
        or "logstash-*"
    )


def _headers() -> dict[str, str]:
    user = os.environ.get("ELK_USER") or os.environ.get("ES_USERNAME") or os.environ.get("ES_USER")
    pw = os.environ.get("ELK_PASS") or os.environ.get("ES_PASSWORD")
    if not user or not pw:
        die("ELK_USER/ELK_PASS (or ES_USERNAME/ES_PASSWORD) must be set")
    creds = base64.b64encode(f"{user}:{pw}".encode("utf-8")).decode("ascii")
    return {
        "authorization": f"Basic {creds}",
        "content-type": "application/json",
    }


def die(msg: str, code: int = 1) -> None:
    json.dump({"error": msg}, sys.stderr)
    sys.stderr.write("\n")
    sys.exit(code)


def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{_base_url()}/{path.lstrip('/')}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        die(f"es {method} {url} -> {e.code}: {body}", code=2)
    except urllib.error.URLError as e:
        die(f"es request failed: {e}", code=2)


def _time_range(from_: str, to: str) -> dict:
    # ES accepts date math like "now-30m" directly in range.gte/lte.
    return {"range": {"@timestamp": {"gte": from_, "lte": to}}}


def cmd_search(args: argparse.Namespace) -> int:
    must = [{"query_string": {"query": args.query}}]
    body = {
        "size": args.limit,
        "sort": [{"@timestamp": {"order": args.sort}}],
        "query": {"bool": {"must": must, "filter": [_time_range(args.from_, args.to)]}},
    }
    out = _request("POST", f"{_index()}/_search", body)
    json.dump(out, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


def cmd_aggregate(args: argparse.Namespace) -> int:
    field = args.field if "." in args.field or args.field.endswith(".keyword") else f"{args.field}.keyword"
    body = {
        "size": 0,
        "query": {
            "bool": {
                "must": [{"query_string": {"query": args.query}}],
                "filter": [_time_range(args.from_, args.to)],
            }
        },
        "aggs": {"by_field": {"terms": {"field": field, "size": args.top}}},
    }
    out = _request("POST", f"{_index()}/_search", body)
    if not args.raw:
        buckets = (out.get("aggregations", {}).get("by_field", {}) or {}).get("buckets", [])
        out = {"total": out.get("hits", {}).get("total"), "buckets": buckets}
    json.dump(out, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


def cmd_mapping(args: argparse.Namespace) -> int:
    out = _request("GET", f"{args.index}/_mapping")
    if args.filter:
        # Walk the mapping and return only field paths containing args.filter
        hits: list[str] = []

        def walk(prefix: list[str], node: Any) -> None:
            if not isinstance(node, dict):
                return
            props = node.get("properties")
            if isinstance(props, dict):
                for k, v in props.items():
                    path = prefix + [k]
                    if args.filter in k:
                        hits.append(".".join(path))
                    walk(path, v)

        for idx, idx_body in out.items():
            walk([idx], (idx_body.get("mappings", {}) or {}))
        json.dump(sorted(set(hits)), sys.stdout, indent=2 if args.pretty else None)
    else:
        json.dump(out, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Elasticsearch search/aggregation helper.")
    p.add_argument("--pretty", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("search", help="Lucene-style search returning raw hits.")
    ps.add_argument("--query", required=True)
    ps.add_argument("--from", dest="from_", default="now-30m")
    ps.add_argument("--to", default="now")
    ps.add_argument("--limit", type=int, default=20)
    ps.add_argument("--sort", choices=["asc", "desc"], default="desc")
    ps.set_defaults(func=cmd_search)

    pa = sub.add_parser("aggregate", help="Terms aggregation by a field.")
    pa.add_argument("--query", required=True)
    pa.add_argument("--from", dest="from_", default="now-30m")
    pa.add_argument("--to", default="now")
    pa.add_argument("--field", required=True, help="Field to bucket by; .keyword auto-appended if absent.")
    pa.add_argument("--top", type=int, default=10)
    pa.add_argument("--raw", action="store_true", help="Return full ES response (default: just buckets).")
    pa.set_defaults(func=cmd_aggregate)

    pm = sub.add_parser("mapping", help="Inspect index field mappings.")
    pm.add_argument("--index", default=_index())
    pm.add_argument("--filter", help="Substring filter on field name.")
    pm.set_defaults(func=cmd_mapping)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
