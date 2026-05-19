"""One-shot helper: emit grouped satellite log lines for this poll cycle.

Reads a JSON spec from stdin like:
  {
    "groups": [
      {"group_hash": "...", "channel": "...", "channel_id": "...",
       "satellite_ts": ["1747...","1747..."]}
    ],
    "now_iso": "2026-05-19T13:30:00Z"
  }

Appends one grouped-with line per satellite ts to kb/incident-log.jsonl.
Also writes the list of all-hashes (primary + satellites) per group to stdout
as JSON: {"<group_hash>": ["primary", "sat1", ...], ...}

Deduplicated against existing incident-log entries via grep.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def h(channel_id: str, ts: str) -> str:
    return hashlib.sha256(f"{channel_id}:{ts}".encode("utf-8")).hexdigest()[:16]


def main() -> int:
    spec = json.load(sys.stdin)
    now = spec["now_iso"]
    log_path = Path("kb/incident-log.jsonl")
    existing = log_path.read_text(encoding="utf-8")

    out: dict[str, list[str]] = {}
    appends: list[str] = []
    for g in spec["groups"]:
        gh = g["group_hash"]
        ch_id = g["channel_id"]
        ch_name = g["channel"]
        primary_ts = g.get("primary_ts")
        sat_ts_list = g["satellite_ts"]

        primary_hash = h(ch_id, primary_ts) if primary_ts else gh
        out[gh] = [primary_hash]

        for ts in sat_ts_list:
            sat_hash = h(ch_id, ts)
            out[gh].append(sat_hash)
            # Dedup check
            if f'"alert_hash": "{sat_hash}"' in existing:
                continue
            line = json.dumps({
                "ts": now,
                "alert_hash": sat_hash,
                "channel": ch_name,
                "classification": "grouped",
                "matched_kb": None,
                "confidence": None,
                "action": f"grouped-with:{gh}",
                "grouped_with": gh,
                "slack_ts": ts,
                "duration_s": 0,
                "runtime_cost_usd": 0,
            })
            appends.append(line)

    if appends:
        with log_path.open("a", encoding="utf-8") as f:
            for line in appends:
                f.write(line + "\n")

    print(json.dumps(out, indent=2))
    print(f"\n# appended {len(appends)} satellite lines", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
