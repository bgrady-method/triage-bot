#!/usr/bin/env python3
"""Verify Datadog credentials and the four scopes the dd-* skills need."""
from __future__ import annotations

import sys
import time

from dd_client import (
    API_KEY,
    APP_KEY,
    SITE,
    DatadogAPIError,
    dd_get,
    dd_post,
)

OK = "[OK]"
FAIL = "[FAIL]"


def _redact(k: str) -> str:
    if not k:
        return "(empty)"
    if len(k) <= 10:
        return "*" * len(k)
    return f"{k[:4]}...{k[-4:]} ({len(k)} chars)"


def _try(label: str, fn) -> bool:
    print(f"  {label:22s}", end=" ", flush=True)
    try:
        fn()
        print(OK)
        return True
    except DatadogAPIError as e:
        print(f"{FAIL}  ({e.status})")
        return False


def main() -> int:
    print(f"Datadog site: {SITE}")
    print(f"DD_API_KEY:   {_redact(API_KEY)}")
    print(f"DD_APP_KEY:   {_redact(APP_KEY)}")
    print()

    print("API key:")
    try:
        r = dd_get("/api/v1/validate")
        if not r.get("valid"):
            print(f"  validate             {FAIL} (DD_API_KEY rejected by /api/v1/validate)")
            return 1
        print(f"  validate             {OK}")
    except DatadogAPIError as e:
        print(f"  validate             {FAIL} ({e.status})")
        print(f"  -> {e}")
        return 1
    print()

    print("App key scopes (probed via representative endpoints):")
    now = int(time.time())
    probes = [
        ("logs_read_data",
         lambda: dd_post("/api/v2/logs/events/search",
                         {"filter": {"query": "*", "from": "now-1m", "to": "now"},
                          "page": {"limit": 1}})),
        ("metrics_read",
         lambda: dd_get("/api/v1/query",
                        params={"query": "avg:system.cpu.user{*}", "from": now - 60, "to": now})),
        ("monitors_read",
         lambda: dd_get("/api/v1/monitor", params={"page": 0, "page_size": 1})),
        ("apm_read",
         lambda: dd_get("/api/v2/services", params={"page[size]": 1})),
    ]
    failed = [name for name, fn in probes if not _try(name, fn)]
    print()

    if failed:
        print(f"Missing or rejected scopes: {', '.join(failed)}")
        print("Fix: Datadog UI -> Personal Settings -> Application Keys -> edit your key -> add the scopes above.")
        return 1

    print("All scopes valid. dd-* skills are ready to use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
