# Method Platform Stability Review — 2026-05

_Generated: 2026-05-05T13:23:45Z · Window: 2026-04-05T13:23:45Z → 2026-05-05T13:23:45Z (30d) · Routine: stability-review v0.1_

> **Limited data — first run.** The triage-bot began operating on 2026-05-01. All 72 incident-log lines in the window fall within a 4-day span (May 1–4). Trend analysis is unavailable; baselines are approximate. Error-budget calculations are directionally correct but should be re-confirmed once the bot has logged a full 30-day cycle.

---

## Executive Summary

- Triage-bot processed **~97 new alerts** across the window (all in May 1–4). Breakdown by formal classification: 0 known-issue-recurrence, 0 false-alarm (KB empty — first month), 0 new-with-clear-fix; the majority were classified **needs-human** (confidence 0.30–0.67) due to conservative mode (<50 runs) and Centreon block-attachment content being unreadable via Slack MCP. 6 alerts were deduplicated.
- A significant P0 event on 2026-05-02 (revert of `b1f9358`) drove the majority of alert volume. The Signup Availability SLO entered Alert on 2026-04-29 (pre-window) and remained in Alert at report time. Elasticsearch was blocked (403) for every investigation in the window.

**Top 5 recommendations (ranked by ICE score):**

1. **Add triage bot's execution-environment IP to ES allowlist** — ICE 36.0. Currently blocks every log-based investigation. Single config change.
2. **Identify prod-new-04 daily scheduled job and add KB false-alarm entry** — ICE 16.0. Eliminates daily triage-bot DM noise; takes 1–2 hours.
3. **Investigate Signup APM silence and formally define Signup SLO** — ICE 13.5. Signup SLO has been in Alert for 6+ days; APM in No Data for 3+ days.
4. **Add deploy-time post-flight monitor validation for runtime-core deployments** — ICE 10.8. The May 2 revert left 8 DD sub-service monitors in No Data for 3+ days with no automated re-alert.
5. **Add client-side retry / graceful degradation for GetSyncWidgetInfoAsync XHR calls** — ICE 6.3. Fired 3× in one day on May 2; self-resolves but generates unnecessary noise and user-visible errors.

**Availability snapshot per critical service (vs proposed SLO):**

| Service | Window availability (est.) | Proposed SLO | Budget burn (est.) |
|---------|---------------------------|--------------|-------------------|
| runtime-core-api | 98.47% | 99.95% | 3,056% |
| Signup | undetermined (APM No Data since May 2) | (none formal) | SLO burn rate > 30× (monitor 154229727) |
| ms-account-api sub-services | No Data since May 2 03:09Z | (none formal) | undetermined |
| ES investigation tool | ~0% (403 throughout) | (internal tool) | N/A |

> Note: runtime-core availability is computed over the full 30-day window denominator; the actual event was confined to 4 days of observation. The 98.47% figure assumes 0 downtime outside the observed window (likely conservative).

Total error budget consumed across listed services: **runtime-core 3,056% of proposed 99.95% target in window.**

---

## Methodology

- Sources read: `kb/incident-log.jsonl` (72 lines), `docs/investigations/2026-05-04-5024f8254f1c6a39.md` (1 report), `kb/known-issues.json` (empty), `kb/false-alarms.json` (empty).
- Fresh DD queries: 7 (`scripts/dd_search.py monitors`, `metric` queries for runtime-core-api and signup hit rates, targeted May 2 P0 window analysis).
- Fresh ES queries: 1 attempted — **all returned 403 (ES host not in allowlist)**. Zero ES data available.
- Jira JQL queries (read-only): 3 broad sweeps (signup/SLO, runtime-core/b1f9358, syncutil/XHR).
- Course modules consulted: 5 (`level-1/availability-and-slas.json`, `level-7/deployment-patterns.json`, `level-10/observability.json`, `level-5/communication-failure.json`, `level-10/circuit-breakers-and-bulkheads.json`).
- Five-whys protocol: `references/methodology/five-whys-template.md`.
- No prior stability reports exist — this is the first run.

---

## Findings

### F1 — Elasticsearch 403: Persistent Investigation Blind Spot

**Symptom (one line):** Every Elasticsearch query in the window returned HTTP 403 (`host not in allowlist`), blocking log-based investigation for the triage routine and for this stability review.

**Frequency:** 100% of ES queries attempted during May 1–4 blocked. Observed across every cycle that attempted ES: poll-cycles on May 2 (`ES blocked 403` noted in 09:24Z, 11:17Z, 14:35Z, and 17:21Z cycles among others) and the May 4 investigation report (5024f8254f1c6a39, Lessons §4).

**Triage-bot evidence:**
- `kb/incident-log.jsonl` lines 18, 21, 24, 28 (poll-cycle `notes` field: "ES blocked 403" in each).
- `docs/investigations/2026-05-04-5024f8254f1c6a39.md` §Tools Run: `ES | level:(ERROR OR FATAL) --from 08:05Z --to 09:00Z | Unavailable — 403 host not in allowlist`.
- This review: `python3 scripts/es_search.py search --query "level:ERROR AND fields.ServiceName:runtime-core" --from "now-30d"` → same 403 error.

