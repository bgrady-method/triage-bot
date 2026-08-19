"""Unit tests for score.py.

Run either way:
  python scripts/test_score.py            # no pytest needed — self-runs
  python -m pytest scripts/test_score.py
"""
from __future__ import annotations

import datetime

from score import (
    escalation_score, decide_escalation, suppression_gate,
    active_users_delta, group_size_delta, metric_breach_delta,
    account_tier_delta, monitor_maturity_delta, recency_decay_delta,
)


# ---------------------------------------------------------------------------
# bracket boundaries
# ---------------------------------------------------------------------------
def test_active_users_brackets():
    assert active_users_delta(0) == 0
    assert active_users_delta(20) == 0
    assert active_users_delta(21) == 1
    assert active_users_delta(100) == 1
    assert active_users_delta(101) == 2
    assert active_users_delta(500) == 2
    assert active_users_delta(501) == 3
    assert active_users_delta(2000) == 3
    assert active_users_delta(2001) == 4


def test_group_size_brackets():
    assert group_size_delta(1) == 0
    assert group_size_delta(2) == 1
    assert group_size_delta(4) == 2
    assert group_size_delta(5) == 3
    assert group_size_delta(9) == 3
    assert group_size_delta(10) == 4


def test_metric_breach_brackets():
    assert metric_breach_delta(None, 500) == (0, None)
    assert metric_breach_delta(700, 0) == (0, None)
    assert metric_breach_delta(600, 500)[0] == 0        # ratio 0.2
    assert metric_breach_delta(800, 500)[0] == 1        # ratio 0.6
    assert metric_breach_delta(1100, 500)[0] == 2       # ratio 1.2
    assert metric_breach_delta(1600, 500)[0] == 3       # ratio 2.2


def test_account_tier():
    assert account_tier_delta(["paid", "enterprise"]) == 2
    assert account_tier_delta(["paid", "paid"]) == 1
    assert account_tier_delta(["paid", "unknown"]) == 0
    assert account_tier_delta([]) == 0
    assert account_tier_delta(["free"]) == 0


def test_monitor_maturity():
    assert monitor_maturity_delta(4, 4) == 0            # unproven (fire_count<5)
    assert monitor_maturity_delta(20, 0) == -2          # dm_rate 0.0
    assert monitor_maturity_delta(10, 2) == -1          # dm_rate 0.2
    assert monitor_maturity_delta(10, 5) == 0           # dm_rate 0.5
    assert monitor_maturity_delta(10, 9) == 1           # dm_rate 0.9


def test_recency_decay():
    assert recency_decay_delta(1) == 0
    assert recency_decay_delta(2) == -1
    assert recency_decay_delta(3) == -2
    assert recency_decay_delta(9) == -2                 # floor


# ---------------------------------------------------------------------------
# escalation_score aggregation
# ---------------------------------------------------------------------------
def test_score_aggregates_and_records_breakdown():
    r = escalation_score({
        "critical_path_service": "ms-gateway-api",   # +3
        "active_users": 350,                          # +2
        "group_size": 3,                              # +2
        "deployed_within_2h": True,                   # +2
        "monitor_fires_today": 2,                     # -1
    })
    assert r["score"] == 8
    signals = {row["signal"] for row in r["breakdown"]}
    assert "critical_path_service" in signals
    assert "recency_decay" in signals
    # zero-delta signals are not recorded
    assert all(row["delta"] != 0 for row in r["breakdown"])


def test_known_issue_is_strong_inhibitor():
    r = escalation_score({"matched_kb": "ki-28", "active_users": 5, "group_size": 1})
    assert r["score"] == -3                            # only the -3 KB penalty


def test_empty_signals_score_zero():
    assert escalation_score({})["score"] == 0


# ---------------------------------------------------------------------------
# decision tree
# ---------------------------------------------------------------------------
def test_decide_swat_bypass():
    d = decide_escalation(-99, "swat", today_post_count=99)
    assert d["action"] == "post" and d["gate_reason"] == "swat-bypass"
    assert d["counts_against_cap"] is False
    assert decide_escalation(0, "team-incident-response", 99)["gate_reason"] == "swat-bypass"


def test_decide_scored_and_cap():
    assert decide_escalation(4, "alert-system", 0)["gate_reason"] == "scored"
    capped = decide_escalation(4, "alert-system", 5)
    assert capped["action"] == "actionable-high-borderline"
    assert capped["gate_reason"] == "daily-cap"


def test_decide_borderline_and_low():
    assert decide_escalation(2, "alert-system", 0)["action"] == "actionable-high-borderline"
    assert decide_escalation(1, "alert-system", 0)["action"] == "actionable-low-impact"


# ---------------------------------------------------------------------------
# suppression gate
# ---------------------------------------------------------------------------
NOW = "2026-07-02T12:00:00Z"


def test_gate_first_notification_posts():
    g = suppression_gate({"last_notified_at": None, "occurrences": 1}, NOW)
    assert g["suppress"] is False and g["gate_reason"] is None
    assert g["set_last_notified"] is True


def test_gate_within_window_suppresses():
    g = suppression_gate(
        {"last_notified_at": "2026-07-02T06:00:00Z", "occurrences": 3}, NOW)
    assert g["suppress"] is True and g["gate_reason"] == "known-issue-window"
    assert g["set_last_notified"] is False


def test_gate_window_elapsed_posts():
    g = suppression_gate(
        {"last_notified_at": "2026-07-01T06:00:00Z", "occurrences": 3}, NOW)
    assert g["suppress"] is False and g["gate_reason"] is None


def test_gate_every_tenth_resurfaces():
    g = suppression_gate(
        {"last_notified_at": "2026-07-02T11:00:00Z", "occurrences": 20}, NOW)
    assert g["suppress"] is False
    assert g["gate_reason"] == "known-issue-occurrence-resurface"


def test_gate_fix_status_change_posts():
    g = suppression_gate(
        {"last_notified_at": "2026-07-02T11:00:00Z", "occurrences": 3}, NOW,
        fix_status_changed=True)
    assert g["suppress"] is False
    assert g["gate_reason"] == "known-issue-fix-status-changed"


def test_gate_incident_channel_bypasses():
    g = suppression_gate(
        {"last_notified_at": "2026-07-02T11:59:00Z", "occurrences": 3}, NOW,
        is_incident_channel=True)
    assert g["suppress"] is False and g["gate_reason"] == "swat-bypass"


def test_gate_tenth_takes_precedence_over_fix_status():
    # occurrences%10==0 is checked before fix_status per prompt.md order
    g = suppression_gate(
        {"last_notified_at": "2026-07-02T11:00:00Z", "occurrences": 30}, NOW,
        fix_status_changed=True)
    assert g["gate_reason"] == "known-issue-occurrence-resurface"


# ---------------------------------------------------------------------------
# self-runner (so `python scripts/test_score.py` works without pytest)
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
