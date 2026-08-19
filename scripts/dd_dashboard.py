"""Datadog Dashboard CRUD — portable wrapper over /api/v1/dashboard.

Companion to `dd_search.py`. Where that file is read-only (logs/monitors/
metrics/RUM), this one can *write* — so writes are gated:

  - list / get      : always safe, read-only.
  - create / update : DRY-RUN BY DEFAULT. Pass --commit to actually write.
  - delete          : DRY-RUN BY DEFAULT. Pass --commit to actually delete.

IMPORTANT — boundary with prompt.md Hard rule #3 ("No mutating Datadog or ES.
Read-only API calls only."): the autonomous triage routine must NOT call the
write paths here. This is a *user-invoked* tool. Reads are fine for anyone.

Auth via env vars (same as dd_search.py):
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


def _request(method: str, url: str, body: dict | None = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        die(f"datadog {method} {url} -> {e.code}: {detail}", code=2)
    except urllib.error.URLError as e:
        die(f"datadog request failed: {e}", code=2)


def _emit(obj: Any, pretty: bool) -> None:
    json.dump(obj, sys.stdout, indent=2 if pretty else None)
    sys.stdout.write("\n")


def _load_body(path: str) -> dict:
    """Read a dashboard definition from a file, or stdin when path == '-'."""
    try:
        if path == "-":
            raw = sys.stdin.read()
        else:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
    except OSError as e:
        die(f"could not read body file {path!r}: {e}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"body file {path!r} is not valid JSON: {e}")


# ── read paths (always safe) ────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace) -> int:
    """GET /api/v1/dashboard — list all dashboards (id/title/url/author)."""
    url = f"https://api.{_site()}/api/v1/dashboard"
    out = _request("GET", url)
    items = out.get("dashboards", []) if isinstance(out, dict) else []
    if args.query:
        q = args.query.lower()
        items = [d for d in items if q in (d.get("title") or "").lower()]
    if args.summary:
        items = [
            {
                "id": d.get("id"),
                "title": d.get("title"),
                "url": d.get("url"),
                "author": d.get("author_handle"),
                "layout_type": d.get("layout_type"),
                "modified": d.get("modified_at"),
            }
            for d in items
        ]
    _emit(items, args.pretty)
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    """GET /api/v1/dashboard/{id} — full definition (use this to clone/edit)."""
    url = f"https://api.{_site()}/api/v1/dashboard/{urllib.parse.quote(args.id)}"
    _emit(_request("GET", url), args.pretty)
    return 0


# ── write paths (dry-run by default; --commit to apply) ─────────────────────

def cmd_create(args: argparse.Namespace) -> int:
    """POST /api/v1/dashboard — create. Dry-run unless --commit."""
    body = _load_body(args.file)
    if "title" not in body or "widgets" not in body:
        die("dashboard body needs at least 'title' and 'widgets' (and usually 'layout_type').")
    if not args.commit:
        _emit({"dry_run": True, "would": "POST /api/v1/dashboard",
               "title": body.get("title"), "widgets": len(body.get("widgets") or []),
               "hint": "re-run with --commit to create"}, args.pretty)
        return 0
    url = f"https://api.{_site()}/api/v1/dashboard"
    _emit(_request("POST", url, body), args.pretty)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """PUT /api/v1/dashboard/{id} — replace. Dry-run unless --commit.

    The PUT replaces the whole dashboard, so the body should be a full
    definition — fetch with `get`, edit, then update.
    """
    body = _load_body(args.file)
    if not args.commit:
        _emit({"dry_run": True, "would": f"PUT /api/v1/dashboard/{args.id}",
               "title": body.get("title"), "widgets": len(body.get("widgets") or []),
               "hint": "re-run with --commit to update"}, args.pretty)
        return 0
    url = f"https://api.{_site()}/api/v1/dashboard/{urllib.parse.quote(args.id)}"
    _emit(_request("PUT", url, body), args.pretty)
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """DELETE /api/v1/dashboard/{id}. Dry-run unless --commit."""
    if not args.commit:
        _emit({"dry_run": True, "would": f"DELETE /api/v1/dashboard/{args.id}",
               "hint": "re-run with --commit to delete"}, args.pretty)
        return 0
    url = f"https://api.{_site()}/api/v1/dashboard/{urllib.parse.quote(args.id)}"
    _emit(_request("DELETE", url), args.pretty)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Datadog dashboard CRUD (writes are dry-run unless --commit).")
    p.add_argument("--pretty", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="List dashboards (read-only).")
    pl.add_argument("--query", help="Case-insensitive substring filter on title.")
    pl.add_argument("--summary", action="store_true", help="Strip to id/title/url/author.")
    pl.set_defaults(func=cmd_list)

    pg = sub.add_parser("get", help="Get one dashboard's full JSON (read-only).")
    pg.add_argument("--id", required=True, help="Dashboard id, e.g. 'abc-d3f-ghi'.")
    pg.set_defaults(func=cmd_get)

    pc = sub.add_parser("create", help="Create a dashboard (dry-run unless --commit).")
    pc.add_argument("--file", required=True, help="JSON definition file ('-' for stdin).")
    pc.add_argument("--commit", action="store_true", help="Actually create (default is dry-run).")
    pc.set_defaults(func=cmd_create)

    pu = sub.add_parser("update", help="Replace a dashboard (dry-run unless --commit).")
    pu.add_argument("--id", required=True, help="Dashboard id to replace.")
    pu.add_argument("--file", required=True, help="Full JSON definition file ('-' for stdin).")
    pu.add_argument("--commit", action="store_true", help="Actually update (default is dry-run).")
    pu.set_defaults(func=cmd_update)

    pd = sub.add_parser("delete", help="Delete a dashboard (dry-run unless --commit).")
    pd.add_argument("--id", required=True, help="Dashboard id to delete.")
    pd.add_argument("--commit", action="store_true", help="Actually delete (default is dry-run).")
    pd.set_defaults(func=cmd_delete)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
