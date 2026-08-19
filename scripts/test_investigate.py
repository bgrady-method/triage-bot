"""Unit tests for investigate.py's signal derivation.

Run either way:
  python scripts/test_investigate.py       # no pytest needed — self-runs
  python -m pytest scripts/test_investigate.py

Covers the history-based signals that used to sit in MODEL_SUPPLIED_SIGNALS and
default to 0 — which biased the escalation score high (toward sending), because
four of the five inhibition signals were among them.
"""
from __future__ import annotations

import datetime

import investigate as I


# ---------------------------------------------------------------------------
# _parse_ts — three real shapes plus junk
# ---------------------------------------------------------------------------
def test_parse_ts_iso():
    got = I._parse_ts("2026-07-15T14:55:29Z")
    assert got == datetime.datetime(2026, 7, 15, 14, 55, 29, tzinfo=datetime.timezone.utc)


def test_parse_ts_slack_ts_string():
    # The CLI's own --ts format. Must NOT fall back to wall-clock now, or the
    # 30d/7d/today windows get computed around the wrong instant on a replay.
    got = I._parse_ts("1784121195.616799")
    assert got.year == 2026 and got.month == 7 and got.day == 15
    assert (got.hour, got.minute, got.second) == (13, 13, 15)


def test_parse_ts_epoch_int():
    assert I._parse_ts(1784121195).day == 15


def test_parse_ts_junk_returns_none():
    for v in ("garbage", "", None, True, {}, 12345):   # 12345 < 1e9 -> not an epoch
        assert I._parse_ts(v) is None, f"expected None for {v!r}"


# ---------------------------------------------------------------------------
# _was_posted — the false-alarm exclusion is load-bearing
# ---------------------------------------------------------------------------
def test_was_posted_counts_unsuppressed_finding():
    assert I._was_posted({"classification": "needs-human", "suppressed_dm": False})
    assert I._was_posted({"classification": "known-issue-recurrence", "suppressed_dm": False})


def test_was_posted_rejects_suppressed():
    assert not I._was_posted({"classification": "needs-human", "suppressed_dm": True})


def test_was_posted_rejects_false_alarm_despite_unsuppressed():
    # Regression: monitor 299551472 (ImportSubscriber No Data) is a false alarm on
    # 45 of 45 recorded fires, and every line carries suppressed_dm=false (nothing
    # was suppressed — the action was a kb-update, not a finding). Reading
    # suppressed_dm naively scored it dm_rate 0.94 -> maturity +1, i.e. the most
    # trustworthy monitor in the fleet. It is the exact opposite.
    assert not I._was_posted({"classification": "false-alarm", "suppressed_dm": False,
                              "action": "kb-update+self-dm"})


def test_was_posted_ignores_bookkeeping_lines():
    for cls in ("poll-cycle", "grouped", "heartbeat", "weekly-digest"):
        assert not I._was_posted({"classification": cls, "suppressed_dm": False})


# ---------------------------------------------------------------------------
# derive_history_signals
# ---------------------------------------------------------------------------
def _with_log(records):
    """Swap the module's log reader for a fixture; restore after."""
    original = I._iter_incident_log
    I._iter_incident_log = lambda: iter(records)
    return original


def test_derive_counts_fires_and_posts_in_30d():
    orig = _with_log([
        {"ts": "2026-07-14T10:00:00Z", "monitor_id": 111, "classification": "needs-human", "suppressed_dm": False},
        {"ts": "2026-07-13T10:00:00Z", "monitor_id": 111, "classification": "known-issue-recurrence", "suppressed_dm": True},
        {"ts": "2026-05-01T10:00:00Z", "monitor_id": 111, "classification": "needs-human", "suppressed_dm": False},  # >30d
        {"ts": "2026-07-14T10:00:00Z", "monitor_id": 999, "classification": "needs-human", "suppressed_dm": False},  # other monitor
    ])
    try:
        out = I.derive_history_signals(
            {"ts": "2026-07-15T12:00:00Z", "monitor_id": 111},
            {"hash": {"alert_hash": "abc"}, "kb-match": {"kind": None}})
        assert out["monitor_fire_count"] == 2, out      # 30d window excludes May
        assert out["monitor_dm_count"] == 1, out        # the suppressed one doesn't count
    finally:
        I._iter_incident_log = orig


def test_derive_fires_today_is_this_fires_ordinal():
    orig = _with_log([
        {"ts": "2026-07-15T08:00:00Z", "monitor_id": 111, "classification": "needs-human", "suppressed_dm": True},
        {"ts": "2026-07-15T09:00:00Z", "monitor_id": 111, "classification": "needs-human", "suppressed_dm": True},
    ])
    try:
        out = I.derive_history_signals(
            {"ts": "2026-07-15T12:00:00Z", "monitor_id": 111},
            {"hash": {"alert_hash": "abc"}, "kb-match": {"kind": None}})
        # two prior fires today -> this one is the 3rd; recency_decay floors at -2
        assert out["monitor_fires_today"] == 3, out
    finally:
        I._iter_incident_log = orig


