"""Datadog REST wrapper — minimal portable equivalent of the local dd-* skills.

Three subcommands mirror the parts of the dd-investigate playbook a routine
needs:
  - logs       : POST /api/v2/logs/events/search
  - monitors   : GET  /api/v1/monitor (with state filters)
  - metric     : POST /api/v1/query (timeseries query)

Auth via env vars:
  DD_API_KEY   — Datadog API key
  DD_APP_KEY   — Datadog application key
  DD_SITE      — datadoghq.com (default), datadoghq.eu, etc.

Output is JSON to stdout. Errors are JSON to stderr + non-zero exit.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _site() -> str:
    return os.environ.get("DD_SITE", "datadoghq.com")


def _headers() -> dict[str, str]:
    api = os.environ.get("DD_API_KEY")
    app = os.environ.get("DD_APP_KEY")
    if not api or not app:
        die("DD_API_KEY and DD_APP_KEY must be set")
    return {
        "DD-API-KEY": api,
        "DD-APPLICATION-KEY": app,
        "Content-Type": "application/json",
    }


def die(msg: str, code: int = 1) -> None:
    json.dump({"error": msg}, sys.stderr)
    sys.stderr.write("\n")
    sys.exit(code)


def _request(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        die(f"datadog {method} {url} -> {e.code}: {body}", code=2)
    except urllib.error.URLError as e:
        die(f"datadog request failed: {e}", code=2)


def cmd_logs(args: argparse.Namespace) -> int:
    """POST /api/v2/logs/events/search — search logs.

    Datadog accepts time as ISO or relative (`now-15m`).
    """
    payload = {
        "filter": {
            "query": args.query,
            "from": args.from_,
            "to": args.to,
        },
        "page": {"limit": args.limit},
        "sort": "-timestamp",
    }
    url = f"https://api.{_site()}/api/v2/logs/events/search"
    out = _request("POST", url, payload)
    json.dump(out, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


def cmd_monitors(args: argparse.Namespace) -> int:
    """GET /api/v1/monitor with tag and state filters."""
    qs: dict[str, Any] = {"with_downtimes": "false"}
    if args.tags:
        qs["monitor_tags"] = args.tags  # comma-separated
    if args.name:
        qs["name"] = args.name
    if args.state:
        # API accepts a comma-separated list via group_states
        qs["group_states"] = ",".join(args.state)
    url = f"https://api.{_site()}/api/v1/monitor?{urllib.parse.urlencode(qs)}"
    out = _request("GET", url)
    if isinstance(out, list) and args.summary:
        out = [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "type": m.get("type"),
                "overall_state": m.get("overall_state"),
                "query": m.get("query"),
                "tags": m.get("tags"),
                "last_triggered_ts": (m.get("overall_state_modified") or None),
            }
            for m in out
        ]
    json.dump(out, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


def cmd_metric(args: argparse.Namespace) -> int:
    """POST /api/v1/query — timeseries metric query."""
    qs = {"from": args.from_unix, "to": args.to_unix, "query": args.query}
    url = f"https://api.{_site()}/api/v1/query?{urllib.parse.urlencode(qs)}"
    out = _request("GET", url)
    json.dump(out, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Datadog API helper.")
    p.add_argument("--pretty", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("logs", help="Search logs.")
    pl.add_argument("--query", required=True, help='Datadog log query, e.g. "service:tables-fields status:error".')
    pl.add_argument("--from", dest="from_", default="now-30m")
    pl.add_argument("--to", default="now")
    pl.add_argument("--limit", type=int, default=50)
    pl.set_defaults(func=cmd_logs)

    pm = sub.add_parser("monitors", help="List monitors.")
    pm.add_argument("--tags", help="Comma-separated monitor_tags filter, e.g. 'service:tables-fields,env:prod'.")
    pm.add_argument("--name", help="Substring search on monitor name.")
    pm.add_argument("--state", action="append", choices=["Alert", "Warn", "No Data", "OK"])
    pm.add_argument("--summary", action="store_true", help="Strip to id/name/state/query.")
    pm.set_defaults(func=cmd_monitors)

    pq = sub.add_parser("metric", help="Run a metric timeseries query.")
    pq.add_argument("--query", required=True, help='e.g. "p95:trace.web.request.duration{service:tables-fields,env:prod}".')
    pq.add_argument("--from-unix", required=True, type=int, help="Unix epoch seconds (start).")
    pq.add_argument("--to-unix", required=True, type=int, help="Unix epoch seconds (end).")
    pq.set_defaults(func=cmd_metric)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
