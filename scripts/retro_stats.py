#!/usr/bin/env python3
"""Aggregate triage-bot history for retrospectives.

Reads `kb/incident-log.jsonl` and `kb/known-issues.json` and prints weekly
classification / DM / known-issue-recurrence (KIR) breakdowns, per-channel and
per-KB-entry weekly counts, and a KB fix timeline.

The incident log is JSON-parsed line by line (never regex/awk): `ts` appears as
an ISO-8601 string (`"ts": "..."` and `"ts":"..."`) and, on older lines, as an
epoch integer. Both are normalised to aware UTC datetimes.

Usage:
    python scripts/retro_stats.py --log kb/incident-log.jsonl \
        --kb kb/known-issues.json --as-of 2026-11-25 [--format md|json] [--ref <git-ref>]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Rows that are bookkeeping, not alerts.
NON_ALERT = {"poll-cycle", "heartbeat", "stability-review"}
# Rows that represent a classified root-cause group (the KIR-share denominator).
DECISIONS = {"known-issue-recurrence", "needs-human", "new-with-clear-fix", "false-alarm"}
# fix_status values treated as "fixed" in the KB timeline.
FIXED = {"resolved", "mitigated", "fixed"}


@dataclass
class LoadResult:
    entries: list[dict[str, Any]] = field(default_factory=list)
    skipped: int = 0


def parse_ts(value: Any) -> datetime | None:
    """Return an aware UTC datetime for an ISO string or epoch number, else None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(s), tz=timezone.utc)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def load_incident_log_lines(lines: Iterable[str]) -> LoadResult:
    out = LoadResult()
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            out.skipped += 1
            continue
        if not isinstance(row, dict):
            out.skipped += 1
            continue
        dt = parse_ts(row.get("ts"))
        if dt is None:
            out.skipped += 1
            continue
        row["_dt"] = dt
        out.entries.append(row)
    return out


def load_incident_log(path: str | Path) -> LoadResult:
    with open(path, encoding="utf-8") as fh:
        return load_incident_log_lines(fh)


def read_text(path: str, ref: str | None) -> str:
    """Read a repo file from the working tree, or from a git ref when `ref` is set."""
    if not ref:
        return Path(path).read_text(encoding="utf-8")
    out = subprocess.run(
        ["git", "show", f"{ref}:{Path(path).as_posix()}"],
        check=True, capture_output=True, cwd=Path(__file__).resolve().parent.parent,
    )
    return out.stdout.decode("utf-8")


