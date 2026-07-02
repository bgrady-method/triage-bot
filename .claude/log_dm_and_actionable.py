import json
import os

NOW = "2026-06-08T18:18:53Z"

# 1) Log the DM to docs/messages/2026-06-08/self-dm.jsonl
dm_body = """📒 *known issue recurrence* — `ki-2026-05-24-runtime-core-rtc-p95-recurring`
**Occurrence #100 — 10x resurface threshold reached** (gate: known-issue-occurrence-resurface; bypasses 24h suppression window)

Cluster #10 today (10 ki-24 clusters between 12:31Z and 17:08Z). Daily trajectory 100 occ / 17 UTC hrs ≈ 5.9/hr vs 3.5/day historical baseline — well above pace.

**This cycle's signature:** Screen Load p95 peak **7.275s @ 17:00:30Z** (ratio 1.425 over 3s threshold) + co-spike Action Execution **3.621s @ 17:04:30Z** = canonical shared-upstream signature. Latency-only (0 ES runtime-core errors). Monitor 115456700 last_triggered 17:01:20Z. Forwarder fired 17:08:31Z (481s lag).

**5th cross-channel ki-21+ki-24 co-firing today** (G1 alert-system 17:05:54Z B03GBAMHUTB ki-21 cascade + G2 17:08:31Z ki-24, 157s apart). Pattern hardening: ki-21+ki-24 likely share upstream root cause (3 prior co-firings + this one + 4th yesterday 13:56Z, 14:11-14:13Z, 14:54-15:04Z).

**Playbook:**
1. Confirm pattern: `dd_search.py metric --query 'p95:trace.aspnet_core.request{env:prod,service:runtime-core-api,resource_name:post_/api/v1/runtime/load/_screenid*}'` over the spike window — multi-point >3s confirms.
2. Confirm latency-only: `dd_search.py logs --query 'service:runtime-core-api status:error env:prod'` should return 0.
3. **Diagnostic gap:** open https://app.datadoghq.com/apm/traces?query=service%3Aruntime-core-api%20%40duration%3A%3E5s in the 16:55-17:15Z window — look for SQL/Mongo/Redis SCAN dominating the slow span.
4. Mitigation options: (a) raise monitor threshold to 4s (masks), (b) circuit breaker per resource_name (medium), (c) profile slowest accounts + targeted index fixes (root cause).
5. Cross-check `ki-2026-05-21-gateway-microservices-timeout` (G1/G3 today) — co-firing pattern strongly suggests shared upstream.

**fix_status:** investigating · **fix_jira:** (not set — soft-recommend flip to `needs-ops-decision`; #10 standing ask deadline reached)

Source alerts (1 total):
  • https://methodintegration.slack.com/archives/CPHHABKAA/p1780938511526869  (alert-system, 17:08 UTC)

Evidence:
  • DD monitor 115456700: https://app.datadoghq.com/monitors/115456700 — "RTC Screen Load has a high p95 latency" (last_triggered 17:01:20Z)
  • DD metric Screen Load p95: https://app.datadoghq.com/metric/explorer?live=false&page=0&exp_metric=trace.aspnet_core.request&exp_scope=env%3Aprod%2Cservice%3Aruntime-core-api%2Cresource_name%3Apost_%2Fapi%2Fv1%2Fruntime%2Fload%2F_screenid%2A&exp_agg=p95&start=1780937700&end=1780938900
  • DD APM traces (diagnostic gap): https://app.datadoghq.com/apm/traces?query=service%3Aruntime-core-api%20%40duration%3A%3E5s&from_ts=1780937700000&to_ts=1780938900000
  • Kibana (runtime-core errors check, 0 hits): https://ca8e80d7f930400fb386a29477353efa.kb.us-west-1.aws.found.io:9243/app/discover#/?_g=(time:(from:'2026-06-08T16:55:00Z',to:'2026-06-08T17:15:00Z'))&_a=(query:(language:kuery,query:'service:runtime-core-api%20AND%20Level:Error'))
  • Investigation report: `docs/investigations/2026-06-08-63d17ee78a22837d.md`"""

