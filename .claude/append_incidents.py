import json

CYCLE_TS = "2026-06-08T18:08:00Z"
NOW = "2026-06-08T18:18:17Z"

lines = []

g1_primary = {
    "ts": CYCLE_TS,
    "alert_hash": "4f0022af0c857ac8",
    "channel": "alert-system",
    "classification": "known-issue-recurrence",
    "matched_kb": "ki-2026-05-21-gateway-microservices-timeout",
    "confidence": 0.65,
    "action": "suppressed-dm:known-issue-window",
    "grouped_alerts": ["4f0022af0c857ac8", "710bbd405ce4cb64"],
    "investigation_doc": "docs/investigations/2026-06-08-4f0022af0c857ac8.md",
    "slack_ts": "1780938354.220359",
    "bot_id": "B03GBAMHUTB",
    "monitor_id": None,
    "monitor_name": "Centreon B03GBAMHUTB Flow Designer Connector paired-fire (empty body)",
    "service_affected": "ms-gateway-api via ki-21 cascade hypothesis (cross-correlated with ki-24 G2 157s later)",
    "suppressed_dm": True,
    "gate_reason": "known-issue-window",
    "kb_occurrences_after": 299,
    "bug_type_guess": "env",
    "escalation_score": -1,
    "score_breakdown": [
        {"signal": "matched_kb_inhibition", "delta": -3, "value": "ki-2026-05-21-gateway-microservices-timeout"},
        {"signal": "group_size_2", "delta": 1, "value": 2},
        {"signal": "critical_path_service", "delta": 3, "value": "ms-gateway-api", "source": "cascade hypothesis"},
        {"signal": "metric_breach", "delta": 0, "value": "n/a (Centreon)"},
        {"signal": "monitor_history", "delta": 0, "value": "no DD monitor_id (Centreon)"},
        {"signal": "active_users_affected", "delta": 0, "value": 0, "source": "account_impact.py-skipped", "user_count_source": "named_only", "accounts_resolved": 0, "accounts_unresolved": 0, "accounts_inactive": 0, "notes": "block-only body"},
        {"signal": "cross_channel", "delta": 0, "value": 1, "notes": "within group single channel; cross-correlation with G2 ki-24 (157s later) is cross-group"},
        {"signal": "novel_no_kb_no_prior_hash_7d", "delta": 0, "value": False, "notes": "B03GBAMHUTB-Centreon-ki-21-cascade precedent (15:08Z G3 + G5 today)"},
        {"signal": "deploy_correlation_2h", "delta": 0, "value": "gh-api 403 chronic cycle 31"},
        {"signal": "recency_decay", "delta": 0, "value": "no monitor_id (Centreon)"},
        {"signal": "operator_engagement", "delta": 0, "value": "no thread replies"},
        {"signal": "recent_dm_matched_kb_24h", "delta": -2, "value": "ki-21 last DM 12:07:35Z ~6h ago (in 24h window)"},
        {"signal": "account_tier", "delta": 0, "value": "no accounts"}
    ],
    "hypothesis": "B03GBAMHUTB Centreon paired-fire 17:05:54Z + 17:05:57Z (3s gap = canonical synthetic dual-trigger). ki-29 RULED OUT (0 NRE hits ES 17:00-17:10Z). ki-21 cascade-downstream hypothesis (same pattern as today 14:13Z + 14:55-15:00Z B03GBAMHUTB precedents). ki-21 last DM ~6h ago -> SUPPRESS known-issue-window. Contributes 2 occurrences to ki-21 total. Cross-channel: G2 ki-24 fired 157s later (5th ki-21+ki-24 co-firing today).",
    "duration_s": 0,
    "runtime_cost_usd": 0
}
g1_sat = {
    "ts": CYCLE_TS,
    "alert_hash": "710bbd405ce4cb64",
    "channel": "alert-system",
    "classification": "grouped",
    "matched_kb": None,
    "confidence": None,
    "action": "grouped-with:4f0022af0c857ac8",
    "grouped_with": "4f0022af0c857ac8",
    "slack_ts": "1780938357.670259",
    "bot_id": "B03GBAMHUTB",
    "duration_s": 0,
    "runtime_cost_usd": 0
}
lines.append(g1_primary)
lines.append(g1_sat)