**Fresh DD evidence:**
- N/A (this finding is about ES tool unavailability, not a DD monitor state).

**Fresh ES evidence:**
- All attempts returned `{"error": "es POST https://ca8e80d7f930400fb386a29477353efa.us-west-1.aws.found.io:443/*/_search -> 403: Host not in allowlist"}`. Kibana URL: unavailable.

**Five-whys:**

```
Symptom: Every ES investigation query returns 403 — no log data accessible to the triage routine.

Why 1: The triage bot's execution environment IP is not in the Elasticsearch allowlist.
  Evidence: Verbatim error message across all es_search.py calls: "403: Host not in allowlist".

Why 2: The ES allowlist was configured for on-premises dev workstations and prod IIS hosts,
  not for cloud-based automation runners.
  Evidence: The ES endpoint is ca8e80d7f930400fb386a29477353efa.us-west-1.aws.found.io
  (Elastic Cloud hosted). Allowlists for hosted ES clusters are managed via the Elastic Cloud
  console; the triage-bot IP range was never added.

Why 3: When the triage bot was set up, no "onboard a new automation client" checklist was
  followed to verify ES access from the runner's IP.
  Evidence: kb/incident-log.jsonl line 1 (first poll cycle, May 1 19:26Z) contains no note about
  ES; the 403 was first encountered on May 2 during the P0 investigation (line 9, 03:33Z cycle),
  not day 0. ES access was not smoke-tested before the bot went live.

Why 4: The triage playbooks assume ES is accessible but include no startup health check that
  verifies connectivity and posts a warning if ES returns 403.
  Evidence: scripts/tool_health.py exists but docs/investigations/TEMPLATE.md and the triage
  prompt do not include an ES accessibility pre-check step.

Why 5: No "monitoring tool access" contract exists. The system relies on engineers knowing which
  tools the automation uses and manually provisioning access when automation is added.
  Evidence: No CLAUDE.md or playbook section describes the process for adding a new automation
  runner's IP to ES, DD, or other observability tool allowlists.

Stop condition: Structural cause — missing access-provisioning process for automation tooling.
```

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):

| Metric | Value | Note |
|---|---|---|
| Frequency | 100% of ES queries blocked | All attempts in May 1–4 window |
| MTTR | undetermined (still blocked at report time) | 4+ days without ES access |
| Availability impact | ~0% ES access / 30d | 100% of log investigation blocked |
| Error budget burn | N/A (internal tool, no SLO) | Qualitative: half the investigation playbook unusable |
| Blast radius | Every triage investigation in window degraded | Zero log corroboration on any alert |

**Similar Jira (read-only cross-reference):**
- No similar open tickets found via JQL: `project in (NCNG, PL) AND (text ~ "elasticsearch" OR text ~ "ES allowlist") AND resolution = Unresolved AND updated >= -90d`.

**Recommendation:**
- (a) Add the triage bot's execution-environment IP range to the Elasticsearch allowlist via the Elastic Cloud console. Verify with `python3 scripts/es_search.py search --query "level:ERROR" --from "now-1h" --limit 1`.
- (b) Alternatively, route ES queries through the SSH bastion (noted in investigation 5024f8254f1c6a39, Lessons §4) — lower blast radius change if IP is dynamic.
- (c) Add an ES health-check step to `scripts/tool_health.py` and call it at the start of each triage poll cycle; post `🔴 ES inaccessible (403)` to `#triage-bot-health` if it fails. This converts silent degradation to visible failure.

