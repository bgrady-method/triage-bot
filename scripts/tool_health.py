"""Tool-availability health check for the triage-bot heartbeat.

Pings each external dependency the triage and stability-review routines rely on
and emits a single JSON document the heartbeat prompt can include in its
`#triage-bot-health` post.

Checks (REST-reachable from the routine VM):
  - gh        : `gh auth status` — GitHub CLI is authenticated and on a token
                with the right scopes.
  - dd        : Datadog API key validates (`GET /api/v1/validate`).
  - es        : Elasticsearch / Logstash search endpoint reachable
                (`POST $ELK_BASE_URL/<index>/_search?size=0`). Uses _search
                rather than _cluster/health because the bot's read-only
                user typically lacks the `monitor` cluster privilege —
                _cluster/health returns 403 even when search works fine.
  - sql       : NOT performed end-to-end (requires the SSH tunnel + a SQL
                driver outside stdlib). Reports `skipped` with a reason.
                The SSH-bastion check was removed 2026-05-22 when the bot
                started running on a direct ethernet connection; ES does
                not depend on it (Elastic Cloud is on the public Internet).
  - mongo     : Same — reported `skipped` since the URI test would need
                pymongo.

MCP tools (slack, atlassian, github MCP) are NOT checked here — Python can't
call MCPs. The heartbeat prompt makes those MCP calls inline. See
`routines/heartbeat.yaml`.

Usage:
  python scripts/tool_health.py              # all checks, JSON to stdout
  python scripts/tool_health.py --check dd   # one check
  python scripts/tool_health.py --pretty     # indented JSON

Exit code:
  0 — all checks passed (or skipped)
  1 — at least one check failed
  2 — internal error (config / network)

No external deps. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from base64 import b64encode

CHECKS = ("gh", "dd", "es", "sql", "mongo")
TIMEOUT_SECONDS = 8


def _ok(detail: str = "") -> dict:
    return {"status": "ok", "detail": detail}


def _fail(error: str) -> dict:
    return {"status": "fail", "error": error}


def _skipped(reason: str) -> dict:
    return {"status": "skipped", "reason": reason}


def check_gh() -> dict:
    """`gh api user` is a strong test: it both validates the token and exercises
    the API path. Returns 0 with `{login: ...}` on success."""
    try:
        res = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return _fail("gh CLI not installed")
    except subprocess.TimeoutExpired:
        return _fail("gh api user timed out")
    if res.returncode != 0:
        return _fail(f"gh api user returncode={res.returncode}: {(res.stderr or res.stdout).strip()[:200]}")
    login = res.stdout.strip()
    return _ok(f"as {login}") if login else _fail("empty login response")


def check_dd() -> dict:
    api = os.environ.get("DD_API_KEY")
    if not api:
        return _skipped("DD_API_KEY not set")
    site = os.environ.get("DD_SITE", "datadoghq.com")
    url = f"https://api.{site}/api/v1/validate"
    req = urllib.request.Request(url, headers={"DD-API-KEY": api})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return _fail(f"HTTP {e.code} from {url}")
    except urllib.error.URLError as e:
        return _fail(f"network: {e.reason}")
    except (TimeoutError, socket.timeout):
        return _fail("timeout")
    if body.get("valid") is True:
        return _ok(f"site={site}")
    return _fail(f"validate response: {body}")


def check_es() -> dict:
    base = os.environ.get("ELK_BASE_URL")
    if not base:
        return _skipped("ELK_BASE_URL not set")
    user = os.environ.get("ELK_USER")
    pw = os.environ.get("ELK_PASS")
    index = os.environ.get("ELK_INDEX_GLOB", "logstash-*")
    headers = {"content-type": "application/json"}
    if user and pw:
        headers["Authorization"] = "Basic " + b64encode(f"{user}:{pw}".encode()).decode()
    # _search?size=0 exercises the same auth+routing path es_search.py uses,
    # without needing the `monitor` cluster privilege that _cluster/health requires.
    url = base.rstrip("/") + f"/{index}/_search?size=0"
    req = urllib.request.Request(
        url,
        data=b'{"query":{"match_all":{}}}',
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return _fail(f"HTTP {e.code} from {url}")
    except urllib.error.URLError as e:
        return _fail(f"network: {e.reason}")
    except (TimeoutError, socket.timeout):
        return _fail("timeout")
    took = body.get("took")
    total = body.get("hits", {}).get("total", {}).get("value")
    if took is not None:
        return _ok(f"index={index} took={took}ms hits={total}")
    return _fail(f"unexpected response shape: {list(body)[:5]}")


def check_sql() -> dict:
    if not os.environ.get("SQL_HOST_PROD1"):
        return _skipped("SQL_HOST_PROD1 not set")
    return _skipped("end-to-end SQL test requires SSH tunnel + driver; not actively tested")


def check_mongo() -> dict:
    if not any(k.startswith("MONGO_URI_") for k in os.environ):
        return _skipped("no MONGO_URI_* env var set")
    return _skipped("end-to-end Mongo test requires pymongo; not actively tested")


CHECK_FN = {
    "gh": check_gh,
    "dd": check_dd,
    "es": check_es,
    "sql": check_sql,
    "mongo": check_mongo,
}


def summarize(results: dict[str, dict]) -> str:
    """One-line summary suitable for Slack."""
    by_status: dict[str, list[str]] = {"ok": [], "fail": [], "skipped": []}
    for name, r in results.items():
        by_status[r["status"]].append(name)
    parts = []
    if by_status["ok"]:
        parts.append("ok: " + ",".join(by_status["ok"]))
    if by_status["fail"]:
        parts.append("FAIL: " + ",".join(by_status["fail"]))
    if by_status["skipped"]:
        parts.append("skip: " + ",".join(by_status["skipped"]))
    return " | ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", choices=CHECKS, help="Run only one check.")
    ap.add_argument("--pretty", action="store_true", help="Indent JSON output.")
    ap.add_argument("--summary", action="store_true", help="Append a one-line summary on stderr.")
    args = ap.parse_args()

    targets = [args.check] if args.check else list(CHECKS)
    results: dict[str, dict] = {}
    for name in targets:
        try:
            results[name] = CHECK_FN[name]()
        except Exception as e:  # never let a check crash the heartbeat
            results[name] = _fail(f"check raised {type(e).__name__}: {e}")

    out = {"checks": results, "summary": summarize(results)}
    json.dump(out, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    if args.summary:
        sys.stderr.write(out["summary"] + "\n")

    any_fail = any(r["status"] == "fail" for r in results.values())
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