g2_primary = {
    "ts": CYCLE_TS,
    "alert_hash": "63d17ee78a22837d",
    "channel": "alert-system",
    "classification": "known-issue-recurrence",
    "matched_kb": "ki-2026-05-24-runtime-core-rtc-p95-recurring",
    "confidence": 0.95,
    "action": "dm-self",
    "grouped_alerts": ["63d17ee78a22837d"],
    "investigation_doc": "docs/investigations/2026-06-08-63d17ee78a22837d.md",
    "slack_ts": "1780938511.526869",
    "bot_id": "B05PN7JG87L",
    "monitor_id": "115456700",
    "monitor_name": "RTC Screen Load has a high p95 latency (forwarder fire — monitor underlying triggered)",
    "service_affected": "runtime-core-api (Screen Load p95 peak 7.275s @ 17:00:30Z; co-spike Action Execution 3.621s @ 17:04:30Z)",
    "suppressed_dm": False,
    "gate_reason": "known-issue-occurrence-resurface",
    "kb_occurrences_after": 100,
    "bug_type_guess": "env",
    "escalation_score": 0,
    "score_breakdown": [
        {"signal": "matched_kb_inhibition", "delta": -3, "value": "ki-2026-05-24-runtime-core-rtc-p95-recurring"},
        {"signal": "group_size_1", "delta": 0, "value": 1},
        {"signal": "critical_path_service", "delta": 3, "value": "runtime-core-api", "source": "DD metric direct alignment + monitor 115456700 last_triggered 17:01:20Z"},
        {"signal": "metric_breach", "delta": 2, "value": {"observed_s": 7.275, "threshold_s": 3.0, "ratio": 1.425, "bracket": "1.0-2.0"}, "source": "DD metric Screen Load peak @ 17:00:30Z, 481s before alert; co-spike Action Execution 3.621s @ 17:04:30Z"},
        {"signal": "monitor_history", "delta": 0, "value": "115456700 chronic dm_rate 0.4-0.8"},
        {"signal": "active_users_affected", "delta": 0, "value": 0, "source": "account_impact.py-skipped", "user_count_source": "named_only", "accounts_resolved": 0, "accounts_unresolved": 0, "accounts_inactive": 0, "notes": "block-only body"},
        {"signal": "cross_channel", "delta": 0, "value": 1, "notes": "singleton; cross-group co-firing with G1 ki-21 (157s earlier) noted"},
        {"signal": "novel_no_kb_no_prior_hash_7d", "delta": 0, "value": False},
        {"signal": "deploy_correlation_2h", "delta": 0, "value": "gh-api 403 chronic cycle 31"},
        {"signal": "recency_decay", "delta": -2, "value": "10th ki-24 cluster today (monitor 115456700); floor"},
        {"signal": "operator_engagement", "delta": 0, "value": "no thread replies"},
        {"signal": "recent_dm_matched_kb_24h", "delta": -2, "value": "ki-24 last DM 13:07:49Z ~5h ago (in 24h window) - but 10x resurface gate overrides"},
        {"signal": "account_tier", "delta": 0, "value": "no accounts"}
    ],
    "hypothesis": "ki-24 sustained-burst onset. Screen Load p95 peak 7.275s @ 17:00:30Z (ratio 1.425) followed by 5.335s @ 17:03:30Z and 5.172s @ 17:04:20Z. Co-spike Action Execution 3.351s @ 17:03:30Z + 3.621s @ 17:04:30Z = canonical shared-upstream signature. B05PN7JG87L forwarder fired 17:08:31Z = 481s after peak (longer than typical 76-135s lag - likely caught trailing samples). Latency-only (0 ES runtime-core errors). Monitor 115456700 last_triggered 17:01:20Z confirms underlying threshold breach. **occ 99 -> 100: 10x resurface threshold reached -> DM (gate_reason=known-issue-occurrence-resurface)**. 5th cross-channel ki-21+ki-24 co-firing today (G1 17:05:54Z + G2 17:08:31Z, 157s apart).",
    "duration_s": 0,
    "runtime_cost_usd": 0
}
lines.append(g2_primary)