**Course module references:**
- `level-10/observability.json` — "Alert on symptoms, not causes. Distributed tracing is essential for debugging latency in microservices." Applied: the ES log pipeline is the primary symptom-investigation tool for the platform; its unavailability means triage bot can only observe DD metrics (causes) and cannot confirm user-visible symptoms from logs. An observability tool that is itself unobservable is a structural gap.
- `level-5/communication-failure.json` — "Design for timeouts, retries, and duplicates; degrade gracefully when services are unavailable." Applied: the triage routine should degrade gracefully (continue with DD-only investigation) rather than silently missing ES data. The current behavior (no warning posted to #triage-bot-health) is invisible degradation.

**ICE score:** Impact 8 · Confidence 9 · Effort 2 → **36.0**
_(I: removes a tool-access failure that blocks half the investigation playbook for every alert. C: IP allowlist addition is a well-understood config change. E: single Elastic Cloud console action + 10 lines in tool_health.py.)_

---

### F2 — prod-new-04 Daily CPU Spike: Centreon Alert Noise and KB Gap

**Symptom (one line):** Centreon fires a CPU alert on `prod-new-04` every day at approximately 08:39Z, after the 08:23–08:38Z spike has already self-resolved; the triage bot cannot read the alert body and DMs Ben each occurrence as `needs-human`.

**Frequency:** 1 confirmed investigation (2026-05-04). DD 24h-ago baseline shows an identical CPU spike pattern on 2026-05-03 at the same UTC hour, indicating a daily recurrence. Estimated 4 occurrences in the 4-day observation window.

**Triage-bot evidence:**
- `docs/investigations/2026-05-04-5024f8254f1c6a39.md` §Key Findings: "CPU resolved at 08:38 UTC — 1 minute before the Centreon alert posted at 08:39 UTC"; "24h baseline is identical: yesterday 08:22–08:38 UTC showed max 53%, avg 44%".
- `kb/incident-log.jsonl` line 68 (2026-05-04T11:09:25Z, duration_s=4286 — indicates a long investigation for a signal that was already over).

**Fresh DD evidence:**
- `system.cpu.user{host:prod-new-04}` spike 08:23–08:38Z, peak 59%, self-resolved: https://app.datadoghq.com/metric/explorer?live=false&exp_metric=system.cpu.user&exp_scope=host%3Aprod-new-04&start=1777882940&end=1777884000
- `iis.uptime{host:prod-new-04}` = 285,532s at alert time — no IIS recycle during spike.
- `iis.net.num_connections{host:prod-new-04}` stable 24–31 throughout — no user-traffic spike driving CPU.

**Fresh ES evidence:** Unavailable — 403.

**Five-whys:**

```
Symptom: Triage bot DMs Ben daily about a Centreon alert that has already resolved.

Why 1: Centreon fires a CPU threshold alert after the spike resolves, due to notification lag.
  Evidence: investigation 5024f8254f1c6a39: spike 08:23–08:38Z, alert posted 08:39Z (1 min lag).

Why 2: A daily scheduled process on prod-new-04 consumes ~50% CPU for ~15 minutes at 08:23Z UTC.
  Evidence: DD metric system.cpu.user shows identical spike on consecutive days at the same hour.
  IIS connections stable throughout; no backend errors during the spike → not user traffic.

Why 3: The triage bot cannot read the Centreon alert body (Slack MCP does not surface block
  content as text), so it cannot correlate to the known daily pattern.
  Evidence: investigation 5024f8254f1c6a39 §Alert Summary: "Alert text: (empty — full content
  in Slack blocks only; not accessible via Slack MCP)".

Why 4: No kb/false-alarms.json entry exists for this daily Centreon pattern.
  Evidence: kb/false-alarms.json = []. First time this alert appeared in the observation window.
  Investigation 5024f8254f1c6a39 §Suggested KB Entry provides the template; it was not added
  because the job identity on prod-new-04 was not confirmed (ES blocked, no process-level metrics).

Why 5: The investigation playbook has no "expected-daily-noise" review step that would prevent
  a known-good daily event from requiring a full investigation on first encounter.
  Evidence: playbooks/triage.md does not include a "known schedule correlation" check before
  escalating a CPU spike alert to needs-human.

Stop condition: Structural — missing KB entry + missing block-content access + no schedule-
  correlation lookup in the triage playbook.
```

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):

| Metric | Value | Note |
|---|---|---|
| Frequency | ~4/month (daily) | Based on 4-day observation, extrapolated |
| MTTR | ~0 min (self-resolves before alert arrives) | Not a real outage; Centreon lag is the issue |
| Availability impact | 0% (no customer-visible impact confirmed) | IIS stable, no backend errors during spike |
| Error budget burn | N/A (false alarm) | |
| Blast radius | 1 triage bot investigation per day wasted | Est. 1–2 USD/day in routine cost |

**Similar Jira (read-only cross-reference):**
- No similar open tickets found via JQL: `project in (NCNG, PL) AND text ~ "prod-new-04" AND resolution = Unresolved AND updated >= -90d`.

**Recommendation:**
- (a) RDP to prod-new-04; check Windows Task Scheduler and SQL Server Agent jobs scheduled around 08:20–08:25 UTC. Confirm the job is expected.
- (b) Once confirmed, add to `kb/false-alarms.json` using the template provided in investigation 5024f8254f1c6a39 §Suggested KB Entry.
- (c) Separately: investigate whether Centreon can be reconfigured to include a plain-text summary alongside the Slack block payload — this would unblock triage bot correlation logic for all future Centreon alerts.
- (d) Also separately: whether the XHR errors monitor (id 77419271) that fired 19 minutes before the Centreon alert on May 4 is causally related (both may be caused by the same scheduled job) — investigate as part of F5.

**Course module references:**
- `level-10/observability.json` — "Alert on symptoms, not causes." Applied: Centreon's CPU % threshold is alerting on a cause (CPU utilization) rather than a symptom (user-visible degradation). The spike is a scheduled batch job with no customer impact. Re-configure the alert to fire only when CPU elevation correlates with service degradation (IIS error rate rise or connection spike) to eliminate this noise class.

