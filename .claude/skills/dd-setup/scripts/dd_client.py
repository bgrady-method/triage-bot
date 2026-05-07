"""Shared Datadog API client used by every dd-* skill helper script.

Other skills import this via (project-vendored layout — `__file__`-relative so
it works whether the parent is `~/.claude/skills/` or `<repo>/.claude/skills/`):

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dd-setup" / "scripts"))
    from dd_client import dd_get, dd_post, parse_time_unix, parse_time_iso, run_or_exit, print_json

Credentials resolution: process env vars (`DD_API_KEY`, `DD_APP_KEY`, `DD_SITE`)
take precedence. If they're absent, falls back to a `.env` file at the path in
`ENV_PATH` (the user-level skill convention). On a disposable-VM deployment the
env vars are set by `scripts/bootstrap.ps1` and the `.env` file is not used.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

try:
    import requests
except ImportError:
    sys.stderr.write("ERROR: 'requests' not installed. Run: pip install requests python-dotenv\n")
    sys.exit(2)

try:
    from dotenv import load_dotenv
except ImportError:
    sys.stderr.write("ERROR: 'python-dotenv' not installed. Run: pip install requests python-dotenv\n")
    sys.exit(2)


ENV_PATH = Path.home() / ".claude" / "skills" / "dd-setup" / ".env"


class DatadogAPIError(Exception):
    def __init__(self, status: int, method: str, path: str, body: str):
        self.status = status
        self.method = method
        self.path = path
        self.body = body
        super().__init__(f"{status} on {method} {path}: {body[:300]}")


def _load_env() -> tuple[str, str, str]:
    # `load_dotenv(override=False)` only fills in vars not already set, so
    # process env vars take precedence over `.env`. On the disposable-VM
    # deployment the file is absent and we read straight from os.environ.
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)
    api_key = os.environ.get("DD_API_KEY", "").strip()
    app_key = os.environ.get("DD_APP_KEY", "").strip()
    site = os.environ.get("DD_SITE", "datadoghq.com").strip() or "datadoghq.com"
    if not api_key or not app_key:
        sys.stderr.write(
            "ERROR: DD_API_KEY and/or DD_APP_KEY not set.\n"
            f"  -> Set them as environment variables, or place them in {ENV_PATH}.\n"
        )
        sys.exit(2)
    return api_key, app_key, site


API_KEY, APP_KEY, SITE = _load_env()
BASE_URL = f"https://api.{SITE}"


def _headers() -> dict[str, str]:
    return {
        "DD-API-KEY": API_KEY,
        "DD-APPLICATION-KEY": APP_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _check(r: "requests.Response", method: str, path: str) -> None:
    if r.status_code >= 400:
        raise DatadogAPIError(r.status_code, method, path, r.text)


def dd_get(path: str, params: Optional[dict] = None) -> Any:
    r = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params, timeout=30)
    _check(r, "GET", path)
    return r.json() if r.text else None


def dd_post(path: str, body: dict) -> Any:
    r = requests.post(f"{BASE_URL}{path}", headers=_headers(), data=json.dumps(body), timeout=30)
    _check(r, "POST", path)
    return r.json() if r.text else None


def run_or_exit(fn: Callable[[], Any]) -> Any:
    """Call fn(); on DatadogAPIError print a helpful message and exit non-zero."""
    try:
        return fn()
    except DatadogAPIError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        if e.status == 401:
            sys.stderr.write("  -> DD_API_KEY rejected. Re-check Organization Settings -> API Keys.\n")
        elif e.status == 403:
            sys.stderr.write(
                "  -> DD_APP_KEY missing scope. Required: logs_read_data, metrics_read, "
                "monitors_read, apm_read.\n"
                "     Edit the key in Datadog UI -> Personal Settings -> Application Keys.\n"
            )
        elif e.status == 429:
            sys.stderr.write("  -> Rate limited. Wait 60s and retry.\n")
        sys.exit(2)


_REL = re.compile(r"^now(?:-(\d+)([smhdw]))?$")
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_time_unix(s: str) -> int:
    """Parse 'now', 'now-15m', ISO 8601, or unix epoch -> unix seconds (int)."""
    if not s:
        raise ValueError("empty time string")
    s = s.strip()
    m = _REL.match(s)
    if m:
        n, unit = m.groups()
        offset = int(n) * _UNITS[unit] if n else 0
        return int(time.time()) - offset
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        pass
    try:
        v = int(s)
        return v // 1000 if v > 10**12 else v
    except ValueError:
        raise ValueError(f"cannot parse time: {s!r}")


def parse_time_iso(s: str) -> str:
    """Parse and re-emit as ISO 8601 with Z. v2 log/span APIs prefer this format."""
    return datetime.fromtimestamp(parse_time_unix(s), tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def web_url(path: str = "") -> str:
    """Build a Datadog web UI URL (handy for printing pivot links). Note: web host is `app.<site>`, not `api.<site>`."""
    return f"https://app.{SITE}{path}"
