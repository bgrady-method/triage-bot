#!/usr/bin/env python3
"""
score.py — the triage bot's deterministic scoring + notification gates, extracted
from prompt.md (step 7) so the logic lives in one testable place instead of prose.

Two independent concerns, both pure (no I/O, no network, no clock reads except the
`now` you pass in):

  escalation_score(signals)        -> {score, breakdown[], threshold_hint}
      The impact + corroboration − inhibition rubric for `needs-human` alerts.
      Consumes already-observed signals (the caller does the querying); this module
      only turns signals into deltas + a total. Mirrors the tables at prompt.md
      "Impact/Corroboration/Inhibition signals".

  decide_escalation(score, channel_name, today_post_count, cfg)
                                   -> {action, gate_reason, counts_against_cap}
      The step-7 decision tree (swat-bypass / scored / high-borderline / low-impact).

  suppression_gate(entry, now, *, is_incident_channel, fix_status_changed, cfg)
                                   -> {suppress, gate_reason, set_last_notified}
      Layer-1 known-issue-recurrence notification gate (last_notified_at window /
      every-10th resurface / fix-status change / swat-bypass).

Design note: the caller (investigate.py / the routine) is responsible for *gathering*
signals — account_impact counts, deploy correlation, monitor history greps, KB match.
This module is deliberately dependency-free so `test_score.py` can exercise every
bracket boundary without a live environment.
"""
from __future__ import annotations
import datetime
from typing import Any

# Defaults mirror kb/config.json; callers pass a cfg dict to override.
DEFAULT_CFG = {
    "escalation_score_threshold": 4,
    "actionable_score_threshold": 2,
    "daily_escalation_cap": 5,
    "suppression_window_hours": 24,
    "critical_path_services": [
        "ms-gateway-api", "ms-authentication-api", "oauth2",
        "ms-tables-fields-api", "runtime-core",
    ],
}

INCIDENT_CHANNELS = ("swat", "team-incident-response")


# ---------------------------------------------------------------------------
# time helpers
# ---------------------------------------------------------------------------
def parse_ts(ts: Any) -> datetime.datetime | None:
    """Parse an ISO-8601 'Z' timestamp (or datetime) to an aware UTC datetime."""
    if ts is None or ts == "":
        return None
    if isinstance(ts, datetime.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=datetime.timezone.utc)
    s = str(ts).strip().replace("Z", "+00:00")
    dt = datetime.datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# per-signal bracket functions (each returns an int delta)
# ---------------------------------------------------------------------------
def active_users_delta(n: int) -> int:
    """prompt.md: ≤20→0, 21–100→+1, 101–500→+2, 501–2000→+3, 2001+→+4."""
    if n <= 20:
        return 0
    if n <= 100:
        return 1
    if n <= 500:
        return 2
    if n <= 2000:
        return 3
    return 4


def group_size_delta(n: int) -> int:
    """1→0, 2→+1, 3–4→+2, 5–9→+3, ≥10→+4."""
    if n <= 1:
        return 0
    if n == 2:
        return 1
    if n <= 4:
        return 2
    if n <= 9:
        return 3
    return 4


def metric_breach_delta(observed: float | None, threshold: float | None):
    """ratio=(observed-threshold)/threshold: <0.5→0, 0.5–1→+1, 1–2→+2, ≥2→+3.

    Returns (delta, ratio|None). ratio is None when inputs are missing/zero.
    """
    if observed is None or threshold in (None, 0):
        return 0, None
    ratio = (observed - threshold) / threshold
    if ratio < 0.5:
        d = 0
    elif ratio < 1.0:
        d = 1
    elif ratio < 2.0:
        d = 2
    else:
        d = 3
    return d, ratio


def account_tier_delta(tiers: list[str]) -> int:
    """any enterprise→+2; else all paid (and ≥1)→+1; else 0."""
    tset = [t for t in (tiers or []) if t]
    if any(t == "enterprise" for t in tset):
        return 2
    if tset and all(t == "paid" for t in tset):
        return 1
    return 0


def monitor_maturity_delta(fire_count: int, dm_count: int) -> int:
    """fire_count<5→0; else by dm_rate: <0.1→−2, 0.1–0.4→−1, 0.4–0.8→0, ≥0.8→+1."""
    if fire_count < 5:
        return 0
    dm_rate = dm_count / fire_count if fire_count else 0.0
    if dm_rate < 0.1:
        return -2
    if dm_rate < 0.4:
        return -1
    if dm_rate < 0.8:
        return 0
    return 1


def recency_decay_delta(fires_today: int) -> int:
    """Same monitor same UTC day: 1st→0, 2nd→−1, 3rd+→−2 (floor)."""
    if fires_today <= 1:
        return 0
    if fires_today == 2:
        return -1
    return -2


