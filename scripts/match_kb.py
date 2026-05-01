"""KB matcher.

Given an alert (channel + text) and a KB file (known-issues.json or
false-alarms.json), returns the first matching entry — or None.

Match order (deterministic, cheap-to-expensive):
  1. literal `contains` (case-insensitive)
  2. regex (`re.search`)
  3. (caller decides whether to fall through to LLM-based semantic match)

A KB entry's `match` block looks like:
  {
    "channels": ["alert-runtime-monitoring"],
    "any_of": [
      {"contains": "Deadlock found when trying to get lock"},
      {"regex": "tables-fields.*Timeout expired"}
    ]
  }
- `channels` is a hard filter (entry only fires on those channels). Omit to match all channels.
- `any_of` clauses OR together. Each clause is a `contains` OR a `regex`.

This module is intentionally pure-Python stdlib so it runs identically inside
the Anthropic routine sandbox and on a dev box.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def matches(entry: dict, channel: str, text: str) -> bool:
    m = entry.get("match") or {}

    channels = m.get("channels")
    if channels and channel not in channels:
        return False

    any_of = m.get("any_of") or []
    if not any_of:
        # An entry with no `any_of` clauses is a no-op — never matches by accident
        return False

    text_lower = text.lower() if text else ""
    for clause in any_of:
        if "contains" in clause:
            needle = clause["contains"].lower()
            if needle and needle in text_lower:
                return True
        elif "regex" in clause:
            try:
                if re.search(clause["regex"], text or "", re.IGNORECASE | re.MULTILINE):
                    return True
            except re.error:
                # Bad regex in KB — log to stderr but don't crash the whole match
                print(f"warning: bad regex in entry {entry.get('id')!r}: {clause['regex']!r}", file=sys.stderr)
    return False


def find_match(kb: list[dict], channel: str, text: str) -> dict | None:
    for entry in kb:
        if matches(entry, channel, text):
            return entry
    return None


def load_kb(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{p} must contain a JSON array")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Match an alert against a KB file.")
    parser.add_argument("--kb", required=True, help="Path to a KB JSON array file.")
    parser.add_argument("--channel", required=True, help="Channel name (e.g. alert-runtime-monitoring).")
    parser.add_argument("--text", help="Alert text to match. If omitted, reads from stdin.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Return all matches instead of just the first.",
    )
    args = parser.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    kb = load_kb(args.kb)

    if args.all:
        hits = [e for e in kb if matches(e, args.channel, text)]
        json.dump(hits, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0 if hits else 1

    hit = find_match(kb, args.channel, text)
    if hit is None:
        print("null")
        return 1
    json.dump(hit, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