g3_primary = {
    "ts": CYCLE_TS,
    "alert_hash": "897f997dbbcd80be",
    "channel": "alert-frontend-errors",
    "classification": "known-issue-recurrence",
    "matched_kb": "ki-2026-05-21-gateway-microservices-timeout",
    "confidence": 0.95,
    "action": "suppressed-dm:known-issue-window",
    "grouped_alerts": ["897f997dbbcd80be", "dfdb1f4df84a562a", "e9756d68db3eae0a", "a99d87d9afc3605e"],
    "investigation_doc": "docs/investigations/2026-06-08-897f997dbbcd80be.md",
    "slack_ts": "1780939153.508249",
    "bot_id": "B011R3D650X",
    "monitor_id": "77419271",
    "monitor_name": "Unusual number of XHR errors for account",
    "service_affected": "method-ui (frontend) -> ms-gateway-api -> microservices.methodlocal.int/syncutil/syncwidget",
    "suppressed_dm": True,
    "gate_reason": "known-issue-window",
    "kb_occurrences_after": 303,
    "bug_type_guess": "env",
    "escalation_score": -1,
    "score_breakdown": [
        {"signal": "matched_kb_inhibition", "delta": -3, "value": "ki-2026-05-21-gateway-microservices-timeout"},
        {"signal": "group_size_3_4", "delta": 2, "value": 4},
        {"signal": "critical_path_service", "delta": 3, "value": "ms-gateway-api", "source": "KB diagnosis + DD logs syncutil/syncwidget URL pattern across 5+ accounts"},
        {"signal": "metric_breach", "delta": 0, "value": "n/a (log-volume monitor 77419271)"},
        {"signal": "monitor_history", "delta": 0, "value": "77419271 chronic dm_rate 0.4-0.8"},
        {"signal": "active_users_affected", "delta": 0, "value": 0, "source": "account_impact.py-skipped", "user_count_source": "cluster_lower_bound", "accounts_resolved": 0, "accounts_unresolved": 0, "accounts_inactive": 0, "notes": "chronic suppression-gate; many accounts in DD logs (fleeteforce, mobilitycityofcoloradosprings, primroseventuresllc, silverbackcommunicationsllcCo1, crslaboratories, etc.) but block-only Slack body - extrapolation: cluster_lower_bound infrastructure pattern, all accounts on shared gateway"},
        {"signal": "cross_channel", "delta": 0, "value": 1, "notes": "within group single channel"},
        {"signal": "novel_no_kb_no_prior_hash_7d", "delta": 0, "value": False, "notes": "ki-21 evidence-based"},
        {"signal": "deploy_correlation_2h", "delta": 0, "value": "gh-api 403 chronic cycle 31"},
        {"signal": "recency_decay", "delta": -2, "value": "3rd ki-21 cluster today; floor"},
        {"signal": "operator_engagement", "delta": 0, "value": "no thread replies"},
        {"signal": "recent_dm_matched_kb_24h", "delta": -2, "value": "ki-21 last DM 12:07:35Z ~6h ago"},
        {"signal": "account_tier", "delta": 0, "value": "no accounts"}
    ],
    "hypothesis": "ki-21 chronic syncutil/syncwidget XHR errors. 4-alert cluster 17:19:13-17:41:13Z bot B011R3D650X in alert-frontend-errors. Monitor 77419271 last_triggered 17:41:12Z aligns within 1s of satellite a99d87d9afc3605e (canonical direct attribution). DD logs confirm XHR error GET /gateway/syncutil/syncwidget/<account>/GetSyncWidgetInfoAsync with http.status_code:0 (timeout) across 5+ distinct accounts (fleeteforce, mobilitycityofcoloradosprings, primroseventuresllc, silverbackcommunicationsllcCo1, crslaboratories) - canonical ki-21 signature. ki-21 last DM 12:07:35Z (~6h ago) -> SUPPRESS known-issue-window. occ 297->303 across G1 (+2) + G3 (+4).",
    "duration_s": 0,
    "runtime_cost_usd": 0
}
g3_sats = []
for sh, sts in [("dfdb1f4df84a562a", "1780939272.486289"), ("e9756d68db3eae0a", "1780940353.346449"), ("a99d87d9afc3605e", "1780940473.411479")]:
    g3_sats.append({
        "ts": CYCLE_TS,
        "alert_hash": sh,
        "channel": "alert-frontend-errors",
        "classification": "grouped",
        "matched_kb": None,
        "confidence": None,
        "action": "grouped-with:897f997dbbcd80be",
        "grouped_with": "897f997dbbcd80be",
        "slack_ts": sts,
        "bot_id": "B011R3D650X",
        "duration_s": 0,
        "runtime_cost_usd": 0
    })