def test_derive_ignores_events_at_or_after_this_alert():
    # A live cycle logs its own line BEFORE side-effects (Hard rule #6), so the
    # current alert is often already in the log. It must not count itself.
    orig = _with_log([
        {"ts": "2026-07-15T12:00:00Z", "monitor_id": 111, "classification": "needs-human", "suppressed_dm": False},
        {"ts": "2026-07-15T13:00:00Z", "monitor_id": 111, "classification": "needs-human", "suppressed_dm": False},
    ])
    try:
        out = I.derive_history_signals(
            {"ts": "2026-07-15T12:00:00Z", "monitor_id": 111},
            {"hash": {"alert_hash": "abc"}, "kb-match": {"kind": None}})
        assert out["monitor_fire_count"] == 0, out
        assert out["monitor_fires_today"] == 1, out     # itself only
    finally:
        I._iter_incident_log = orig


def test_derive_novel_true_when_no_kb_and_no_prior_hash():
    orig = _with_log([])
    try:
        out = I.derive_history_signals(
            {"ts": "2026-07-15T12:00:00Z", "monitor_id": None},
            {"hash": {"alert_hash": "abc"}, "kb-match": {"kind": None, "matched_id": None}})
        assert out["novel"] is True, out
        assert "monitor_fire_count" not in out, "no monitor_id -> omit, don't assume 0"
    finally:
        I._iter_incident_log = orig


def test_derive_novel_false_on_prior_same_hash_in_7d():
    orig = _with_log([
        {"ts": "2026-07-12T12:00:00Z", "alert_hash": "abc", "classification": "needs-human"},
    ])
    try:
        out = I.derive_history_signals(
            {"ts": "2026-07-15T12:00:00Z", "monitor_id": None},
            {"hash": {"alert_hash": "abc"}, "kb-match": {"kind": None, "matched_id": None}})
        assert out["novel"] is False, out
    finally:
        I._iter_incident_log = orig


def test_derive_novel_false_on_kb_match():
    orig = _with_log([])
    try:
        out = I.derive_history_signals(
            {"ts": "2026-07-15T12:00:00Z", "monitor_id": None},
            {"hash": {"alert_hash": "abc"},
             "kb-match": {"kind": "known-issue", "matched_id": "ki-x", "entry": {}}})
        assert out["novel"] is False, out
    finally:
        I._iter_incident_log = orig


def test_derive_recent_post_same_kb_24h_boundary():
    orig = _with_log([])
    try:
        near = I.derive_history_signals(
            {"ts": "2026-07-15T12:00:00Z", "monitor_id": None},
            {"hash": {"alert_hash": "abc"},
             "kb-match": {"kind": "known-issue", "matched_id": "ki-x",
                          "entry": {"last_notified_at": "2026-07-15T02:00:00Z"}}})
        assert near["recent_post_same_kb_24h"] is True, near

        far = I.derive_history_signals(
            {"ts": "2026-07-15T12:00:00Z", "monitor_id": None},
            {"hash": {"alert_hash": "abc"},
             "kb-match": {"kind": "known-issue", "matched_id": "ki-x",
                          "entry": {"last_notified_at": "2026-07-13T21:20:00Z"}}})
        assert far["recent_post_same_kb_24h"] is False, far   # the real case-03 value: 41h
    finally:
        I._iter_incident_log = orig


def test_derive_tolerates_malformed_log_lines():
    orig = _with_log([
        {"ts": 1784000000, "monitor_id": 111, "classification": "needs-human", "suppressed_dm": False},
        {"ts": None, "monitor_id": 111},
        {"monitor_id": 111},
        {"ts": "not-a-date", "monitor_id": 111},
    ])
    try:
        out = I.derive_history_signals(
            {"ts": "2026-07-15T12:00:00Z", "monitor_id": 111},
            {"hash": {"alert_hash": "abc"}, "kb-match": {"kind": None}})
        assert out["monitor_fire_count"] == 1, out   # only the epoch line is usable
    finally:
        I._iter_incident_log = orig


def test_model_supplied_signals_only_the_underivable():
    # Anything derivable from data on disk must NOT be here — an absent signal
    # contributes nothing, and the inhibition signals are negative.
    assert set(I.MODEL_SUPPLIED_SIGNALS) == {
        "deployed_within_2h", "metric", "operator_engaged", "swat_thread_mentions"}


# ---------------------------------------------------------------------------
# self-runner (so `python scripts/test_investigate.py` works without pytest)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failures}/{len(fns)} passed")
    sys.exit(1 if failures else 0)
