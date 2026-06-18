"""KB-entry-to-ES-query helper.

Given a KB id, read its `match.any_of` and emit a single Kibana/ES query
string. Used by step 3 of the triage routine (KIR shortcut) to confirm
the recurrence with one ES query and to produce a clickable Kibana URL
for the DM.

Output is plain text on stdout — pipe into `es_search.py --query`.

ES holds Serilog app logs; queries must reference real ES fields. The single
most reliable ES query is **service-scoped** on the `Application` field, so that
is preferred over raw KB `match.any_of` literals (which are tuned to match Slack
*alert text* — Datadog monitor names, `monitors/<id>` tokens — and frequently do
NOT appear in ES log documents, yielding zero hits).

Priority order for picking the query content:
  1. **Service-scoped** `Application:"<service>"` when a service name can be
     derived from the entry's title or regex clauses (best — matches real ES docs).
  2. Top-level / nested `all_of` `contains` literals in `match.any_of`,
     **excluding Datadog-only tokens** (`monitors/<id>`), OR'd together (≤3).
  3. Top-level `regex` clauses in `match.any_of` — wrapped as Lucene regex.
  4. Fallback: KB entry's `title` as a quoted phrase.

`monitors/<id>` literals are always dropped — they never appear in ES logs.
If nothing usable is found, exits with status 1 (caller should fall back to a
service-scoped `Application:"<service>"` query).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Datadog-only token: a `monitors/<id>` reference. Lives in Slack alert text /
# Datadog, never in ES log documents — must never become an ES query term.
_MONITOR_TOKEN_RE = re.compile(r"monitors/\d+")

# Method service / Application names as they appear in ES `Application` field,
# e.g. runtime-core-api, ms-gateway-api, method-platform-ui, legacy-miurl-api.
_SERVICE_RE = re.compile(
    r"\b("
    r"runtime-core(?:-api|-subscriber-api)?"
    r"|oauth2"
    r"|xero-sync"
    r"|ms-[a-z0-9]+(?:-[a-z0-9]+)*"
    r"|qbo-[a-z0-9]+(?:-[a-z0-9]+)*"
    r"|legacy-[a-z0-9]+(?:-[a-z0-9]+)*"
    r"|method-[a-z0-9]+(?:-[a-z0-9]+)*"
    r"|[a-z0-9]+(?:-[a-z0-9]+)*-api"
    r")\b"
)


def _literal_for_lucene(s: str) -> str:
    """Quote and escape a literal so it parses as a Lucene phrase."""
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _is_dd_only(literal: str) -> bool:
    """True if the literal is a Datadog-only token (never present in ES logs)."""
    return bool(_MONITOR_TOKEN_RE.search(literal))


def _derive_service(entry: dict) -> str | None:
    """Best-effort service name from the entry's title, then its regex clauses.

    Returns the first Method service/Application token found, lowercased — the
    most reliable thing to scope an ES query on. The caller (and the triage
    prompt) may refine it against the service actually seen in logs.
    """
    candidates = [entry.get("title") or ""]
    any_of = (entry.get("match") or {}).get("any_of") or []
    candidates += [c["regex"] for c in any_of if "regex" in c]
    for text in candidates:
        m = _SERVICE_RE.search(text.lower())
        if m:
            return m.group(1)
    return None


def _harvest_contains(any_of: list) -> list[str]:
    """Pull contains literals from any_of (incl. nested all_of), dropping DD-only tokens."""
    out: list[str] = []
    for clause in any_of:
        if "contains" in clause:
            if not _is_dd_only(clause["contains"]):
                out.append(clause["contains"])
        elif "all_of" in clause:
            for sub in clause["all_of"]:
                if "contains" in sub and not _is_dd_only(sub["contains"]):
                    out.append(sub["contains"])
                    break  # one literal per all_of group is enough
    return out


def _harvest_regex(any_of: list) -> list[str]:
    return [c["regex"] for c in any_of if "regex" in c]


def kb_to_query(entry: dict) -> str | None:
    m = entry.get("match") or {}
    any_of = m.get("any_of") or []

    # 1. Prefer a service-scoped query — the only thing reliably present in ES.
    service = _derive_service(entry)
    if service:
        return f'Application:{_literal_for_lucene(service)}'

    # 2. contains literals, excluding Datadog-only tokens (monitors/<id>).
    literals = _harvest_contains(any_of)[:3]
    if literals:
        return " OR ".join(_literal_for_lucene(lit) for lit in literals)

    # 3. No usable contains — try regex (Lucene supports /pattern/ at term position)
    regexes = _harvest_regex(any_of)[:1]
    if regexes:
        return f"/{regexes[0]}/"

    title = entry.get("title")
    if title:
        # Truncate long titles to the first clause (split on em dash / colon)
        for delim in (" — ", ": "):
            if delim in title:
                title = title.split(delim, 1)[0]
                break
        return _literal_for_lucene(title)

    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kb-id", required=True, help="Entry id, e.g. ki-2026-05-21-gateway-microservices-timeout")
    p.add_argument(
        "--kb-file",
        default="kb/known-issues.json",
        help="Path to KB JSON (default: kb/known-issues.json relative to cwd)",
    )
    args = p.parse_args()

    kb_path = Path(args.kb_file)
    if not kb_path.exists():
        print(f"error: KB file not found: {kb_path}", file=sys.stderr)
        return 1

    with kb_path.open(encoding="utf-8") as f:
        entries = json.load(f)

    entry = next((e for e in entries if e.get("id") == args.kb_id), None)
    if entry is None:
        print(f"error: KB id not found: {args.kb_id}", file=sys.stderr)
        return 1

    query = kb_to_query(entry)
    if query is None:
        print(f"error: no usable match content in entry {args.kb_id}", file=sys.stderr)
        return 1

    print(query)
    return 0


if __name__ == "__main__":
    sys.exit(main())