lines.append(g3_primary)
lines.extend(g3_sats)

g4_primary = {
    "ts": CYCLE_TS,
    "alert_hash": "3d54e58d7078448b",
    "channel": "alert-runtime-monitoring",
    "classification": "needs-human",
    "matched_kb": None,
    "confidence": 0.55,
    "action": "suppressed-dm:low-impact",
    "grouped_alerts": ["3d54e58d7078448b"],
    "investigation_doc": "docs/investigations/2026-06-08-3d54e58d7078448b.md",
    "slack_ts": "1780941583.097099",
    "bot_id": "B063S8NBW0M",
    "monitor_id": None,
    "monitor_name": None,
    "service_affected": "runtime-core-api (inferred channel routing + Screen Load p95 mini-breach 3.565s @ 17:51:00Z; specific monitor unknown - block-only body)",
    "suppressed_dm": True,
    "gate_reason": "low-impact",
    "kb_occurrences_after": None,
    "bug_type_guess": "unknown",
    "escalation_score": 2,
    "score_breakdown": [
        {"signal": "novel_no_kb_no_prior_hash_7d", "delta": 2, "value": True, "notes": "hash 3d54e58d7078448b first seen; no KB match"},
        {"signal": "group_size_1", "delta": 0, "value": 1, "notes": "singleton"},
        {"signal": "critical_path_service", "delta": 0, "value": None, "notes": "runtime-core-api inferred via channel routing + DD metric Screen Load mini-breach but no monitor alignment +/-60s (9-minute lag); conservative 0 per 4eff228c4786b810 14:18Z precedent"},
        {"signal": "metric_breach", "delta": 0, "value": {"observed_s": 3.565, "threshold_s": 3.0, "ratio": 0.188, "bracket": "<0.5"}, "source": "DD metric Screen Load p95 peak @ 17:51:00Z = 523s before alert; Action Execution sub-threshold"},
        {"signal": "monitor_history", "delta": 0, "value": "unknown monitor_id (block-only body)"},
        {"signal": "active_users_affected", "delta": 0, "value": 0, "source": "account_impact.py-skipped", "user_count_source": "named_only", "accounts_resolved": 0, "accounts_unresolved": 0, "accounts_inactive": 0, "notes": "block-only body, no @account_name"},
        {"signal": "cross_channel", "delta": 0, "value": 1, "notes": "singleton; G3 ki-21 ended 17:41:13Z (18min earlier, different channel) - not within-group"},
        {"signal": "deploy_correlation_2h", "delta": 0, "value": "gh-api 403 chronic cycle 31"},
        {"signal": "recency_decay", "delta": 0, "value": "no monitor_id (B063S8NBW0M proxy: 2nd today vs 4eff228c4786b810 at 14:05:31Z); convention 0 per past"},
        {"signal": "operator_engagement", "delta": 0, "value": "no thread replies"},
        {"signal": "recent_dm_matched_kb_24h", "delta": 0, "value": "no KB match"},
        {"signal": "account_tier", "delta": 0, "value": "no accounts"}
    ],
    "hypothesis": "B063S8NBW0M singleton 17:59:43Z alert-runtime-monitoring with empty Slack body (chronic MCP gap). DD metric Screen Load p95 mini-breach 3.565s @ 17:51:00Z (ratio 0.188, bracket <0.5) - 523s (~9 min) before alert. Action Execution sub-threshold across full G4 window. Long lag from Screen Load peak rules out forwarder of monitor 115456700/117279738. Likely DD APM Watchdog story for runtime-core-api (consistent with 14:05:31Z precedent 4eff228c4786b810). 0 long Action Exec traces >2.5s in window (DD logs). 0 ES runtime-core errors. Tail of broader ki-24 chronic flap possible (10th ki-24 cluster today) but unconfirmed without APM trace search (standing ask #7). 2nd B063S8NBW0M today (precedent 1: 14:05:31Z score 2; this: also score 2 novel only) -> actionable low-impact.",
    "duration_s": 0,
    "runtime_cost_usd": 0
}
lines.append(g4_primary)