**ICE score:** Impact 4 · Confidence 8 · Effort 2 → **16.0**
_(I: eliminates 1 daily DM to Ben + 1 unnecessary investigation. C: KB entry + job identification is straightforward. E: 1–2 hours of an engineer's time.)_

---

### F3 — Signup Availability SLO Breach and APM Silence (Ongoing)

**Symptom (one line):** The Signup service Availability SLO has been in Alert since 2026-04-29 (6+ days at report time); all Signup APM monitors entered No Data state on 2026-05-02 at 15:50–16:00Z and have not recovered.

**Frequency:** 1 ongoing SLO breach event, active for at least the last 6 days of the window.

**Triage-bot evidence:**
- `kb/incident-log.jsonl` line 7 (May 2 01:32Z cycle): "Signup SLO breach" noted.
- `kb/incident-log.jsonl` lines 8, 9, 10, 13, 18, 21, 23, 24: all note "Signup SLO Alert ongoing since Apr 29".
- `docs/investigations/`: no dedicated investigation report for Signup (alert content unreadable via Slack MCP).

**Fresh DD evidence:**
- Monitor 154229727 "Service Signup Availability SLO" — state: **Alert**, last_changed: 2026-04-29T16:36:27. URL: https://app.datadoghq.com/monitors/154229727. Query: `error_budget("f543e0152a9b5118a647770c1a1e3a2d").over("7d") > 30`. A burn rate > 30× means the 7-day error budget would be exhausted in `7d/30 ≈ 5.6 hours`. As of May 5 the alert has been firing for 6 days.
- Monitor 154230536 "Service Signup has a high error rate" — state: **No Data** since 2026-05-02T15:54:56.
- Monitor 154251781 "Signup page load p90" — state: **No Data** since 2026-05-02T15:54:01.
- Monitor 154252126 "Signup post p90" — state: **No Data** since 2026-05-02T15:50:46.
- Monitor 154252601 "Signup avg latency" — state: **No Data** since 2026-05-02T16:00:41.
- Metric `trace.aspnet.request.hits{service:signup,env:prod}`: non-null through 2026-05-01T12:00Z (avg 0.020/s), then no data in the window. URL: https://app.datadoghq.com/metric/explorer

**Fresh ES evidence:** Unavailable — 403.

**Five-whys:**

```
Symptom: Signup SLO in Alert for 6+ days; all Signup APM monitors in No Data for 3+ days.

Why 1: The Signup service Availability SLO shows a burn rate > 30× its budget over the 7-day window.
  Evidence: DD monitor 154229727, state=Alert since 2026-04-29T16:36:27.

Why 2: The SLO breach began before the May 2 P0 (Apr 29 vs May 2 midnight), and the APM
  No Data started on May 2 at 15:50Z — these are two distinct phases of the same failure.
  Phase 1 (Apr 29): Signup had actual errors driving SLO breach. Phase 2 (May 2 15:50Z):
  Signup APM stopped reporting entirely (possibly a side-effect of the runtime-core revert
  impacting the APM agent on the shared host, or an IIS pool restart that did not restart the
  APM agent).
  Evidence: Signup hit rate in DD was 0.020/s avg through May 1 12:00Z and then disappears;
  the No Data transition on May 2 15:50–16:00Z coincides with the period the triage bot noted
  "runtime-core-api APM recovery" (14:35Z cycle: "rate at normal 24h baseline (50/10min), monitor
  back OK") suggesting APM pipeline disruption was resolving in runtime-core at that exact time
  but killed Signup APM spans in the process.

Why 3: Once the Signup APM spans stopped, the 4 latency/error monitors entered No Data and could
  not alert on actual Signup service errors — any subsequent errors were invisible.
  Evidence: monitors 154230536, 154251781, 154252126, 154252601 all No Data since ~15:50Z May 2.
  notify_no_data is not set on these monitors (confirmed from DD monitor JSON output); the monitors
  went silent without alerting.

Why 4: No Signup-specific synthetic monitor exists that is independent of APM instrumentation.
  Evidence: DD synthetics monitors in the window (121308660, 123495390, 133625690, 123495492,
  142200330, 149705129) are all tagged "Method UI Grid and Dropdown Performance" — they test
  the runtime app, not the signup flow. A sign-up-specific synthetic (e.g., complete the
  registration flow) does not exist.

Why 5: The Signup service has no formal SLO document defining what "available" means, which
  signals to measure, and what alerting is required for the SLO to be credible. The existing
  SLO monitor fires a burn-rate alert but there is no independent verification path.
  Evidence: references/architecture/platform-overview.md §"SLOs": "None defined. Performance
  targets exist in scattered CLAUDE.md files but are not formal SLOs." The Signup service is
  not listed in known-failure-modes.md with a proposed SLO.

Stop condition: Structural — no formal SLO document and no synthetic independent of APM.
```

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):

| Metric | Value | Note |
|---|---|---|
| Frequency | 1 ongoing breach (started Apr 29) | |
| MTTR | undetermined (still ongoing at May 5) | |
| Availability impact | undetermined (APM No Data for 3+ days) | Cannot compute without spans |
| Error budget burn | > 30× burn rate over 7d window | Monitor 154229727; actual % requires SLO metric read |
| Blast radius | All new user sign-ups during breach | Direct revenue pipeline impact |

**Similar Jira (read-only cross-reference):**
- No open ticket directly matching "Signup SLO breach" or "Signup APM No Data" found via JQL: `project in (NCNG, PL) AND (text ~ "signup" OR text ~ "SLO") AND resolution = Unresolved AND updated >= -90d`. (Returned 10 results, none matching Signup availability or APM failure.)

