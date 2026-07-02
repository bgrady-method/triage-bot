import json
from pathlib import Path

CYCLE_TS = "2026-06-08T13:07:49Z"
LOG = Path("kb/incident-log.jsonl")

lines = []

lines.append({
    "ts": CYCLE_TS, "alert_hash": "31ad6c811417c664", "channel": "alert-frontend-errors",
    "classification": "grouped", "matched_kb": None, "confidence": None,
    "action": "grouped-with:0cf91190bd8b9368", "grouped_with": "0cf91190bd8b9368",
    "slack_ts": "1780920853.160059", "bot_id": "B011R3D650X",
    "duration_s": 0, "runtime_cost_usd": 0
})

lines.append({
    "ts": CYCLE_TS, "alert_hash": "0cf91190bd8b9368", "channel": "alert-frontend-errors",
    "classification": "known-issue-recurrence", "matched_kb": "ki-2026-05-21-gateway-microservices-timeout",
    "confidence": 0.95, "action": "suppressed-dm:known-issue-window",
    "grouped_alerts": ["0cf91190bd8b9368", "31ad6c811417c664"],
    "investigation_doc": "docs/investigations/2026-06-08-0cf91190bd8b9368.md",
    "slack_ts": "1780920733.839459", "bot_id": "B011R3D650X",
    "monitor_id": "77419271", "monitor_name": "Unusual number of XHR errors for account",
    "service_affected": "method-ui (frontend) -> ms-gateway-api -> microservices.methodlocal.int/syncutil",
    "suppressed_dm": True, "gate_reason": "known-issue-window", "kb_occurrences_after": 278,
    "bug_type_guess": "env",
    "escalation_score": 0,
    "score_breakdown": [
        {"signal": "matched_kb_inhibition", "delta": -3, "value": "ki-2026-05-21-gateway-microservices-timeout"},
        {"signal": "group_size_2", "delta": 1, "value": 2},
        {"signal": "critical_path_service", "delta": 3, "value": "ms-gateway-api", "source": "KB diagnosis"},
        {"signal": "metric_breach", "delta": 0, "value": "n/a (log-volume monitor)"},
        {"signal": "monitor_history", "delta": 0, "value": "77419271 chronic high-fire-count"},
        {"signal": "active_users_affected", "delta": 0, "value": 0, "source": "account_impact.py-skipped", "user_count_source": "cluster_lower_bound", "accounts_resolved": 0, "accounts_unresolved": 5, "accounts_inactive": 0, "notes": "5 distinct accounts in DD log sample; prod3/4/5 AlocetSystem chronic unconfigured"},
        {"signal": "cross_channel", "delta": 0, "value": 1},
        {"signal": "novel_no_kb_no_prior_hash_7d", "delta": 0, "value": False, "notes": "ki-21 evidence-based"},
        {"signal": "deploy_correlation_2h", "delta": 0, "value": "gh-api 403 chronic; KB chronic-residual post 2026-06-05 rollback"},
        {"signal": "recency_decay", "delta": 0, "value": "2nd ki-21 cluster today (1st 12:06Z)"},
        {"signal": "operator_engagement", "delta": 0, "value": "no thread replies on primary"},
        {"signal": "recent_dm_matched_kb_24h", "delta": -2, "value": "ki-21 last DM 12:07:35Z = 60min ago"}
    ],
    "hypothesis": "ki-21 chronic syncutil/syncwidget XHR errors. 2-alert cluster 12:12:13-12:14:13Z bot B011R3D650X. DD logs sampled 12:05-12:15Z = 5 distinct accounts all on /gateway/syncutil/syncwidget/<account>/GetSyncWidgetInfoAsync. ki-21 last_notified_at 12:07:35Z (60min ago) -> SUPPRESS known-issue-window. occ 277->278.",
    "duration_s": 0, "runtime_cost_usd": 0
})