cycle_summary = {
    "ts": CYCLE_TS,
    "alert_hash": None,
    "channel": None,
    "classification": "poll-cycle",
    "matched_kb": None,
    "confidence": None,
    "action": "summary",
    "details": {
        "polled": 8,
        "groups": 4,
        "new": 4,
        "deduped": 0,
        "satellites_added": 4,
        "failed": 0,
        "dms_sent": 1,
        "actionable_appended": 3,
        "gate_reasons": {"known-issue-window": 2, "known-issue-occurrence-resurface": 1, "low-impact": 1},
        "kb_bumped": ["ki-2026-05-21-gateway-microservices-timeout", "ki-2026-05-24-runtime-core-rtc-p95-recurring"],
        "poll_window_minutes": 65,
        "notes": "8 alerts polled across 4 channels (3 alert-system, 4 alert-frontend-errors, 1 alert-runtime-monitoring, 0 swat). 0 deduped (all hashes novel). 4 new groups: G1 alert-system B03GBAMHUTB 17:05:54+57Z 2 alerts ki-21 cascade SUPPRESS (Centreon paired-fire 3s gap, ki-29 ruled out 0 NRE hits, precedent today 14:13Z+14:55-15:00Z); G2 alert-system B05PN7JG87L 17:08:31Z singleton ki-24 **DM-OCCURRENCE-RESURFACE** (occ 99->100, 10x threshold reached; monitor 115456700 last_triggered 17:01:20Z; Screen Load peak 7.275s @ 17:00:30Z + Action Execution co-spike 3.621s @ 17:04:30Z = shared-upstream signature; 481s forwarder lag); G3 alert-frontend B011R3D650X 17:19:13-17:41:13Z 4 alerts ki-21 SUPPRESS (monitor 77419271 last_triggered 17:41:12Z direct alignment within 1s; DD logs confirm syncutil/syncwidget XHR timeouts across 5+ accounts: fleeteforce, mobilitycityofcoloradosprings, primroseventuresllc, silverbackcommunicationsllcCo1, crslaboratories); G4 alert-runtime B063S8NBW0M 17:59:43Z singleton novel hash (needs-human score 2 actionable low-impact; Screen Load p95 mini-breach 3.565s @ 17:51:00Z 523s before alert = unusual 9-min lag; 2nd B063S8NBW0M today vs 14:05:31Z precedent 4eff228c4786b810). KB bumps: ki-21 occ 297->303 (last_seen 17:41:13Z, last_notified unchanged 12:07:35Z); ki-24 occ 99->100 (last_seen 17:08:31Z, last_notified UPDATED 18:18:17Z via 10x resurface gate). **1 DM sent this cycle (ki-24 occurrence-resurface)**. 5th cross-channel ki-21+ki-24 co-firing today (G1 17:05:54Z + G2 17:08:31Z, 157s apart) further hardens shared-upstream hypothesis. ki-24 trajectory today: 10 clusters by 17:08Z, occ 100. ki-21 trajectory: 8 clusters today, projected EOD ~11 vs 16.5/day baseline (slightly below). Tools: gh-ok / dd-monitors-ok / dd-metric-ok / dd-logs-ok / es-search-ok / es-aggregate-ok / git-deploys-blocked (gh-api 403 chronic cycle 31) / slack-ok. SQL+Mongo skipped (no infra-shaped event). account_impact.py skipped (all groups block-only body, no @account_name). KIBANA_BASE_URL substituted correctly. Standing asks: #1 gh-api 403 cycle 31; #6 ki-29 monitor 236570583 too-broad clause; #7 dd_search.py APM trace search blocker for ki-24 root cause attribution + chronic B063S8NBW0M attribution gap; #10 ki-24 fix_status flip (occ=100 reached; soft-recommend escalation deadline reached, DM sent surfaces this to Ben)."
    },
    "duration_s": 0,
    "runtime_cost_usd": 0
}
lines.append(cycle_summary)

with open('kb/incident-log.jsonl', 'a', encoding='utf-8') as f:
    for line in lines:
        f.write(json.dumps(line, ensure_ascii=False) + '\n')

print(f"Appended {len(lines)} lines")
