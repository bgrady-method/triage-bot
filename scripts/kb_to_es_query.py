"""KB-entry-to-ES-query helper.

Given a KB id, read its `match.any_of` and emit a single Kibana/ES query
string. Used by step 3 of the triage routine (KIR shortcut) to confirm
the recurrence with one ES query and to produce a clickable Kibana URL
for the DM.

Output is plain text on stdout — pipe into `es_search.py --query`.

Priority order for picking the query content:
  1. Top-level `contains` clauses in `match.any_of` (best — literal, deterministic).
  2. Inside nested `all_of` clauses in `any_of`, the first `contains` literal.
  3. Top-level `regex` clauses in `match.any_of` — wrapped as Lucene regex.
  4. Fallback: KB entry's `title` as a quoted phrase.

Up to 3 literals are OR'd together. If nothing usable is found, exits with
status 1 (caller should fall back to a service-tag query).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _literal_for_lucene(s: str) -> str:
    """Quote and escape a literal so it parses as a Lucene phrase."""
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _harvest_contains(any_of: list) -> list[str]:
    """Pull contains literals from any_of, including nested all_of clauses."""
    out: list[str] = []
    for clause in any_of:
        if "contains" in clause:
            out.append(clause["contains"])
        elif "all_of" in clause:
            for sub in clause["all_of"]:
                if "contains" in sub:
                    out.append(sub["contains"])
                    break  # one literal per all_of group is enough
    return out


def _harvest_regex(any_of: list) -> list[str]:
    return [c["regex"] for c in any_of if "regex" in c]


def kb_to_query(entry: dict) -> str | None:
    m = entry.get("match") or {}
    any_of = m.get("any_of") or []

    literals = _harvest_contains(any_of)[:3]
    if literals:
        return " OR ".join(_literal_for_lucene(lit) for lit in literals)

    # No contains — try regex (Lucene supports /pattern/ at term position)
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
