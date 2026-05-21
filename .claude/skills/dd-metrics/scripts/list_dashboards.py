#!/usr/bin/env python3
"""List Datadog dashboards (optionally filtered by title substring).

Wraps GET /api/v1/dashboard. Returns trimmed JSON with id, title, description, url.
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dd-setup" / "scripts"))
from dd_client import dd_get, run_or_exit, print_json, web_url  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--filter", dest="filt", default=None,
                   help="Case-insensitive substring match on dashboard title (client-side)")
    p.add_argument("--top", type=int, default=50,
                   help="Max dashboards to print after filtering. Default: 50")
    p.add_argument("--raw", action="store_true",
                   help="Print full Datadog response")
    args = p.parse_args()

    resp = run_or_exit(lambda: dd_get("/api/v1/dashboard"))
    if args.raw:
        print_json(resp)
        return 0

    dashboards = resp.get("dashboards") or []
    if args.filt:
        needle = args.filt.lower()
        dashboards = [d for d in dashboards if needle in (d.get("title") or "").lower()]
    dashboards = dashboards[: args.top]

    rows = [
        {
            "id": d.get("id"),
            "title": d.get("title"),
            "description": (d.get("description") or "")[:200],
            "modified_at": d.get("modified_at"),
            "author_handle": d.get("author_handle"),
            "url": web_url(f"/dashboard/{d.get('id')}"),
        }
        for d in dashboards
    ]
    print_json({"count": len(rows), "filter": args.filt, "dashboards": rows})
    return 0


if __name__ == "__main__":
    sys.exit(main())