def week_key(dt: datetime) -> str:
    """ISO week label, e.g. '2026-W23' (weeks start Monday, UTC)."""
    y, w, _ = dt.astimezone(timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"


def _action(row: dict[str, Any]) -> str:
    return str(row.get("action") or "").lower()


# `action` is free text written by the routine. Until late June 2026 a surfaced
# alert was a self-DM (`dm-self`); after that it is a post to #triage-results
# (`post-triage-results`, `kb-update + post to #triage-results`, ...). Both count.
_SURFACE_MARKERS = ("dm", "post", "triage-results")
# "suppressed" (not "suppress"): "posted ... (past 24h suppression window)" was sent.
_NOT_SENT_MARKERS = ("suppressed", "no-send", "no-kb-write", "blocked-by")


def is_surfaced(row: dict[str, Any]) -> bool:
    """True when the row put a message in front of a human (DM or #triage-results post)."""
    if row.get("classification") in NON_ALERT:
        return False
    if row.get("suppressed_dm") is True:
        return False
    a = _action(row)
    if any(m in a for m in _NOT_SENT_MARKERS):
        return False
    return any(m in a for m in _SURFACE_MARKERS)


def is_dm_suppressed(row: dict[str, Any]) -> bool:
    if row.get("classification") in NON_ALERT:
        return False
    a = _action(row)
    if row.get("suppressed_dm") is True:
        return True
    if row.get("suppressed_dm") is False and is_surfaced(row):
        return False
    return "suppressed" in a or a.startswith("actionable-append")


def kir_share(counts: Counter) -> float | None:
    denom = sum(counts.get(k, 0) for k in DECISIONS)
    if denom == 0:
        return None
    return counts.get("known-issue-recurrence", 0) / denom


def weekly_breakdown(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    weeks: dict[str, dict[str, Any]] = {}
    for row in entries:
        k = week_key(row["_dt"])
        w = weeks.setdefault(
            k,
            {"classes": Counter(), "alert_rows": 0, "surfaced": 0, "dm_suppressed": 0, "cost_usd": 0.0},
        )
        cls = row.get("classification") or "unknown"
        w["classes"][cls] += 1
        if cls not in NON_ALERT:
            w["alert_rows"] += 1
        if is_surfaced(row):
            w["surfaced"] += 1
        if is_dm_suppressed(row):
            w["dm_suppressed"] += 1
        try:
            w["cost_usd"] += float(row.get("runtime_cost_usd") or 0)
        except (TypeError, ValueError):
            pass
    for w in weeks.values():
        w["needs_human"] = w["classes"].get("needs-human", 0)
        w["kir"] = w["classes"].get("known-issue-recurrence", 0)
        w["kir_share"] = kir_share(w["classes"])
    return dict(sorted(weeks.items()))


def per_channel(entries: list[dict[str, Any]]) -> dict[str, Counter]:
    out: dict[str, Counter] = defaultdict(Counter)
    for row in entries:
        if row.get("classification") in NON_ALERT:
            continue
        ch = row.get("channel") or "(none)"
        out[ch][week_key(row["_dt"])] += 1
    return dict(out)


def per_kb_entry(entries: list[dict[str, Any]]) -> dict[str, Counter]:
    out: dict[str, Counter] = defaultdict(Counter)
    for row in entries:
        if row.get("classification") != "known-issue-recurrence":
            continue
        kb = row.get("matched_kb") or "(unmatched)"
        out[kb][week_key(row["_dt"])] += 1
    return dict(out)


def kb_fix_timeline(known_issues: list[dict[str, Any]], as_of: datetime) -> list[dict[str, Any]]:
    rows = []
    for ki in known_issues:
        last = parse_ts(ki.get("last_seen"))
        status = str(ki.get("fix_status") or "unknown")
        days = max(0, (as_of - last).days) if last else None
        fixed = status.lower() in FIXED
        rows.append(
            {
                "id": ki.get("id"),
                "first_seen": ki.get("first_seen"),
                "last_seen": ki.get("last_seen"),
                "occurrences": ki.get("occurrences") or 0,
                "fix_status": status,
                "days_since_last_seen": days,
                "state": "fixed" if fixed else "open",
            }
        )
    rows.sort(key=lambda r: -int(r["occurrences"] or 0))
    return rows


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def render_md(load: LoadResult, weeks, channels, kbs, timeline, top_kb: int = 10) -> str:
    out = []
    total = Counter()
    for w in weeks.values():
        total.update(w["classes"])
    first = min((e["_dt"] for e in load.entries), default=None)
    last = max((e["_dt"] for e in load.entries), default=None)
    out.append(f"Lines parsed: {len(load.entries)} (skipped {load.skipped}); "
               f"span {first:%Y-%m-%d %H:%MZ} -> {last:%Y-%m-%d %H:%MZ}" if first else "No entries.")
    out.append("")
    out.append("Classification totals: " + ", ".join(f"{k} {v}" for k, v in total.most_common()))
    out.append("")
    out.append("| Week | Alert rows | Needs-human | KIR | KIR share | Surfaced (DM/post) | Suppressed | Cost USD |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for k, w in weeks.items():
        out.append(f"| {k} | {w['alert_rows']} | {w['needs_human']} | {w['kir']} | {_pct(w['kir_share'])} | "
                   f"{w['surfaced']} | {w['dm_suppressed']} | {w['cost_usd']:.2f} |")
    week_ids = list(weeks)
    out.append("")
    out.append("| Channel | " + " | ".join(week_ids) + " | Total |")
    out.append("|---|" + "---:|" * (len(week_ids) + 1))
    for ch, c in sorted(channels.items(), key=lambda kv: -sum(kv[1].values())):
        out.append(f"| {ch} | " + " | ".join(str(c.get(w, 0)) for w in week_ids) + f" | {sum(c.values())} |")
    out.append("")
    out.append(f"Top {top_kb} KB entries by KIR rows:")
    out.append("")
    out.append("| KB entry | " + " | ".join(week_ids) + " | Total |")
    out.append("|---|" + "---:|" * (len(week_ids) + 1))
    for kb, c in sorted(kbs.items(), key=lambda kv: -sum(kv[1].values()))[:top_kb]:
        out.append(f"| {kb} | " + " | ".join(str(c.get(w, 0)) for w in week_ids) + f" | {sum(c.values())} |")
    out.append("")
    fixed = [r for r in timeline if r["state"] == "fixed"]
    out.append(f"KB entries: {len(timeline)} ({len(fixed)} fixed/mitigated, {len(timeline) - len(fixed)} open)")
    out.append("")
    out.append("| KB entry | Occurrences | fix_status | Last seen | Days since |")
    out.append("|---|---:|---|---|---:|")
    for r in timeline[:top_kb]:
        out.append(f"| {r['id']} | {r['occurrences']} | {r['fix_status']} | {r['last_seen']} | "
                   f"{'' if r['days_since_last_seen'] is None else r['days_since_last_seen']} |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--log", default="kb/incident-log.jsonl")
    p.add_argument("--kb", default="kb/known-issues.json")
    p.add_argument("--as-of", default=date.today().isoformat())
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument("--top-kb", type=int, default=10)
    p.add_argument("--ref", help="read --log/--kb from this git ref (e.g. origin/main) instead of the working tree")
    args = p.parse_args(argv)

    load = load_incident_log_lines(read_text(args.log, args.ref).splitlines())
    known = json.loads(read_text(args.kb, args.ref))
    as_of = parse_ts(args.as_of + "T00:00:00Z") if len(args.as_of) == 10 else parse_ts(args.as_of)
    weeks = weekly_breakdown(load.entries)
    channels = per_channel(load.entries)
    kbs = per_kb_entry(load.entries)
    timeline = kb_fix_timeline(known, as_of)

    if args.format == "json":
        json.dump(
            {
                "parsed": len(load.entries),
                "skipped": load.skipped,
                "weeks": {k: {**v, "classes": dict(v["classes"])} for k, v in weeks.items()},
                "channels": {k: dict(v) for k, v in channels.items()},
                "kb_entries": {k: dict(v) for k, v in kbs.items()},
                "kb_timeline": timeline,
            },
            sys.stdout,
            indent=2,
        )
        print()
    else:
        print(render_md(load, weeks, channels, kbs, timeline, args.top_kb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