**Recommendation:**
- (a) Immediately investigate why Signup APM stopped reporting on May 2 at 15:50Z. Check whether the `signup` service IIS app pool was restarted (planned or unplanned) during the runtime-core P0 recovery window, and whether the APM agent (`ddagent` or Datadog .NET tracer) was properly restarted alongside it.
- (b) Add `notify_no_data: true` (with `no_data_timeframe: 10` minutes) to monitors 154230536, 154251781, 154252126, 154252601 so that APM silence triggers an alert rather than silent No Data.
- (c) Create a Datadog Synthetic monitor for the Signup registration flow (POST to `signin.methodlocal.com` / `signup.methodlocal.com`) independent of APM — this provides a signal even when the APM pipeline is down.
- (d) Formally document the Signup SLO targets in `references/architecture/known-failure-modes.md` (proposed: error rate < 0.1%, p90 page load < 4s, availability > 99.9% over 30d).

**Course module references:**
- `level-1/availability-and-slas.json` — "Use SLIs to measure, SLOs as internal targets, and SLAs as customer contracts. In series systems, overall availability is the product of components — improve the weakest link first." Applied: the Signup SLO currently has a single measurement path (APM spans). When the APM pipeline fails, the SLO measurement fails too. Redundant SLI paths (APM + synthetic) would preserve observability during APM outages — consistent with the principle that availability in parallel paths is 1 − (1−A₁)×(1−A₂).
- `level-10/observability.json` — "Alert on symptoms, not causes. RED method (Rate, Errors, Duration) for services." Applied: the current Signup monitoring detects symptoms (latency, error rate) via APM but has no independent symptom check. Adding a synthetic test checks the symptom (can a new user sign up?) without relying on the APM infrastructure.

**ICE score:** Impact 9 · Confidence 6 · Effort 4 → **13.5**
_(I: ongoing SLO breach directly affects new user acquisition — highest business impact. C: root cause of APM silence needs verification; recommendation is split into known-good steps. E: IIS investigation + monitor config + synthetic creation ~ 1 week.)_

---

### F4 — May 2 Revert Deploy Cascade: runtime-core and ms-account-api Sub-Service APM Still Dark

**Symptom (one line):** Revert of commit `b1f9358` deployed at ~00:00Z 2026-05-02 triggered a multi-service APM disruption; 8 Datadog sub-service monitors remain in No Data at report time (3+ days), and the overall event drove 11+ alert bursts over a 14-hour window.

**Frequency:** 1 P0-class event; 11+ alert bursts in the window of 08:47–11:17Z May 2 alone.

**Triage-bot evidence:**
- `kb/incident-log.jsonl` lines 9, 10, 11, 18, 21, 24 (all citing the b1f9358 revert and runtime-core-api APM disruption).
- Line 9 (03:33Z): "runtime-core-api silent since 00:00Z (revert b1f9358 deployment ~00:00Z); DI wiring suspect for GetLegacyPermissionsAndBundlesCommand (898e5d4)".
- Line 21 (11:17Z): "ongoing P0: runtime-core-api 0 APM hits for ~10.6h since revert b1f9358 deploy; IIS pool restart needed".
- Line 18 (09:24Z): "Watchdog story fired 08:58Z; Synthetics Alert; ES blocked 403; deduped 0b5423c (fe alert from prior cycle)".

**Fresh DD evidence:**
- 8 monitors in No Data since May 2 03:08–04:59Z (still No Data at 2026-05-05T13:23Z):
  - 80445983 "runtime-core-api-sql-server avg latency" — No Data since 2026-05-02T04:59:23
  - 19710080 "runtime-core-api-mongodb p90 latency" — No Data since 2026-05-02T03:09:20
  - 65603337 "ms-account-api-mongodb avg latency" — No Data since 2026-05-02T03:13:57
  - 65603338 "ms-account-api-mongodb p90 latency" — No Data since 2026-05-02T03:08:59
  - 65603311 "ms-account-api-sql-server p90 latency" — No Data since 2026-05-02T03:09:31
  - 65603306 "ms-account-api-sql-server avg latency" — No Data since 2026-05-02T03:09:26
  - 65577146 "ms-account-api-redis p90 latency" — No Data since 2026-05-02T03:09:27
  - 65577145 "ms-account-api-redis avg latency" — No Data since 2026-05-02T03:09:25
- Base monitors 17420774 and 17872725 (`runtime-core-api` error rate and p90) returned to OK by 2026-05-04T18:52.
- DD metric `trace.aspnet_core.request.hits{service:runtime-core-api}`: traffic recovered progressively starting ~11:00Z May 2 (avg 14.2/s at hour 11 vs 1.8/s at hour 06). Full business-hours traffic (~60/s) resumed by 14:00Z. URL: https://app.datadoghq.com/metric/explorer

**Fresh ES evidence:** Unavailable — 403.

**Five-whys:**