# ---------------------------------------------------------------------------
# escalation score
# ---------------------------------------------------------------------------
def escalation_score(signals: dict, cfg: dict | None = None) -> dict:
    """Turn observed signals into {score, breakdown, threshold_hint}.

    `signals` keys (all optional; absent → contributes 0):
      critical_path_service   str|None  matched service on the critical path
      active_users            int       sum of total_active_users (status:ok)
      user_count_source       str       audit tag carried into the breakdown row
      accounts_resolved/unresolved/inactive  int  audit metadata
      deployed_within_2h      bool
      metric                  {observed, threshold}|None
      account_tiers           [str]     tiers of status:ok accounts
      group_size              int       # alerts in the root-cause cluster
      distinct_channels       int       # distinct channel_names across satellites
      novel                   bool      no KB match AND no same-hash alert in 7d
      swat_thread_mentions    bool      active swat thread names same service/bot
      matched_kb              str|None  KB id if this matched a known issue
      operator_engaged        bool      non-bot/non-Ben reply on primary.ts <30m
      recent_post_same_kb_24h bool      same matched_kb already posted today
      monitor_fire_count      int       fires for this monitor_id in last 30d
      monitor_dm_count        int       of those, how many were posted
      monitor_fires_today     int       this monitor_id's fires in today's log
    """
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    breakdown: list[dict] = []

    def add(signal, delta, **detail):
        if delta:
            breakdown.append({"signal": signal, "delta": delta, **detail})

    # --- impact ---
    if signals.get("critical_path_service"):
        add("critical_path_service", 3, value=signals["critical_path_service"])

    if "active_users" in signals:
        n = int(signals.get("active_users") or 0)
        add("active_users_affected", active_users_delta(n),
            value=n,
            user_count_source=signals.get("user_count_source", "named_only"),
            accounts_resolved=signals.get("accounts_resolved"),
            accounts_unresolved=signals.get("accounts_unresolved"),
            accounts_inactive=signals.get("accounts_inactive"))

    if signals.get("deployed_within_2h"):
        add("deployed_within_2h", 2)

    metric = signals.get("metric")
    if metric:
        d, ratio = metric_breach_delta(metric.get("observed"), metric.get("threshold"))
        add("metric_breach", d, observed=metric.get("observed"),
            threshold=metric.get("threshold"), ratio=ratio)

    if signals.get("account_tiers"):
        add("account_tier", account_tier_delta(signals["account_tiers"]),
            tiers=signals["account_tiers"])

    # --- corroboration ---
    if "group_size" in signals:
        add("group_size", group_size_delta(int(signals["group_size"])),
            value=int(signals["group_size"]))

    if int(signals.get("distinct_channels") or 0) >= 2:
        add("cross_channel_cofiring", 2, value=int(signals["distinct_channels"]))

    if signals.get("novel"):
        add("truly_novel", 2)

    if signals.get("swat_thread_mentions"):
        add("swat_thread_mentions_service", 1)

    # --- inhibition ---
    if signals.get("matched_kb"):
        add("matched_kb", -3, value=signals["matched_kb"])

    if signals.get("operator_engaged"):
        add("operator_engaged", -3)

    if signals.get("recent_post_same_kb_24h"):
        add("recent_post_same_kb", -2)

    if "monitor_fire_count" in signals:
        add("monitor_maturity",
            monitor_maturity_delta(int(signals.get("monitor_fire_count") or 0),
                                   int(signals.get("monitor_dm_count") or 0)),
            fire_count=int(signals.get("monitor_fire_count") or 0),
            dm_count=int(signals.get("monitor_dm_count") or 0))

    if "monitor_fires_today" in signals:
        add("recency_decay", recency_decay_delta(int(signals["monitor_fires_today"])),
            fires_today=int(signals["monitor_fires_today"]))

    score = sum(row["delta"] for row in breakdown)
    return {
        "score": score,
        "breakdown": breakdown,
        "threshold_hint": cfg["escalation_score_threshold"],
    }


def decide_escalation(score: int, channel_name: str, today_post_count: int,
                      cfg: dict | None = None) -> dict:
    """The step-7 decision tree. Returns {action, gate_reason, counts_against_cap}.

    action ∈ {"post", "actionable-high-borderline", "actionable-low-impact"}.
    """
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    if channel_name in INCIDENT_CHANNELS:
        return {"action": "post", "gate_reason": "swat-bypass",
                "counts_against_cap": False}
    if score >= cfg["escalation_score_threshold"]:
        if today_post_count < cfg["daily_escalation_cap"]:
            return {"action": "post", "gate_reason": "scored",
                    "counts_against_cap": True}
        return {"action": "actionable-high-borderline", "gate_reason": "daily-cap",
                "counts_against_cap": False}
    if score >= cfg["actionable_score_threshold"]:
        return {"action": "actionable-high-borderline", "gate_reason": "low-impact",
                "counts_against_cap": False}
    return {"action": "actionable-low-impact", "gate_reason": "low-impact",
            "counts_against_cap": False}


# ---------------------------------------------------------------------------
# known-issue-recurrence suppression gate (Layer 1)
# ---------------------------------------------------------------------------
def suppression_gate(entry: dict, now: Any, *, is_incident_channel: bool = False,
                     fix_status_changed: bool = False, cfg: dict | None = None) -> dict:
    """Decide whether to post a known-issue-recurrence finding.

    Returns {suppress: bool, gate_reason: str|None, set_last_notified: bool}.
    Mirrors prompt.md step 7 "Decide whether to notify (Layer 1)".
    """
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    window_h = cfg["suppression_window_hours"]
    now_dt = parse_ts(now)
    last = parse_ts(entry.get("last_notified_at"))
    occurrences = int(entry.get("occurrences") or 0)

    def post(reason):
        return {"suppress": False, "gate_reason": reason, "set_last_notified": True}

    if is_incident_channel:
        return post("swat-bypass")
    if last is None:
        return post(None)
    if (now_dt - last) > datetime.timedelta(hours=window_h):
        return post(None)
    if occurrences % 10 == 0 and occurrences > 0:
        return post("known-issue-occurrence-resurface")
    if fix_status_changed:
        return post("known-issue-fix-status-changed")
    return {"suppress": True, "gate_reason": "known-issue-window",
            "set_last_notified": False}


if __name__ == "__main__":
    # Tiny smoke demo when run directly.
    import json
    demo = escalation_score({
        "critical_path_service": "ms-gateway-api",
        "active_users": 350, "group_size": 3, "matched_kb": None,
        "monitor_fire_count": 12, "monitor_dm_count": 1, "monitor_fires_today": 2,
    })
    print(json.dumps(demo, indent=2))
    print(decide_escalation(demo["score"], "alert-system", 0))
