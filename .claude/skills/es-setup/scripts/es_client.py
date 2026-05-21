"""Shared Elasticsearch client used by every es-* skill helper script.

Import pattern (same as dd_client; `__file__`-relative so it works for both
user-level and project-vendored layouts):

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "es-setup" / "scripts"))
    from es_client import es_get, es_post, run_or_exit, print_json, DEFAULT_INDEX, KIBANA_URL

Credentials resolution: process env vars take precedence; falls back to `.env`
at `ENV_PATH` if present. The vendored deployment also accepts the
triage-bot-routine-native env-var names (`ELK_BASE_URL`, `ELK_USER`, `ELK_PASS`)
as aliases for `ES_SEARCH_ENDPOINT`, `ES_USERNAME`, `ES_PASSWORD`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.stderr.write("ERROR: 'requests' not installed. Run: pip install requests python-dotenv\n")
    sys.exit(2)

try:
    from dotenv import load_dotenv
except ImportError:
    sys.stderr.write("ERROR: 'python-dotenv' not installed. Run: pip install requests python-dotenv\n")
    sys.exit(2)


ENV_PATH = Path.home() / ".claude" / "skills" / "es-setup" / ".env"


class ElasticAPIError(Exception):
    def __init__(self, status: int, method: str, path: str, body: str):
        self.status = status
        self.method = method
        self.path = path
        self.body = body
        super().__init__(f"{status} on {method} {path}: {body[:400]}")


def _load_env() -> tuple[str, str, str, str, str, str]:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)
    # Accept ES_SEARCH_ENDPOINT (current), ES_URL (earlier), and ELK_BASE_URL
    # (triage-bot routine-native) so a single secrets file works for both the
    # user-level skill and the vendored disposable-VM deployment.
    url = (
        os.environ.get("ES_SEARCH_ENDPOINT")
        or os.environ.get("ES_URL")
        or os.environ.get("ELK_BASE_URL")
        or ""
    ).strip().rstrip("/")
    user = (
        os.environ.get("ES_USERNAME")
        or os.environ.get("ES_USER")
        or os.environ.get("ELK_USER")
        or ""
    ).strip()
    password = (
        os.environ.get("ES_PASSWORD")
        or os.environ.get("ELK_PASS")
        or ""
    ).strip()
    cloud_id = (os.environ.get("ES_CLOUD_ID") or "").strip()
    default_index = (
        os.environ.get("ES_DEFAULT_INDEX")
        or os.environ.get("ELK_INDEX_GLOB")
        or ""
    ).strip()
    kibana = (os.environ.get("KIBANA_URL") or "https://logstash.method.me").strip().rstrip("/")
    if not url:
        sys.stderr.write(
            "ERROR: Elasticsearch endpoint not set.\n"
            "  -> Set ES_SEARCH_ENDPOINT (or ELK_BASE_URL) as an env var, "
            f"or place it in {ENV_PATH}.\n"
        )
        sys.exit(2)
    if not user or not password:
        sys.stderr.write(
            "ERROR: Elasticsearch credentials not set.\n"
            "  -> Set ES_USERNAME+ES_PASSWORD (or ELK_USER+ELK_PASS) as env vars, "
            f"or place them in {ENV_PATH}.\n"
        )
        sys.exit(2)
    return url, user, password, cloud_id, default_index, kibana


ES_URL, ES_USER, ES_PASSWORD, ES_CLOUD_ID, DEFAULT_INDEX, KIBANA_URL = _load_env()
_AUTH = HTTPBasicAuth(ES_USER, ES_PASSWORD)


def _headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "Accept": "application/json"}


def _check(r: "requests.Response", method: str, path: str) -> None:
    if r.status_code >= 400:
        raise ElasticAPIError(r.status_code, method, path, r.text)


def es_get(path: str, params: Optional[dict] = None) -> Any:
    r = requests.get(f"{ES_URL}{path}", headers=_headers(), auth=_AUTH,
                     params=params, timeout=30)
    _check(r, "GET", path)
    return r.json() if r.text else None


def es_post(path: str, body: dict, params: Optional[dict] = None) -> Any:
    r = requests.post(f"{ES_URL}{path}", headers=_headers(), auth=_AUTH,
                      params=params, data=json.dumps(body), timeout=60)
    _check(r, "POST", path)
    return r.json() if r.text else None


def run_or_exit(fn: Callable[[], Any]) -> Any:
    """Call fn(); on ElasticAPIError print a helpful message and exit non-zero."""
    try:
        return fn()
    except ElasticAPIError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        if e.status == 401:
            sys.stderr.write("  -> ES_USER / ES_PASSWORD rejected. Check credentials in .env.\n")
        elif e.status == 403:
            sys.stderr.write("  -> User lacks the required role on the target index.\n")
        elif e.status == 404:
            sys.stderr.write("  -> Index not found. Try `python list_indices.py` to list available indices.\n")
        elif e.status == 429:
            sys.stderr.write("  -> Rate limited / cluster busy. Retry in a moment.\n")
        elif e.status >= 500:
            sys.stderr.write("  -> Cluster error. May be transient; retry or check status in Kibana.\n")
        sys.exit(2)


def resolve_index(explicit: Optional[str]) -> str:
    idx = explicit or DEFAULT_INDEX
    if not idx:
        sys.stderr.write(
            "ERROR: no index pattern specified and ES_DEFAULT_INDEX is unset in .env.\n"
            "  -> Pass --index <pattern> or set ES_DEFAULT_INDEX.\n"
        )
        sys.exit(2)
    return idx


def print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def kibana_discover_url(index_pattern: str, query: str, frm: str, to: str) -> str:
    """Build a best-effort clickable Discover URL. Exact format varies by Kibana version."""
    return (
        f"{KIBANA_URL}/app/discover#/?"
        f"_g=(time:(from:'{quote(frm, safe=':-')}',to:'{quote(to, safe=':-')}'))"
        f"&_a=(index:'{quote(index_pattern, safe='*')}',"
        f"query:(language:lucene,query:'{quote(query, safe='')}'))"
    )
