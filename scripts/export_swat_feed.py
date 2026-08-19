#!/usr/bin/env python3
"""Export a SWAT-contribution worksheet from the triage-bot knowledge base.

This is an AUTHORING AID, not a runtime feed. It reads kb/known-issues.json and
ranks recurring issues by occurrence, flags a best-effort "chronic" guess, and
maps each to the SWAT surface (SSM runbook / Datadog monitor) that would address
it. Use it to decide what to contribute to opscode/SWAT next and to keep those
contributions honest as new issues emerge.

  python scripts/export_swat_feed.py            # markdown table to stdout
  python scripts/export_swat_feed.py --json     # JSON worksheet to stdout
  python scripts/export_swat_feed.py --min 3    # only issues with >= 3 occurrences

It intentionally does NOT publish anything or talk to SWAT — SWAT's box-side
consumption (swat_ai grounding, notifier gate) is a separate, DevOps-owned step.
"""
from __future__ import annotations

import argparse
import json
import os
import re

KB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kb", "known-issues.json")

# keyword -> the SWAT surface that would address it (runbook and/or monitor)
SURFACE_MAP = [
    (r"subscriber|amqp|rabbit|consumer|cache invalidat",
     "swat-rb-subscriber-health-linux-v1 + [P1] subscriber-down monitor"),
    (r"\brtc\b|runtime/load|screen load|p95|latency",
     "[P2] RTC screen-load latency monitor"),
    (r"iis|app ?pool|\b502\b|bad gateway",           "swat-rb-iis-pool-status-windows-v1"),
    (r"elastic|lucene|read_only_allow_delete|shard",  "swat-rb-elastic-cluster-health-v1"),
    (r"disk|/var/log|watermark|msl04|aspnetcore log", "swat-rb-clear-logs-linux-v1 (action)"),
    (r"dns|route ?53|could not be resolved|nxdomain", "swat-rb-dns-dc-investigate-v1"),
    (r"ocelot|gateway|timed ?out|taskcancel",        "swat-rb-http-endpoint-investigate-v1"),
    (r"mongo",                                        "swat-rb-mongo-investigate-v1"),
]

CHRONIC_STATUS = re.compile(r"chronic|residual|mitigat|needs-|in-progress", re.I)


def _text(e: dict) -> str:
    parts = [str(e.get(k, "")) for k in ("id", "title", "diagnosis", "fix_status")]
    parts.append(json.dumps(e.get("match", "")))
    return " ".join(parts).lower()


def _surface(e: dict) -> str:
    t = _text(e)
    hits = [s for pat, s in SURFACE_MAP if re.search(pat, t)]
    return "; ".join(dict.fromkeys(hits)) if hits else "(no host surface — route to owner)"


def _chronic(e: dict) -> bool:
    occ = e.get("occurrences", 0) or 0
    return occ >= 5 or bool(CHRONIC_STATUS.search(str(e.get("fix_status", ""))))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a markdown table")
    ap.add_argument("--min", type=int, default=1, help="minimum occurrences to include")
    args = ap.parse_args()

    issues = json.load(open(KB, encoding="utf-8"))
    rows = []
    for e in issues:
        if not isinstance(e, dict):
            continue
        occ = e.get("occurrences", 0) or 0
        if occ < args.min:
            continue
        rows.append({
            "id": e.get("id", ""),
            "title": (e.get("title", "") or "")[:80],
            "occurrences": occ,
            "chronic_guess": _chronic(e),
            "fix_status": e.get("fix_status", ""),
            "owning_team": e.get("owning_team", ""),
            "swat_surface": _surface(e),
        })
    rows.sort(key=lambda r: r["occurrences"], reverse=True)

    if args.json:
        print(json.dumps({"generated_from": "kb/known-issues.json", "count": len(rows),
                          "note": "authoring aid, not a runtime feed", "issues": rows}, indent=2))
        return

    print("# SWAT contribution worksheet (from triage-bot KB)\n")
    print("Ranked by occurrence. `chronic?` is a heuristic (>=5 occ or fix_status hints) — "
          "confirm before treating an alert as noise. `SWAT surface` is the runbook/monitor to add or wire.\n")
    print("| occ | chronic? | id | SWAT surface | fix_status |")
    print("|----:|:--------:|----|--------------|------------|")
    for r in rows:
        print(f"| {r['occurrences']} | {'yes' if r['chronic_guess'] else ''} | "
              f"{r['id']} | {r['swat_surface']} | {r['fix_status']} |")
    print(f"\n_{len(rows)} issues (>= {args.min} occ). Chronic-flagged: "
          f"{sum(1 for r in rows if r['chronic_guess'])}._")


if __name__ == "__main__":
    main()
