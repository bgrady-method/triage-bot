#!/usr/bin/env python3
"""One-shot: produce docs/investigations/<date>-<hash>.md for the top-N
alert_hashes from kb/incident-log.jsonl, drawing investigation content from
the matching DM body in docs/messages/. ES enrichment is deferred — the
production cluster has been returning 403 since 2026-05-01 (see
docs/messages/*/triage-bot-health.jsonl), so the original investigations
ran without ES; this backfill mirrors the DM findings to disk so they're
greppable and feed the stability-review.

Selection: prefer classification=needs-human, then has-DM, then by ts.

Usage:
    python scripts/backfill_investigations.py            # dry-run, prints plan
    python scripts/backfill_investigations.py --apply    # writes the .md files
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INCIDENT_LOG = REPO_ROOT / "kb" / "incident-log.jsonl"
MESSAGES_ROOT = REPO_ROOT / "docs" / "messages"
INVESTIGATIONS_ROOT = REPO_ROOT / "docs" / "investigations"


def load_incident_log() -> list[dict]:
    out = []
    with INCIDENT_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def load_dms() -> list[dict]:
    """Load every self-dm message body so we can match by alert_hash mention."""
    out = []
    for path in MESSAGES_ROOT.glob("*/self-dm.jsonl"):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def find_dm_for_hash(dms: list[dict], alert_hash: str, alert_ts: str) -> dict | None:
    """Pick the DM that mentions this alert_hash (in body) closest in time to the alert ts.
    Falls back to nearest-by-ts DM if hash isn't mentioned."""
    candidates_with_hash = [d for d in dms if alert_hash in d.get("body", "")]
    if candidates_with_hash:
        candidates_with_hash.sort(key=lambda d: abs(_iso_epoch(d["ts"]) - _iso_epoch(alert_ts)))
        return candidates_with_hash[0]
    nearby = [d for d in dms if abs(_iso_epoch(d["ts"]) - _iso_epoch(alert_ts)) < 3600]
    if nearby:
        nearby.sort(key=lambda d: abs(_iso_epoch(d["ts"]) - _iso_epoch(alert_ts)))
        return nearby[0]
    return None


def _iso_epoch(iso: str) -> float:
    """Parse an ISO-8601 string to epoch seconds, lenient on fractional seconds and Z."""
    if not iso:
        return 0.0
    s = iso.rstrip("Z")
    fmt_candidates = ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S")
    for fmt in fmt_candidates:
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue
    return 0.0


def select_top_n(entries: list[dict], dms: list[dict], n: int) -> list[dict]:
    """Score entries: +10 for classification=needs-human, +5 for has-DM,
    +count for occurrences, +1 for grouped-with."""
    counts = Counter(e["alert_hash"] for e in entries if e.get("alert_hash"))
    seen = set()
    deduped: list[dict] = []
    for entry in entries:
        h = entry.get("alert_hash")
        if not h or h in seen:
            continue
        seen.add(h)
        deduped.append(entry)

    def score(entry):
        h = entry["alert_hash"]
        s = 0
        cls = entry.get("classification", "")
        if cls == "needs-human":
            s += 10
        if cls == "grouped":
            s += 1
        s += counts.get(h, 1)
        if find_dm_for_hash(dms, h, entry.get("ts", "")):
            s += 5
        return s

    deduped.sort(key=lambda e: (-score(e), e.get("ts", "")))
    return deduped[:n]


def render_report(entry: dict, dm: dict | None, today: str) -> str:
    h = entry["alert_hash"]
    ts = entry.get("ts", "")
    date_only = ts.split("T")[0] if ts else today
    channel = entry.get("channel", "?")
    classification = entry.get("classification", "?")
    confidence = entry.get("confidence", "?")
    action = entry.get("action", "?")
    matched_kb = entry.get("matched_kb")

    lines = [
        f"# Investigation: {h} — {ts} (BACKFILLED {today})",
        "",
        "_Backfilled from incident-log + DM corpus on " + today + ". The original "
        "triage-bot run posted findings via DM to Ben but did not commit a "
        "`docs/investigations/` report on its branch (per the v0.7 prompt this is "
        "a recoverable gap). ES enrichment was deferred — the Logstash cluster has "
        "been returning HTTP 403 from the routine's environment since 2026-05-01 "
        "(see `docs/messages/*/triage-bot-health.jsonl`). Once ES auth is restored, "
        "a follow-up routine pass can re-enrich each backfilled report with fresh "
        "queries against the original time window._",
        "",
        "## Alert summary",
        f"- **Channel:** {channel}",
        f"- **Alert time:** {ts}",
        f"- **Alerts in group:** {1}  (logged singletons; group satellites tracked as separate alert_hashes in `kb/incident-log.jsonl`)",
        "",
        "## Classification",
        f"- **Result:** {classification}",
        f"- **Confidence:** {confidence}",
        f"- **Action taken:** {action}",
        f"- **Matched KB entry:** {matched_kb if matched_kb else 'none'}",
        "",
        "## DM transcript (canonical investigation content)",
        "",
    ]
    if dm:
        lines += [
            f"_Source DM at {dm['ts']}, channel `{dm.get('channel_name', '?')}`. Type: `{dm.get('message_type', '?')}`._",
            "",
            "```",
            dm["body"],
            "```",
            "",
        ]
    else:
        lines += [
            "_No matching DM found in `docs/messages/`. The alert may have been "
            "deduplicated against an earlier needs-human DM (see same-day messages "
            "for the channel) or originated before the message backfill window._",
            "",
        ]

    lines += [
        "## What we couldn't determine",
        "- ES exception breakdown for the alert window (cluster 403'd during original run; this backfill could not retry).",
        "- Datadog trace pivots beyond what the original DM captured.",
        "",
        "## Lessons / follow-up",
        "- Mirror DM findings to disk on the original branch (the v0.7 prompt mandates this; investigate why the cron's commit step was skipped — see `#triage-bot-health` health-status entries flagging push 403s on 2026-05-01).",
        "- Restore ES connectivity from the routine environment so future investigations populate the **Tools run** section with real query results, not the DM summary alone.",
        "",
        "## Original incident-log line",
        "",
        "```json",
        json.dumps(entry),
        "```",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = load_incident_log()
    dms = load_dms()
    print(f"loaded {len(entries)} incident-log lines, {len(dms)} DM messages", file=sys.stderr)

    top = select_top_n(entries, dms, args.n)
    print(f"selected top {len(top)} (preferring needs-human + has-DM)", file=sys.stderr)

    INVESTIGATIONS_ROOT.mkdir(parents=True, exist_ok=True)

    for entry in top:
        h = entry["alert_hash"]
        date_only = entry.get("ts", today).split("T")[0]
        path = INVESTIGATIONS_ROOT / f"{date_only}-{h}.md"
        if path.exists():
            print(f"skip (exists): {path}", file=sys.stderr)
            continue
        dm = find_dm_for_hash(dms, h, entry.get("ts", ""))
        body = render_report(entry, dm, today)
        if args.apply:
            path.write_text(body, encoding="utf-8")
            print(f"wrote {path}  (dm={'yes' if dm else 'no'}, classification={entry.get('classification')})", file=sys.stderr)
        else:
            print(f"would write {path}  (dm={'yes' if dm else 'no'}, classification={entry.get('classification')})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