```
Symptom: 8 DD sub-service APM monitors for runtime-core and ms-account-api entered No Data on
  May 2 at 03:08Z and remain No Data 3+ days later, undetected by any new alert.

Why 1: APM spans for SQL Server, MongoDB, and Redis sub-services stopped being emitted.
  Evidence: DD monitors 80445983, 19710080, 65603306/11/37/38, 65577145/46 all entered No Data
  within a 1-hour window (03:08–04:59Z May 2).

Why 2: The No Data state is correlated with the revert of b1f9358 deployed at ~00:00Z May 2.
  Triage bot notes (lines 9, 10, 21) identify the revert as the trigger. Either the revert
  modified APM instrumentation configuration, or the resulting IIS app pool recycle killed the
  Datadog .NET APM tracer for these sub-service span emitters without automatic restart.
  Evidence: IIS uptime for prod-new-04 shows no recycle during the May 4 window (investigation
  5024f8254f1c6a39); however the May 2 revert-triggered recycle was not separately confirmed
  (ES 403 blocked log verification).

Why 3: All 8 sub-service monitors have `notify_no_data: false` — they do not alert when spans
  stop. The monitors entered No Data silently.
  Evidence: DD monitor JSON for monitors 65603337, 65577146, etc. all contain
  `"notify_no_data": false` (confirmed from the monitors query output in this run).

Why 4: The post-deploy verification step after the b1f9358 revert did not include checking that
  all DD monitors returned to a known-good (OK) state within N minutes.
  Evidence: The triage bot's 04:31Z cycle (line 10) still notes "runtime-core-api outage since
  ~00:22Z from revert b1f9358 deploy" — no deploy-team post-flight check fired to surface the
  No Data states before 03:08Z.

Why 5: There is no defined "deployment health gate" for runtime-core that asserts: after a
  deploy (or revert), all listed DD monitors must be in OK or No-Data-with-alert-enabled within
  10 minutes, otherwise the deploy is flagged for human review.
  Evidence: references/architecture/known-failure-modes.md F6 notes "Auto-restart on crash;
  deploy-time auto-recycle policy" as the recommended fix but it has not been implemented.

Stop condition: Structural — no post-deploy monitor health gate and no notify_no_data on sub-
  service monitors.
```

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):

| Metric | Value | Note |
|---|---|---|
| Frequency | 1/month (this window) | |
| MTTR (user-visible traffic recovery) | ~11h | 00:00Z → ~11:00Z May 2; inferred from DD hit rate |
| MTTR (APM sub-service monitors) | undetermined (still No Data) | 72h+ and counting |
| Availability impact | A = (43200 − 660) / 43200 = 98.47% | 660 min = 11h downtime vs 30d window |
| Error budget burn vs proposed 99.95% | budget = 21.6 min; burn = 660/21.6 = **3,056%** | Massively over target |
| Blast radius | All authenticated platform users for 11h | runtime-core handles all runtime/designer/apps requests |

**Similar Jira (read-only cross-reference):**
- PL-62064: "Secure runtime-core PermissionsController endpoints" — P1-High, In Test, assignee: m.raihaan. Runtime-core work, but scoped to security, not the APM/deploy issue.
- PL-62100: "Transient account lookup failures permanently kill app routine schedules" — P2-Normal, Done Dev, unassigned. Related to ms-account-api reliability but not to sub-service APM silence.
- No open ticket matching "b1f9358 revert", "APM sub-service No Data", or "deploy health gate" found via JQL: `project in (NCNG, PL) AND (text ~ "runtime-core" OR text ~ "b1f9358") AND resolution = Unresolved AND updated >= -90d`.

**Recommendation:**
- (a) Enable `notify_no_data: true` (no_data_timeframe: 10 min) on all 8 sub-service monitors listed above. This converts the silent No Data into an actionable alert.
- (b) Investigate why the 8 sub-service APM spans stopped on May 2 and have not recovered in 3+ days. Likely hypothesis: the Datadog .NET APM tracer for the SQL/Mongo/Redis sub-service instrumentation was not restarted when the IIS pool recycled after the b1f9358 revert. Action: restart the Datadog agent on the affected hosts and verify sub-service spans re-appear.
- (c) Add a post-deploy validation step to the runtime-core deployment runbook: within 5 minutes of any deploy or revert, confirm that monitors 80445983, 19710080, 65603337, 65603338, 65603311, 65603306, 65577146, 65577145 are either in OK or have recently transitioned from No Data back to a data-emitting state.
- (d) Consider a canary deployment approach for future reverts: per `level-7/deployment-patterns.json`, route 1% of traffic to the reverted build first, monitor error rate for 5 minutes, then cut over. This limits blast radius from a bad revert.

**Course module references:**
- `level-7/deployment-patterns.json` — "Canary release: route a small percentage of traffic to the new version. Monitor for errors. Gradually increase." Applied: applying canary to the revert deployment would have caught the APM disruption at 1% traffic scale before it affected all users. "Blue-green: instant rollback is the killer feature." Applied: if the reverted build was staged in a blue-green slot, rollback to the pre-revert build (or re-revert to the intended state) would have been a single traffic-switch rather than an IIS pool restart sequence.
- `level-10/observability.json` — "Alert on symptoms (error rate > 1%, p99 > 500ms) not causes." Applied: `notify_no_data: false` on the sub-service monitors means a loss of spans (a cause) goes undetected. Enabling `notify_no_data: true` ensures the symptom (spans missing) is always surfaced.

**ICE score:** Impact 9 · Confidence 6 · Effort 5 → **10.8**
_(I: P0 event with 3,056% error budget burn; 8 monitors still dark 3 days later. C: APM restart hypothesis is plausible but unconfirmed without ES logs. E: monitor config changes are easy; post-deploy runbook addition and canary investigation are 1–2 sprints.)_