for sat_hash, sat_ts in [
    ("8b15c5dff548ced9", "1780922248.320189"),
    ("9288ebe17a1c3189", "1780922375.276979"),
    ("33f10ff64eb57770", "1780922376.014599"),
]:
    lines.append({
        "ts": CYCLE_TS, "alert_hash": sat_hash, "channel": "alert-system",
        "classification": "grouped", "matched_kb": None, "confidence": None,
        "action": "grouped-with:7a9a44941f6774ec", "grouped_with": "7a9a44941f6774ec",
        "slack_ts": sat_ts, "bot_id": "B011R3D650X",
        "duration_s": 0, "runtime_cost_usd": 0
    })

lines.append({
    "ts": CYCLE_TS, "alert_hash": "7a9a44941f6774ec", "channel": "alert-system",
    "classification": "known-issue-recurrence", "matched_kb": "ki-2026-05-24-runtime-core-rtc-p95-recurring",
    "confidence": 0.85, "action": "dm-self",
    "grouped_alerts": ["7a9a44941f6774ec", "8b15c5dff548ced9", "9288ebe17a1c3189", "33f10ff64eb57770"],
    "investigation_doc": "docs/investigations/2026-06-08-7a9a44941f6774ec.md",
    "slack_ts": "1780921888.273169", "bot_id": "B011R3D650X",
    "monitor_id": "115456700+236570583", "monitor_name": "RTC Screen Load p95 (primary) + Watchdog New issue to review (overlay ki-29)",
    "service_affected": "runtime-core-api (post_/api/v1/runtime/load/_screenid*)",
    "suppressed_dm": False, "gate_reason": None, "kb_occurrences_after": 89,
    "bug_type_guess": "env",
    "escalation_score": 5,
    "score_breakdown": [
        {"signal": "matched_kb_inhibition", "delta": -3, "value": "ki-2026-05-24-runtime-core-rtc-p95-recurring"},
        {"signal": "group_size_3_4", "delta": 2, "value": 4},
        {"signal": "critical_path_service", "delta": 3, "value": "runtime-core-api", "source": "DD monitor 115456700"},
        {"signal": "metric_breach", "delta": 3, "value": {"observed_s": 10.56, "threshold_s": 3.0, "ratio": 2.52, "bracket": ">=2.0"}, "source": "DD metric p95 peak @ 12:29:50Z"},
        {"signal": "monitor_history", "delta": 0, "value": "115456700+117279738 fire_count>>5 dm_rate~0.4"},
        {"signal": "active_users_affected", "delta": 0, "value": 0, "source": "account_impact.py-not-applicable", "user_count_source": "named_only", "accounts_resolved": 0, "accounts_unresolved": 0, "accounts_inactive": 0, "notes": "block-only body; runtime-core DD logs lack account_name tag"},
        {"signal": "cross_channel", "delta": 0, "value": 1},
        {"signal": "novel_no_kb_no_prior_hash_7d", "delta": 0, "value": False, "notes": "ki-24 evidence-based"},
        {"signal": "deploy_correlation_2h", "delta": 0, "value": "gh-api 403 cycle 26; KB last deploy 2026-05-06"},
        {"signal": "recency_decay", "delta": 0, "value": "1st ki-24 cluster today"},
        {"signal": "operator_engagement", "delta": 0, "value": "no thread replies on primary"},
        {"signal": "recent_dm_matched_kb_24h", "delta": 0, "value": "ki-24 last DM 2026-06-07T11:22:03Z = 25h45m ago (past 24h)"}
    ],
    "hypothesis": "ki-24 RTC p95 chronic flap occ 89. 4-alert cluster 12:31:28-12:39:36Z bot B011R3D650X. DD monitor 115456700 Alert state last_triggered 12:37:20Z within 8s of sat1. Metric p95 peak 10.56s @ 12:29:50Z (ratio 2.52), 2nd burst peak 6.53s @ 12:36Z. Latency-only confirmed (0 runtime-core errors DD+ES 12:25-13:10Z). DUAL-MONITOR OVERLAY: 12:39:35+12:39:36 satellites align with monitor 236570583 last_triggered 12:39:33Z (ki-29 chronic watchdog noise overlay). ki-24 last_notified_at 2026-06-07T11:22:03Z = 25h45m past 24h -> DM, last_notified_at bumped to NOW.",
    "duration_s": 0, "runtime_cost_usd": 0
})

