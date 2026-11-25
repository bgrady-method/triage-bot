"""Unit tests for retro_stats. Run: `python -m pytest scripts/test_retro_stats.py`."""

from __future__ import annotations

from datetime import datetime, timezone

from retro_stats import (
    kb_fix_timeline,
    is_dm_suppressed,
    is_surfaced,
    kir_share,
    load_incident_log_lines,
    parse_ts,
    per_channel,
    per_kb_entry,
    week_key,
    weekly_breakdown,
)

LINES = [
    '{"ts": "2026-06-07T23:59:00Z", "classification": "needs-human", "channel": "alert-system", "action": "dm-self"}',
    '{"ts":"2026-06-08T00:01:00Z","classification":"known-issue-recurrence","channel":"alert-system",'
    '"matched_kb":"ki-a","action":"actionable-append","suppressed_dm":true}',
    '{"ts": 1780876800, "classification": "grouped", "channel": "alert-system", "action": "grouped-with:x"}',
    '{"ts": "2026-06-08T01:00:00Z", "classification": "poll-cycle", "action": "summary", "runtime_cost_usd": 0.25}',
    "not json at all",
    "",
    '{"ts": "2026-06-08T02:00:00Z", "classification": "known-issue-recurrence", "channel": "alert-frontend-errors",'
    ' "matched_kb": "ki-a", "action": "dm-self", "suppressed_dm": false}',
    '{"ts": "2026-06-08T03:00:00Z", "classification": "needs-human", "action": "suppressed-dm (known-issue-window)"}',
]


def test_parse_ts_iso_epoch_and_bad():
    assert parse_ts("2026-06-08T00:01:00Z") == datetime(2026, 6, 8, 0, 1, tzinfo=timezone.utc)
    assert parse_ts(1780876800) == datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)
    assert parse_ts("1780876800") == datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)
    assert parse_ts("2026-06-08T00:01:00") == datetime(2026, 6, 8, 0, 1, tzinfo=timezone.utc)
    assert parse_ts("garbage") is None
    assert parse_ts(None) is None


def test_load_skips_malformed_and_handles_spacing():
    res = load_incident_log_lines(LINES)
    assert len(res.entries) == 6
    assert res.skipped == 1


def test_week_bucket_sunday_to_monday():
    sun = datetime(2026, 6, 7, 23, 59, tzinfo=timezone.utc)
    mon = datetime(2026, 6, 8, 0, 1, tzinfo=timezone.utc)
    assert week_key(sun) == "2026-W23"
    assert week_key(mon) == "2026-W24"


def test_weekly_breakdown_counts():
    weeks = weekly_breakdown(load_incident_log_lines(LINES).entries)
    assert list(weeks) == ["2026-W23", "2026-W24"]
    w23, w24 = weeks["2026-W23"], weeks["2026-W24"]
    assert w23["needs_human"] == 1 and w23["surfaced"] == 1
    # W24: KIR(suppressed), grouped, poll-cycle, KIR(dm), needs-human(suppressed)
    assert w24["alert_rows"] == 4  # poll-cycle excluded
    assert w24["kir"] == 2
    assert w24["surfaced"] == 1
    assert w24["dm_suppressed"] == 2
    assert abs(w24["cost_usd"] - 0.25) < 1e-9
    # grouped and poll-cycle do not enter the KIR-share denominator: 2 KIR / (2 KIR + 1 NH)
    assert abs(w24["kir_share"] - 2 / 3) < 1e-9


def test_kir_share_none_without_decisions():
    from collections import Counter

    assert kir_share(Counter({"grouped": 5, "poll-cycle": 3})) is None


def test_per_channel_and_kb():
    entries = load_incident_log_lines(LINES).entries
    ch = per_channel(entries)
    assert sum(ch["alert-system"].values()) == 3
    assert "(none)" in ch  # needs-human row without channel
    kb = per_kb_entry(entries)
    assert kb["ki-a"]["2026-W24"] == 2


def test_kb_fix_timeline():
    as_of = datetime(2026, 11, 25, tzinfo=timezone.utc)
    rows = kb_fix_timeline(
        [
            {"id": "ki-fixed", "last_seen": "2026-04-17T21:00:00Z", "occurrences": 1, "fix_status": "resolved"},
            {"id": "ki-chronic", "last_seen": "2026-06-18T12:00:00Z", "occurrences": 444,
             "fix_status": "chronic-residual"},
            {"id": "ki-nolast", "occurrences": 2, "fix_status": "needs-human"},
        ],
        as_of,
    )
    assert [r["id"] for r in rows] == ["ki-chronic", "ki-nolast", "ki-fixed"]
    by = {r["id"]: r for r in rows}
    assert by["ki-chronic"]["state"] == "open" and by["ki-chronic"]["days_since_last_seen"] == 159
    assert by["ki-fixed"]["state"] == "fixed"
    assert by["ki-nolast"]["days_since_last_seen"] is None


def test_surfaced_covers_dm_and_triage_results_posts():
    nh = "needs-human"
    assert is_surfaced({"classification": nh, "action": "dm-self"})
    assert is_surfaced({"classification": nh, "action": "post-triage-results"})
    assert is_surfaced({"classification": nh, "action": "kb-update + post to #triage-results"})
    assert not is_surfaced({"classification": nh, "action": "dm-self", "suppressed_dm": True})
    assert not is_surfaced({"classification": nh, "action": "no-send (degraded); kb-update self-dm"})
    assert not is_surfaced({"classification": nh, "action": "dm-self-blocked-by-classifier"})
    assert not is_surfaced({"classification": nh, "action": "actionable-append"})
    assert not is_surfaced({"classification": "poll-cycle", "action": "dm-self"})
    assert is_dm_suppressed({"classification": nh, "action": "kb-bump (suppressed, known-issue-window)"})
    sent = {"classification": nh, "action": "posted to #triage-results (past 24h suppression window)"}
    assert is_surfaced(sent) and not is_dm_suppressed(sent)


def test_cli_md_output(tmp_path, capsys):
    from retro_stats import main

    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(LINES), encoding="utf-8")
    kb = tmp_path / "kb.json"
    kb.write_text('[{"id": "ki-a", "last_seen": "2026-06-08T00:00:00Z", "occurrences": 2, "fix_status": "open"}]',
                  encoding="utf-8")
    assert main(["--log", str(log), "--kb", str(kb), "--as-of", "2026-06-10"]) == 0
    out = capsys.readouterr().out
    assert "Lines parsed: 6 (skipped 1)" in out
    assert "| 2026-W24 | 4 | 1 | 2 | 67% | 1 | 2 | 0.25 |" in out
    assert "| ki-a | 2 | open |" in out