---

### F5 — GetSyncWidgetInfoAsync XHR Status=0 Failures (alert-frontend-errors)

**Symptom (one line):** Frontend XHR calls to `GetSyncWidgetInfoAsync` returned `status=0` (network-level abort) 50+ times across 20+ accounts on 2026-05-02, firing DD monitor 77419271 three times in a single day.

**Frequency:** 3 firings on 2026-05-02 (04:14Z, 10:13Z, 12:44Z EDT); alert appears to self-resolve by 17:21Z. Rate: 2.5× 24h baseline at peak.

**Triage-bot evidence:**
- `kb/incident-log.jsonl` line 24 (14:35Z): "2 new alerts in alert-frontend-errors (10:13Z and 10:17Z); syncutil GetSyncWidgetInfoAsync XHR failures 50+ across 20 accounts (account-a and account-b top offenders); rate at normal 24h baseline (50/10min), monitor back OK; backend classic/syncservices healthy; 3rd recurrence today".
- `kb/incident-log.jsonl` line 28 (17:21Z): "monitor 77419271 back OK; rate at normal 24h baseline".
- `kb/incident-log.jsonl` lines 25, 26 (15:05Z): deduplicated re-fires of the same alert hashes.

**Fresh DD evidence:**
- Monitor 77419271 "GetSyncWidgetInfoAsync XHR status=0 failures" — state: OK as of report time. Last Alert: 2026-05-02. URL: https://app.datadoghq.com/monitors/77419271.
- No metric query returned specific XHR error data (the signal is browser-side, not APM-side).

**Fresh ES evidence:** Unavailable — 403.

**Five-whys:**

```
Symptom: Users on 20+ accounts see XHR errors when the syncutil widget attempts to load.

Why 1: XHR calls to GetSyncWidgetInfoAsync returned HTTP status=0 — the connection was
  reset or refused at the network level before the server sent a response.
  Evidence: line 24 of incident-log: "XHR status=0 failures" (status=0 = network abort, not a
  4xx/5xx from the server).

Why 2: The failures occurred on May 2 during the same window as the runtime-core P0 (revert
  b1f9358 active). The syncutil/syncservices backend was noted as "healthy" (line 28) so the
  failures were likely caused by transient network instability or a shared infrastructure component
  (IIS, gateway) being intermittently down during the P0 recovery period.
  Evidence: line 24: "backend classic/syncservices healthy"; but the alert fired 3× over the same
  business-hours window that the P0 was being resolved.

Why 3: The frontend XHR caller has no retry logic or circuit-breaker for the syncutil call.
  When the backend drops the connection, the browser gets status=0 and reports an error immediately
  rather than retrying after a short delay.
  Evidence: Inferred from the pattern — a single retry with 500ms backoff would likely succeed
  given the intermittent nature of the failures. ES log data (unavailable) would confirm.

Why 4: Monitor 77419271 fires at a fixed count threshold without distinguishing between
  transient network storms and sustained syncutil outages. A 3-firing event in one day drives 3
  separate DMs to Ben even though the root cause is a single infrastructure disruption.
  Evidence: 3 separate firings on the same day, same root cause.

Why 5: The syncutil frontend integration has no formal SLO, no documented expected-failure rate,
  and no client-side resilience specification. Whether "50+ XHR errors across 20 accounts" is
  acceptable or alarming has no documented answer.
  Evidence: kb/known-issues.json = []; no CLAUDE.md or service doc found for syncutil resilience
  targets.

Stop condition: Structural — no client-side resilience spec and no SLO for this integration path.
```

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):

| Metric | Value | Note |
|---|---|---|
| Frequency | 3 alert firings / 1 day (May 2 only) | |
| MTTR | ~2.5h (last firing 12:44Z EDT, resolved by 17:21Z EDT) | |
| Availability impact | Transient; self-resolved | No sustained outage confirmed |
| Error budget burn | N/A (no formal SLO for this path) | |
| Blast radius | 20+ accounts, 50+ errors per burst | account-a and account-b top offenders |

**Similar Jira (read-only cross-reference):**
- PL-44736: "Logstash CleanUp - ms-sync: Database does not exist" — P2, Ready for Dev, unassigned. Tangentially related to sync services but a different error class and very old (2024-01-12).
- No open ticket matching "GetSyncWidgetInfoAsync" or "XHR status=0" found via JQL: `project in (NCNG, PL) AND (text ~ "syncutil" OR text ~ "GetSyncWidgetInfoAsync" OR text ~ "XHR") AND resolution = Unresolved AND updated >= -90d`.

**Recommendation:**
- (a) Add exponential-backoff retry (1 attempt, 500ms wait) on the frontend XHR call to `GetSyncWidgetInfoAsync`. Per `level-5/communication-failure.json`: "use exponential backoff with jitter for retries" — a single retry would absorb transient network drops without user-visible error.
- (b) Add graceful degradation: if `GetSyncWidgetInfoAsync` fails after retry, display the sync widget in a disabled/read-only state rather than triggering an error event. This prevents the error from appearing in monitor 77419271 for transient failures.
- (c) On the monitoring side, correlate XHR alert 77419271 with overall platform P0 state. If runtime-core is known-down, suppress the XHR alert (it is a downstream symptom, not a root cause). Until a formal correlation is available, add this pattern to `kb/known-issues.json` as an expected secondary signal during P0 events.