dm_entry = {
    "ts": NOW,
    "channel_id": "D0647LD5FND",
    "channel_name": "self-dm",
    "recipient": "self-dm",
    "message_type": "known-issue",
    "alert_hash": "63d17ee78a22837d",
    "thread_ts": None,
    "body": dm_body
}
with open("docs/messages/2026-06-08/self-dm.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(dm_entry, ensure_ascii=False) + "\n")
print("DM logged to docs/messages/2026-06-08/self-dm.jsonl")

# 2) Append entries to docs/actionable/2026-06-08.md
actionable_path = "docs/actionable/2026-06-08.md"
if not os.path.exists(actionable_path):
    raise SystemExit(f"actionable file missing: {actionable_path}")

# G1: known-issue-recurrence (high-borderline category) suppressed by known-issue-window
g1_entry = """## `4f0022af0c857ac8` · 17:05Z · #alert-system · category=known-issue-recurrence
**Score:** -1 (DM gate: 4)
**Classification:** known-issue-recurrence · **bug-type guess:** env
**Hypothesis:** B03GBAMHUTB Centreon paired-fire 17:05:54+57Z (3s gap) — ki-21 cascade-downstream; ki-29 ruled out (0 NRE hits ES 17:00-17:10Z); 5th cross-channel ki-21+ki-24 co-firing today (G2 ki-24 157s later).
**Investigation:** [docs/investigations/2026-06-08-4f0022af0c857ac8.md](docs/investigations/2026-06-08-4f0022af0c857ac8.md)
**Score breakdown:**
- -3 matched_kb_inhibition (ki-2026-05-21-gateway-microservices-timeout)
- +1 group_size_2 (2 alerts)
- +3 critical_path_service (ms-gateway-api via cascade)
- 0 metric_breach (n/a Centreon)
- 0 monitor_history (no DD monitor_id)
- 0 active_users_affected (block-only body)
- 0 cross_channel (within-group single channel; cross-group co-firing noted)
- 0 novel_no_kb_no_prior_hash_7d (B03GBAMHUTB-Centreon-ki-21-cascade precedent today)
- 0 deploy_correlation_2h (gh-api 403 chronic)
- 0 recency_decay (no monitor_id)
- 0 operator_engagement
- -2 recent_dm_matched_kb_24h (ki-21 last DM ~6h ago)
- 0 account_tier
**Matched KB:** ki-2026-05-21-gateway-microservices-timeout (suppression window)
**Suggested action:** None this cycle. ki-21 chronic-residual-post-rollback-2026-06-05; Centreon paired-fire signal is stable.

---
"""

# G3: known-issue-recurrence (high-borderline) suppressed by known-issue-window
g3_entry = """## `897f997dbbcd80be` · 17:19Z · #alert-frontend-errors · category=known-issue-recurrence
**Score:** -1 (DM gate: 4)
**Classification:** known-issue-recurrence · **bug-type guess:** env
**Hypothesis:** ki-21 chronic syncutil/syncwidget XHR errors; 4-alert cluster 17:19:13-17:41:13Z B011R3D650X; monitor 77419271 last_triggered 17:41:12Z direct alignment within 1s; DD logs confirm timeouts across 5+ accounts (fleeteforce, mobilitycityofcoloradosprings, primroseventuresllc, silverbackcommunicationsllcCo1, crslaboratories).
**Investigation:** [docs/investigations/2026-06-08-897f997dbbcd80be.md](docs/investigations/2026-06-08-897f997dbbcd80be.md)
**Score breakdown:**
- -3 matched_kb_inhibition (ki-2026-05-21-gateway-microservices-timeout)
- +2 group_size_3_4 (4 alerts)
- +3 critical_path_service (ms-gateway-api via DD logs URL pattern)
- 0 metric_breach (log-volume monitor)
- 0 monitor_history (77419271 chronic dm_rate 0.4-0.8)
- 0 active_users_affected (extrapolation: cluster_lower_bound infrastructure pattern)
- 0 cross_channel (within-group single channel)
- 0 novel_no_kb_no_prior_hash_7d (ki-21 evidence-based)
- 0 deploy_correlation_2h (gh-api 403 chronic)
- -2 recency_decay (3rd ki-21 cluster today; floor)
- 0 operator_engagement
- -2 recent_dm_matched_kb_24h (ki-21 last DM ~6h ago)
- 0 account_tier
**Matched KB:** ki-2026-05-21-gateway-microservices-timeout (suppression window)
**Suggested action:** None this cycle. ki-21 chronic; densest ki-21 cluster of the day so far. Continue suppression until 12:07Z+24h = tomorrow 12:07Z OR 10x resurface (occ 300 already passed; next is 310).

---
"""

# G4: needs-human (low-impact category) score 2
g4_entry = """## `3d54e58d7078448b` · 17:59Z · #alert-runtime-monitoring · category=high-borderline
**Score:** 2 (DM gate: 4)
**Classification:** needs-human · **bug-type guess:** unknown
**Hypothesis:** B063S8NBW0M singleton 17:59:43Z alert-runtime-monitoring (empty Slack body). DD metric Screen Load p95 mini-breach 3.565s @ 17:51:00Z (523s before alert; unusual 9-min lag rules out monitor 115456700 forwarder). Likely DD APM Watchdog story for runtime-core-api per 14:05:31Z precedent 4eff228c4786b810. Tail of broader ki-24 chronic flap possible (10th ki-24 cluster today) but unconfirmed without APM trace search.
**Investigation:** [docs/investigations/2026-06-08-3d54e58d7078448b.md](docs/investigations/2026-06-08-3d54e58d7078448b.md)
**Score breakdown:**
- +2 novel_no_kb_no_prior_hash_7d (hash 3d54e58d7078448b first seen; no KB match)
- 0 group_size_1 (singleton)
- 0 critical_path_service (runtime-core inferred; no monitor alignment ±60s; conservative per 4eff228c4786b810 precedent)
- 0 metric_breach (Screen Load 3.565s ratio 0.188 <0.5 bracket)
- 0 monitor_history (unknown monitor_id; block-only body)
- 0 active_users_affected (block-only body)
- 0 cross_channel (singleton; G3 ki-21 18min earlier different channel — not within-group)
- 0 deploy_correlation_2h (gh-api 403 chronic)
- 0 recency_decay (no monitor_id; 2nd B063S8NBW0M today is bot-level not monitor-level)
- 0 operator_engagement
- 0 recent_dm_matched_kb_24h (no KB match)
- 0 account_tier
**Matched KB:** none
**Suggested action:** Add to recurring pattern: 2nd B063S8NBW0M today (1st was 14:05:31Z `4eff228c4786b810` score 2 also). If a 3rd appears today, recency_decay convention may need revisit and a KB entry "ki-2026-06-08-B063S8NBW0M-watchdog-runtime-core" should be drafted. Root cause still blocked by standing ask #7 (dd_search.py APM trace search).

---
"""

with open(actionable_path, "a", encoding="utf-8") as f:
    f.write(g1_entry)
    f.write(g3_entry)
    f.write(g4_entry)
print("Appended 3 entries to docs/actionable/2026-06-08.md")