lines.append({
    "ts": CYCLE_TS, "alert_hash": "49a2932e1331b4ac", "channel": "alert-system",
    "classification": "known-issue-recurrence", "matched_kb": "ki-2026-05-24-runtime-core-rtc-p95-recurring",
    "confidence": 0.70, "action": "suppressed-dm:known-issue-window",
    "grouped_alerts": ["49a2932e1331b4ac"],
    "investigation_doc": "docs/investigations/2026-06-08-49a2932e1331b4ac.md",
    "slack_ts": "1780923931.872329", "bot_id": "B05PN7JG87L",
    "monitor_id": "115456700+117279738 (attributed by metric evidence)", "monitor_name": "RTC Screen Load + Action Execution co-fire @ 13:07:50Z",
    "service_affected": "runtime-core-api (post_/api/v1/runtime/load/_screenid* + post_/api/v1/runtime/_actionid_*)",
    "suppressed_dm": True, "gate_reason": "known-issue-window", "kb_occurrences_after": 90,
    "bug_type_guess": "env",
    "escalation_score": 0,
    "score_breakdown": [
        {"signal": "matched_kb_inhibition", "delta": -3, "value": "ki-2026-05-24-runtime-core-rtc-p95-recurring"},
        {"signal": "group_size_1", "delta": 0, "value": 1},
        {"signal": "critical_path_service", "delta": 3, "value": "runtime-core-api", "source": "DD metric evidence"},
        {"signal": "metric_breach", "delta": 3, "value": {"observed_s": 8.24, "threshold_s": 3.0, "ratio": 1.75, "bracket": "1.0-2.0 = +2; dual-endpoint canonical bumps to +3"}, "source": "DD metric p95 13:07:50-13:08:00Z both endpoints"},
        {"signal": "monitor_history", "delta": 0, "value": "115456700 chronic"},
        {"signal": "active_users_affected", "delta": 0, "value": 0, "source": "account_impact.py-not-applicable", "user_count_source": "named_only", "accounts_resolved": 0, "accounts_unresolved": 0, "accounts_inactive": 0, "notes": "block-only body"},
        {"signal": "cross_channel", "delta": 0, "value": 1},
        {"signal": "novel_no_kb_no_prior_hash_7d", "delta": 0, "value": False},
        {"signal": "deploy_correlation_2h", "delta": 0, "value": "gh-api 403 chronic"},
        {"signal": "recency_decay", "delta": -1, "value": "2nd ki-24 cluster today (G2 was 1st)"},
        {"signal": "operator_engagement", "delta": 0, "value": "no thread replies"},
        {"signal": "recent_dm_matched_kb_24h", "delta": -2, "value": "ki-24 last DM 13:07:49Z (G2 same cycle)"}
    ],
    "hypothesis": "ki-24 occ 90. Solo B05PN7JG87L alert 13:05:31Z. DD metric: RTC Screen Load p95 8.11s @ 13:07:50Z + 8.24s @ 13:08:00Z; RTC Action Execution p95 co-spiked 5.77s + 4.79s same instant -- canonical dual-endpoint shared-upstream signature. Alert 13:05:31Z precedes visible spike by ~2min (DD API returns only most-recent last_triggered; earlier fire likely overwritten). Latency-only confirmed. 2nd ki-24 cluster today after G2 (~26min apart). G2 DM bumped ki-24 last_notified_at to 13:07:49Z -> within 24h -> SUPPRESS. occ 89->90.",
    "duration_s": 0, "runtime_cost_usd": 0
})

with LOG.open('a', encoding='utf-8') as f:
    for line in lines:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

print(f"Appended {len(lines)} log lines")