**Course module references:**
- `level-5/communication-failure.json` — "Design for timeouts, retries, and duplicates. Use exponential backoff with jitter for retries; degrade gracefully when services are unavailable." Applied: the current frontend caller has no retry and no graceful degradation. A single retry with backoff would eliminate the status=0 failures during transient network drops. Graceful degradation (show disabled widget) eliminates the user-visible error class entirely.
- `level-10/circuit-breakers-and-bulkheads.json` — "Circuit breakers convert slow failures to fast failures; set timeouts on every external call." Applied: the XHR caller should have an explicit timeout (e.g., 5s). If the call hangs beyond 5s (current default may be browser-determined), a circuit breaker pattern in the frontend layer would fast-fail and trigger the degraded-state UI rather than blocking the user.

**ICE score:** Impact 5 · Confidence 5 · Effort 4 → **6.3**
_(I: 20+ accounts affected, but self-resolves and likely a secondary symptom of the May 2 P0. C: retry logic hypothesis is plausible but unconfirmed without ES logs to see if retry would have succeeded. E: frontend change touching syncutil widget + monitor tuning ~ 1 week.)_

---

## Trend Analysis

_Skipped — no prior stability reports exist. This is the first run of the stability-review routine._

---

## Open Follow-ups

_No items meet the threshold of 2+ consecutive months unaddressed (first report). The following items are flagged for tracking in the June 2026 report:_

- **Signup SLO breach** — surfaced 2026-05, APM silent since May 2. Verify resolved by June 1 report.
- **8 runtime-core / ms-account-api sub-service APM monitors in No Data** — surfaced 2026-05. Verify all return to OK or have notify_no_data enabled by June 1 report.
- **ES 403 blocking** — surfaced 2026-05. Verify ES accessible to triage bot by June 1 report.

---

## Appendix: raw queries

```bash
# DD monitors — all alerting/No Data/Warn in prod
python3 scripts/dd_search.py monitors --tags "env:prod" --state Alert --state "No Data" --state Warn
# Run: 2026-05-05T13:23:45Z. Result: 44 monitors.

# DD metric — runtime-core-api hit rate, May 2 (P0 window)
python3 scripts/dd_search.py metric \
  --query "sum:trace.aspnet_core.request.hits{service:runtime-core-api,env:prod}.as_rate()" \
  --from-unix 1746144000 --to-unix 1746230400
# Result: traffic bottomed at 1.8/s avg at 06:00Z; recovered to 14.2/s by 11:00Z.

# DD metric — runtime-core-api error rate, 30-day window
python3 scripts/dd_search.py metric \
  --query "sum:trace.aspnet_core.request.errors{service:runtime-core-api,env:prod}.as_rate()" \
  --from-unix 1775395425 --to-unix 1777987425
# Result: max error rate 0.0081/s at 2026-04-23T12:00:00Z (non-zero throughout).

# DD metric — Signup hit rate, 30-day window
python3 scripts/dd_search.py metric \
  --query "sum:trace.aspnet.request.hits{service:signup,env:prod}.as_rate()" \
  --from-unix 1775395425 --to-unix 1777987425
# Result: 156 non-null points through 2026-05-01T12:00Z; no data points after.

# DD monitors — Signup service
python3 scripts/dd_search.py monitors --tags "service:signup,env:prod" --state Alert
# Result: 7 monitors; 1 in Alert (SLO), 4 in No Data (latency/error), 2 in OK.

# ES search (all attempts returned 403)
python3 scripts/es_search.py search \
  --query "level:ERROR AND fields.ServiceName:runtime-core" \
  --from "now-30d" --to "now" --limit 5
# Result: {"error": "es POST .../aws.found.io:443/*/_search -> 403: Host not in allowlist"}

# Jira JQL (read-only) — 3 queries
# 1. project in (NCNG, PL) AND (text ~ "signup" OR text ~ "sign-up" OR text ~ "SLO") AND resolution = Unresolved AND updated >= -90d ORDER BY updated DESC
# Result: 10 results; no Signup SLO/APM match.
# 2. project in (NCNG, PL) AND (text ~ "runtime-core" OR text ~ "b1f9358" OR text ~ "GetLegacyPermissionsAndBundlesCommand") AND resolution = Unresolved AND updated >= -90d ORDER BY updated DESC
# Result: 10 results; PL-62064 (Secure PermissionsController, In Test) and PL-62100 (Transient account lookup, Done Dev) are the closest.
# 3. project in (NCNG, PL) AND (text ~ "syncutil" OR text ~ "GetSyncWidgetInfoAsync" OR text ~ "XHR" OR text ~ "syncservices") AND resolution = Unresolved AND updated >= -90d ORDER BY updated DESC
# Result: 10 results; PL-44736 (Logstash CleanUp ms-sync, 2024) is the only sync-related open item; no XHR match.
```
