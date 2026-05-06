> _Updated 2026-05-06T13:23:38Z — superseding earlier run (2026-05-05T13:23:45Z)_

# Method Platform Stability Review — 2026-05

_Generated: 2026-05-06T13:23:38Z · Window: 2026-04-06T13:23:38Z → 2026-05-06T13:23:38Z (30d) · Routine: stability-review v0.1_

> **Effective observation span: 6 days (May 1–6).** The triage-bot began operating on 2026-05-01. All incident-log entries with alert-level classifications fall within May 1–6. The window denominator (30 days = 43,200 min) is used for availability calculations; error-budget burn figures are therefore upper-bounds — a full 30-day cycle would produce lower burn percentages if the remaining 24 days were incident-free. Trend analysis is available between this run and the prior run (2026-05-05), but with only a 1-day delta.

---

## Executive Summary

- Triage-bot processed **85 incident-log lines** in the window: 75 poll-cycle entries, 1 needs-human (confidence 0.30), 8 deduplicated, 1 stability-review. Zero KB entries exist (first month). Conservative mode (<50 cumulative investigations) was in effect throughout.
- The May 2 P0 (revert of `b1f9358`) was the dominant event. User-visible traffic recovered in ~11 hours; however full 5XX error resolution was not confirmed until **2026-05-06T13:11Z** — 4 days 13 hours after the event. The Signup service SLO has been in Alert for **7+ days** as of this report with APM still in No Data.
- A Serilog migration initiative (multiple `PL-40xxx`/`PL-61xxx` tickets) is active across several services. Until the ES allowlist is fixed, zero log-based investigation is possible for any migrated service.

**Top 5 recommendations (ranked by ICE score):**

1. **Add triage bot's execution-environment IP to ES allowlist** — ICE 36.0. Blocks 100% of log investigation. Now more urgent: active Serilog migration means more services are adding ES as their log sink. Single Elastic Cloud console config change.
2. **Identify prod-new-04 daily scheduled job and add KB false-alarm entry** — ICE 16.0. Eliminates ~1 DM/day to Ben. 1–2 hours of RDP investigation.
3. **Investigate Signup APM silence and formally define Signup SLO** — ICE 13.5. Signup SLO has been Alert for 7+ days; APM in No Data for 4+ days. Direct revenue pipeline impact.
4. **Enable `notify_no_data` on 8 sub-service monitors; add post-deploy validation step** — ICE 10.8. 8 monitors still dark 4+ days after the P0. Full 5XX recovery only confirmed today.
5. **Add client-side retry / graceful degradation for GetSyncWidgetInfoAsync XHR calls** — ICE 6.3. Recurring frontend noise (3× May 2, 2× May 6 deduplicated).

**Availability snapshot per critical service (vs proposed SLO):**

| Service | Window availability (est.) | Proposed SLO | Budget burn (est.) |
|---------|---------------------------|--------------|-------------------|
| runtime-core-api (user-visible traffic) | 98.47% | 99.95% | **3,056%** |
| Signup | undetermined (APM No Data since May 2) | (none formal) | SLO burn rate >30× (monitor 154229727) |
| ms-account-api sub-services (APM) | No Data since May 2 | (none formal) | undetermined |
| ES investigation tool | ~0% (403 throughout) | (internal tool) | N/A |

Total error budget consumed across listed services: **runtime-core 3,056% of proposed 99.95% target** in window. Signup and ms-account-api sub-service budgets undetermined due to APM silence.

---

## Methodology

- Sources read: `kb/incident-log.jsonl` (85 lines), `docs/investigations/2026-05-04-5024f8254f1c6a39.md` (1 report), `kb/known-issues.json` (empty), `kb/false-alarms.json` (empty).
- Fresh DD queries: 9 (`scripts/dd_search.py monitors` ×2, `metric` ×3, detail extraction from cached monitor list for 8 specific IDs).
- Fresh ES queries: 1 attempted — **all returned 403 (ES host not in allowlist)**. Zero ES data available.
- Jira JQL queries (read-only): 3 sweeps (ES/triage-bot, Signup, runtime-core/APM/deploy-health). No directly matching open tickets found.
- Course modules consulted: 5 (`level-7/deployment-patterns.json`, `level-10/observability.json`, `level-1/availability-and-slas.json`, `level-10/circuit-breakers-and-bulkheads.json`, `level-5/communication-failure.json`).
- Five-whys protocol: `references/methodology/five-whys-template.md`.
- Prior report: `stability-reviews/2026-05/report.md` (generated 2026-05-05T13:23:45Z).

---

## Findings

### F1 — Elasticsearch 403: Persistent Investigation Blind Spot (Worsening)

**Symptom (one line):** Every Elasticsearch query in the window returned HTTP 403 (`host not in allowlist`), blocking log-based investigation. Severity is increasing as the Serilog migration initiative moves more services to ES as their log sink.

**Frequency:** 100% of ES queries attempted during May 1–6 blocked. Active for the full 6-day observation period with no sign of remediation.

**Triage-bot evidence:**
- `kb/incident-log.jsonl` multiple poll-cycle entries noting "ES blocked 403" (every cycle that attempted ES).
- `docs/investigations/2026-05-04-5024f8254f1c6a39.md` §Tools Run: `ES | Unavailable — 403 host not in allowlist`.
- This review: `python3 scripts/es_search.py search --query "level:ERROR" --from "now-30d"` → same 403 error.

**Fresh DD evidence:** N/A (this finding is about ES tool unavailability, not a DD monitor state).

**Fresh ES evidence:** `{"error": "es POST https://ca8e80d7f930400fb386a29477353efa.us-west-1.aws.found.io:443/*/_search -> 403: Host not in allowlist"}`. Kibana URL: unavailable.

**New context (Jira, read-only):** JQL `project in (NCNG, PL) AND (text ~ "elasticsearch" OR text ~ "ES allowlist" OR text ~ "triage bot") AND resolution = Unresolved AND updated >= -90d` returned five "move to serilog: \<service\>" tickets (PL-61595 In Test, PL-40965 Done Dev, PL-61229 Done Dev, PL-40959 Ready For Dev, PL-40962 Ready For Dev — all assigned to k.mifflin). None directly address the allowlist gap; but the Serilog migration initiative confirms ES log coverage is actively expanding. Every newly migrated service that produces log data the triage bot cannot read amplifies the investigation blind spot.

**Five-whys:**

```
Symptom: Every ES investigation query returns 403 — no log data accessible to the triage routine.

Why 1: The triage bot's execution environment IP is not in the Elasticsearch allowlist.
  Evidence: Verbatim error message across all es_search.py calls: "403: Host not in allowlist".

Why 2: The ES allowlist was configured for on-premises dev workstations and prod IIS hosts,
  not for cloud-based automation runners. The ES endpoint is Elastic Cloud hosted
  (ca8e80d7f930400fb386a29477353efa.us-west-1.aws.found.io). Allowlists are managed
  via the Elastic Cloud console; the triage-bot IP range was never added.
  Evidence: Error URL domain matches Elastic Cloud dedicated deployment format.

Why 3: When the triage bot was set up, no "onboard a new automation client" checklist was
  followed to verify ES access from the runner's IP.
  Evidence: kb/incident-log.jsonl first entry is 2026-05-01T19:26Z (first poll cycle); the
  403 was first encountered on May 2 during the P0 investigation — ES access was not
  smoke-tested before the bot went live.

Why 4: The triage playbooks assume ES is accessible but include no startup health check that
  verifies connectivity and posts a warning if ES returns 403.
  Evidence: scripts/tool_health.py exists but the triage prompt does not include an ES
  accessibility pre-check step; silent degradation is the current behaviour.

Why 5: No "monitoring tool access" contract exists. The system relies on engineers knowing
  which tools the automation uses and manually provisioning access when automation is added.
  Evidence: No CLAUDE.md or playbook section describes the process for adding a new
  automation runner's IP to ES, DD, or other observability tool allowlists.

Stop condition: Structural — missing access-provisioning process for automation tooling.
```

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):

| Metric | Value | Note |
|---|---|---|
| Frequency | 100% of ES queries blocked | All attempts in May 1–6 |
| MTTR | undetermined (still blocked at report time) | 5+ days and counting |
| Availability impact | ~0% ES access / 30d | 100% of log investigation blocked |
| Error budget burn | N/A (internal tool, no SLO) | Qualitative: half the investigation playbook unusable |
| Blast radius | Every triage investigation in window degraded | Zero log corroboration on any alert |

**Similar Jira (read-only cross-reference):**
- PL-61595: "move to serilog: emailgadget-signin-ui" — In Test, k.mifflin. Active Serilog migration confirms ES is the intended log destination for more services; the allowlist gap becomes more costly over time.
- No open ticket matching "ES allowlist" or "triage bot IP" found.

**Recommendation:**
- (a) Add the triage bot's execution-environment IP range to the Elasticsearch allowlist via the Elastic Cloud console. Verify with `python3 scripts/es_search.py search --query "level:ERROR" --from "now-1h" --limit 1`.
- (b) Alternatively, route ES queries through the SSH bastion — lower blast radius if the IP is dynamic or NAT'd.
- (c) Add an ES health-check step to `scripts/tool_health.py`; call it at the start of each poll cycle; post `🔴 ES inaccessible (403)` to `#triage-bot-health` if it fails. Converts silent degradation to a visible failure, consistent with the observability principle below.

**Course module references:**
- `level-10/observability.json` — "Alert on symptoms, not causes. RED method (Rate, Errors, Duration) for services." Applied: the ES log pipeline is the primary symptom-investigation tool. Its unavailability means triage bot can only observe metrics (causes) and cannot confirm user-visible symptoms from logs. The lack of a health-check on the tool itself means the failure is invisible — a structural observability gap.
- `level-5/communication-failure.json` — "Design for timeouts, retries, and duplicates; degrade gracefully when services are unavailable." Applied: the triage routine should degrade gracefully (DD-only investigation) and surface the degradation rather than silently omitting ES data.

**ICE score:** Impact 8 · Confidence 9 · Effort 2 → **36.0**
_(I: removes a tool-access failure that blocks half the investigation playbook for every alert; worsening as Serilog migration proceeds. C: IP allowlist addition is a well-understood config change. E: single Elastic Cloud console action + ~10 lines in tool_health.py.)_

---

### F2 — prod-new-04 Daily CPU Spike: Centreon Alert Noise and KB Gap

**Symptom (one line):** Centreon fires a CPU alert on `prod-new-04` every day at approximately 08:39Z, after the 08:23–08:38Z spike has self-resolved; the triage bot cannot read the alert body (Slack blocks only) and DMs Ben each occurrence as `needs-human`.

**Frequency:** 1 confirmed investigation (2026-05-04). DD 24h-ago baseline confirms identical CPU spike on 2026-05-03 at the same UTC hour. Estimated 5 occurrences in the 5-day observation window; extrapolated ~30/month.

**Triage-bot evidence:**
- `docs/investigations/2026-05-04-5024f8254f1c6a39.md` §Key Findings: "CPU resolved at 08:38 UTC — 1 minute before the Centreon alert posted at 08:39 UTC"; "24h baseline is identical: yesterday 08:22–08:38 UTC showed max 53%, avg 44%".
- `kb/incident-log.jsonl` line at 2026-05-04T11:09:25Z (duration_s=4286 — long investigation for an already-resolved event).

**Fresh DD evidence:**
- `system.cpu.user{host:prod-new-04}` spike 08:23–08:38Z, peak 59%, self-resolved: https://app.datadoghq.com/metric/explorer?live=false&exp_metric=system.cpu.user&exp_scope=host%3Aprod-new-04&start=1777882940&end=1777884000
- `iis.uptime{host:prod-new-04}` = 285,532s at alert time — no IIS recycle.
- `iis.net.num_connections{host:prod-new-04}` stable 24–31 throughout — no user-traffic spike driving CPU.

**Fresh ES evidence:** Unavailable — 403.

**Five-whys:**

```
Symptom: Triage bot DMs Ben daily about a Centreon alert that has already resolved.

Why 1: Centreon fires a CPU threshold alert after the spike resolves, due to notification lag.
  Evidence: investigation 5024f8254f1c6a39: spike 08:23–08:38Z, alert posted 08:39Z (1 min lag).

Why 2: A daily scheduled process on prod-new-04 consumes ~50% CPU for ~15 minutes at 08:23Z.
  Evidence: DD system.cpu.user shows identical spike on consecutive days at the same hour.
  IIS connections stable; no backend errors → not user traffic.

Why 3: The triage bot cannot read the Centreon alert body (Slack MCP does not surface block
  content as text), so it cannot correlate to the known daily pattern.
  Evidence: investigation 5024f8254f1c6a39 §Alert Summary: "Alert text: (empty — full content
  in Slack blocks only; not accessible via Slack MCP)".

Why 4: No kb/false-alarms.json entry exists for this daily Centreon pattern.
  Evidence: kb/false-alarms.json = []. Suggested KB entry template exists in investigation
  5024f8254f1c6a39 §Suggested KB Entry but was not added: the scheduled job identity on
  prod-new-04 was not confirmed (ES blocked, no process-level metrics).

Why 5: The investigation playbook has no "expected-daily-noise" review step that would prevent
  a known-good daily event from requiring a full investigation on first encounter.
  Evidence: The triage prompt does not include a "known schedule correlation" check before
  escalating a CPU spike alert to needs-human classification.

Stop condition: Structural — missing KB entry + missing block-content access + no schedule-
  correlation lookup in the playbook.
```

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):

| Metric | Value | Note |
|---|---|---|
| Frequency | ~30/month (daily) | 5-day observation extrapolated |
| MTTR | ~0 min (self-resolves before alert) | Not a real outage; Centreon lag is the issue |
| Availability impact | 0% (no customer-visible impact confirmed) | IIS stable, no backend errors |
| Error budget burn | N/A (false alarm class) | |
| Blast radius | 1 investigation/day wasted | Est. $1–2 USD/day in routine cost |

**Similar Jira (read-only cross-reference):**
- No open ticket matching "prod-new-04" or "Centreon CPU" found via JQL.

**Recommendation:**
- (a) RDP to prod-new-04; check Windows Task Scheduler and SQL Server Agent jobs scheduled around 08:20–08:25 UTC. Confirm the job is expected.
- (b) Once confirmed, add to `kb/false-alarms.json` using the template in investigation 5024f8254f1c6a39 §Suggested KB Entry.
- (c) Investigate whether Centreon can include a plain-text summary alongside the Slack block payload — this would unblock correlation logic for all Centreon alert classes.

**Course module references:**
- `level-10/observability.json` — "Alert on symptoms, not causes." Applied: Centreon's CPU % threshold is alerting on a cause (utilisation) rather than a symptom (user-visible degradation). The spike is a scheduled batch job with no customer impact. Re-configure to fire only when CPU elevation correlates with service degradation (IIS error rate rise or connection spike).

**ICE score:** Impact 4 · Confidence 8 · Effort 2 → **16.0**
_(I: eliminates ~1 daily DM to Ben + 1 unnecessary investigation. C: KB entry + job identification is straightforward. E: 1–2 hours of engineer time.)_

---

### F3 — Signup Availability SLO Breach and APM Silence (Still Ongoing, Day 7+)

**Symptom (one line):** The Signup service Availability SLO has been in Alert since 2026-04-29 (7+ days at this report); all Signup APM monitors entered No Data on 2026-05-02 at 15:50–16:00Z and remain in No Data (4+ days with no recovery).

**Frequency:** 1 ongoing SLO breach event; 7+ consecutive days at report time.

**Triage-bot evidence:**
- `kb/incident-log.jsonl` multiple poll-cycle entries noting "Signup SLO Alert ongoing since Apr 29" across May 1–6.

**Fresh DD evidence (as of 2026-05-06T13:23Z):**
- Monitor 154229727 "Service Signup Availability SLO" — state: **Alert**, last_changed: 2026-04-29T16:36:27. Burn rate >30× over 7d window. URL: https://app.datadoghq.com/monitors/154229727.
- Monitor 154230536 "Service Signup has a high error rate" — state: **No Data** since 2026-05-02T15:54:56. No recovery in 4+ days.
- Monitor 154251781 "Signup page load p90" — state: **No Data** since 2026-05-02T15:54:01.
- Monitor 154252126 "Signup post p90" — state: **No Data** since 2026-05-02T15:50:46.
- Monitor 154252601 "Signup avg latency" — state: **No Data** since 2026-05-02T16:00:41.
- Monitor 154163500 "Signup unexpected number of errors" — state: **Alert**, last_changed: 2026-04-29T16:31:41.
- Metric `trace.aspnet.request.hits{service:signup,env:prod}`: 150 non-null points through 2026-05-01T12:00Z (avg 0.020/s), then zero data through the full May 2–6 window. URL: https://app.datadoghq.com/metric/explorer

**Fresh ES evidence:** Unavailable — 403.

**Fresh Jira (read-only):** JQL `project in (NCNG, PL) AND (text ~ "signup" OR text ~ "sign-up") AND resolution = Unresolved AND updated >= -90d` returned PL-62669 "An error message appears when loading the 'Invite User' dialog during Onboarding and when loading the 'Email' tab of the 'User Profile' page" — P1-High, To Do, unassigned. This may reflect a related symptom (onboarding/signup-adjacent flows erroring). No direct match to "Signup SLO breach" or "APM No Data". No open ticket for the root cause.

**Five-whys:**

```
Symptom: Signup SLO in Alert for 7+ days; all Signup APM monitors No Data for 4+ days.

Why 1: The Signup service Availability SLO shows a burn rate >30× its budget over 7 days.
  Evidence: DD monitor 154229727, state=Alert since 2026-04-29T16:36:27.

Why 2: The SLO breach started Apr 29 (Phase 1: actual errors). On May 2 at 15:50Z, all Signup
  APM spans stopped (Phase 2: APM silence), likely a side-effect of the runtime-core P0
  recovery disrupting the shared APM pipeline.
  Evidence: Signup hit rate non-null avg 0.020/s through May 1 12:00Z, then zero.
  The No Data transition (15:50–16:00Z May 2) coincides with the runtime-core APM recovery
  window noted in triage-bot poll cycles.

Why 3: Once APM spans stopped, the 4 latency/error monitors entered No Data silently.
  notify_no_data is false on all four monitors. Any subsequent Signup errors are invisible.
  Evidence: monitors 154230536, 154251781, 154252126, 154252601 all No Data and not alerting.

Why 4: No Signup-specific synthetic monitor exists independent of APM instrumentation.
  Evidence: All Datadog Synthetic monitors in the window are tagged "Method UI Grid and
  Dropdown Performance" (runtime app tests). No sign-up registration flow synthetic exists.

Why 5: The Signup service has no formal SLO document defining what signals to measure, what
  redundant measurement paths are required, and what alerting is needed for the SLO to be
  credible. The SLO monitor fires a burn-rate alert but has no independent verification path.
  Evidence: references/architecture/platform-overview.md §"SLOs": "None defined."
  Signup is not in known-failure-modes.md with a proposed SLO.

Stop condition: Structural — no formal SLO document, no synthetic monitor, no notify_no_data
  on APM monitors.
```

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):

| Metric | Value | Note |
|---|---|---|
| Frequency | 1 ongoing breach (started Apr 29) | Now 7+ days, vs 6+ days in prior report |
| MTTR | undetermined (still ongoing at report time) | |
| Availability impact | undetermined (APM No Data for 4+ days) | Cannot compute without spans |
| Error budget burn | >30× burn rate over 7d window | Monitor 154229727; actual % requires SLO metric read |
| Blast radius | All new user sign-ups during breach | Direct revenue pipeline impact |

**Similar Jira (read-only cross-reference):**
- PL-62669: "error loading Invite User dialog during Onboarding" — P1-High, To Do, unassigned. Tangentially related (onboarding flow). Not a Signup SLO/APM ticket.
- No open ticket matching "Signup SLO" or "Signup APM No Data" found.

**Recommendation:**
- (a) Immediately investigate why Signup APM stopped on May 2 at 15:50Z. Check whether the `signup` service IIS app pool was restarted during the runtime-core P0 recovery window and whether the Datadog .NET APM tracer was properly restarted alongside it.
- (b) Add `notify_no_data: true` (no_data_timeframe: 10 min) to monitors 154230536, 154251781, 154252126, 154252601 so APM silence triggers an alert rather than silent No Data.
- (c) Create a Datadog Synthetic monitor for the Signup registration flow independent of APM — provides signal even when the APM pipeline is down.
- (d) Formally document Signup SLO targets in `references/architecture/known-failure-modes.md` (proposed: error rate < 0.1%, p90 page load < 4s, availability > 99.9% over 30d).

**Course module references:**
- `level-1/availability-and-slas.json` — "Use SLIs to measure, SLOs as internal targets, and SLAs as customer contracts. In series systems, overall availability is the product of components — improve the weakest link first. Redundancy (parallel components) is how you achieve high availability." Applied: the Signup SLO currently has a single measurement path (APM spans). When the APM pipeline fails, the SLO measurement fails too. Adding a synthetic as a redundant SLI path preserves observability during APM outages — consistent with the principle that reliability through parallel paths is 1 − (1−A₁)×(1−A₂).
- `level-10/observability.json` — "RED method (Rate, Errors, Duration) for services. Alert on symptoms, not causes." Applied: the current Signup monitoring detects symptoms via APM but has no independent symptom check. A synthetic test checks the symptom (can a new user sign up?) without relying on APM infrastructure.

**ICE score:** Impact 9 · Confidence 6 · Effort 4 → **13.5**
_(I: ongoing 7-day SLO breach directly affects new user acquisition. C: APM silence root cause needs verification. E: IIS investigation + monitor config + synthetic creation ~1 week.)_

---

### F4 — May 2 Revert Deploy Cascade: Extended Recovery (Full 5XX Resolution Confirmed May 6)

**Symptom (one line):** Revert of commit `b1f9358` on 2026-05-02T00:00Z triggered a multi-service disruption; user-visible traffic recovered in ~11 hours, but elevated 5XX errors, designer-core-api anomalies, and RTC latency spikes persisted until **2026-05-06T13:11Z** (4 days 13 hours). 8 sub-service APM monitors remain in No Data.

**Frequency:** 1 P0-class event; extended tail lasting 4 days 13 hours. Confirmed by monitor 70171778 "Unexpected number of 5XX errors" recovering at 2026-05-06T13:11Z.

**Triage-bot evidence:**
- `kb/incident-log.jsonl` multiple entries across May 2–6 referencing the b1f9358 revert and runtime-core APM disruption.
- Deduplicated alert hashes on 2026-05-06T12:09Z (alert-frontend-errors, group 622af3d0d30741c5) — consistent with continued XHR noise as 5XX errors resolved.

**Fresh DD evidence (as of 2026-05-06T13:23Z):**
- Monitor 70171778 "Unexpected number of 5XX errors" — recovered to **OK** at 2026-05-06T13:11:38. Was Alert/firing since May 2. Recovery just confirmed. URL: https://app.datadoghq.com/monitors/70171778.
- Monitor 115456700 "RTC Screen Load has a high p95 latency" — recovered to **OK** at 2026-05-06T06:03:20. Was Alert post-revert. URL: https://app.datadoghq.com/monitors/115456700.
- Monitor 117279738 "RTC Action Execution has a high p95 latency" — recovered to **OK** at 2026-05-04T18:53:18.
- Monitor 115452625 "designer-core-api anomalous throughput" — recovered to **OK** at 2026-05-04T18:52:25.
- Monitor 115452626 "designer-core-api high average latency" — recovered to **OK** at 2026-05-04T18:52:26.
- Metric `trace.aspnet_core.request.hits{service:runtime-core-api}`: May 6 12:00Z = 34.0/s (30d avg 30.4/s). Full traffic recovery confirmed. URL: https://app.datadoghq.com/metric/explorer
- **Still No Data (unchanged):** 8 sub-service monitors — 80445983, 19710080, 65603337, 65603338, 65603311, 65603306, 65577146, 65577145 — all No Data since May 2 03:08–04:59Z. No recovery in 4+ days.
- **Still No Data:** Synthetics monitors 121308660, 123495390, 123495492, 133625690 — all showing No Data at their scheduled run times on May 5–6.

**Fresh ES evidence:** Unavailable — 403.

**Fresh Jira (read-only):**
- PL-62064: "Secure runtime-core PermissionsController endpoints" — P1-High, In Test, m.raihaan. Runtime-core work, scoped to security; not the APM/deploy issue.
- NCNG-1124: "Can't open action editor when mongo load fails for any action" — P3-Low, Ready For Dev, unassigned. Tangentially related (mongo failure in action editor); not the sub-service APM silence.
- No open ticket matching "b1f9358 revert", "APM No Data", "deploy health gate", or "notify_no_data" found.

**Five-whys:**

```
Symptom: The b1f9358 revert triggered a 4.5-day cascade: user-visible traffic down 11h, elevated
  5XX errors for 4 days 13h, 8 sub-service APM monitors still No Data at report time.

Why 1: APM spans for SQL Server, MongoDB, and Redis sub-services stopped on May 2 at 03:08Z;
  5XX errors elevated until May 6 13:11Z; RTC latency elevated until May 6 06:03Z.
  Evidence: Monitor state transitions above; `trace.aspnet_core.request.hits` recovering from
  1.8/s (06:00Z) to 14.2/s (11:00Z) to 34.0/s (May 6 12:00Z).

Why 2: The revert of b1f9358 at ~00:00Z May 2 disrupted APM instrumentation. Either the revert
  modified APM configuration, or the resulting IIS app pool recycle killed the Datadog .NET
  APM tracer for sub-service span emitters without automatic restart.
  Evidence: All 8 sub-service monitors entered No Data within 90 minutes of the revert
  (03:08–04:59Z May 2). ES 403 prevents log-level confirmation of the restart chain.

Why 3: All 8 sub-service monitors have notify_no_data: false — they entered No Data silently.
  Evidence: DD monitor JSON for monitors 65603337, 65577146, etc. confirm notify_no_data: false.
  4+ days of No Data with zero alert to surface the condition.

Why 4: The post-deploy verification step after the b1f9358 revert did not check that all DD
  monitors returned to OK within N minutes.
  Evidence: No deploy-team post-flight entry in incident-log correlating to the revert.

Why 5: There is no defined "deployment health gate" for runtime-core that asserts: after any
  deploy or revert, all listed DD monitors must be in OK or No-Data-with-alert-enabled within
  10 minutes, otherwise the deploy is flagged for human review.
  Evidence: references/architecture/known-failure-modes.md F6 notes "Auto-restart on crash;
  deploy-time auto-recycle policy" as the recommended fix — not yet implemented.

Stop condition: Structural — no post-deploy monitor health gate, no notify_no_data on sub-
  service monitors.
```

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):

| Metric | Value | Note |
|---|---|---|
| Frequency | 1/month (this window) | |
| MTTR (user-visible traffic) | A = (43,200 − 660) / 43,200 = 98.47% | 660 min = 11h from 00:00Z to ~11:00Z May 2 |
| MTTR (full 5XX resolution) | 6,551 min ≈ 4 days 13h | 2026-05-02T00:00Z → 2026-05-06T13:11Z |
| MTTR (APM sub-service monitors) | undetermined (still No Data) | 4+ days and counting |
| Availability impact | A = (43,200 − 660) / 43,200 = **98.47%** | Using conservative user-visible figure |
| Error budget burn vs proposed 99.95% | budget = (1 − 0.9995) × 43,200 = 21.6 min; burn = 660 / 21.6 = **3,056%** | Massively over target |
| Blast radius | All authenticated platform users for 11h; extended 5XX for 4.5 days | runtime-core handles all runtime/designer/apps requests |

**Similar Jira (read-only cross-reference):**
- PL-62064: "Secure runtime-core PermissionsController endpoints" — P1-High, In Test, m.raihaan. Related service, different scope.
- NCNG-1124: "Can't open action editor when mongo load fails" — P3-Low, Ready For Dev. Tangential.
- No ticket matching the deploy cascade, APM silence, or health-gate gap found.

**Recommendation:**
- (a) Enable `notify_no_data: true` (no_data_timeframe: 10 min) on all 8 sub-service monitors: 80445983, 19710080, 65603337, 65603338, 65603311, 65603306, 65577146, 65577145. This converts silent No Data into an actionable alert.
- (b) Investigate and restart the Datadog APM tracer on affected hosts. Hypothesis: the Datadog .NET APM tracer for the SQL/Mongo/Redis sub-service instrumentation was not restarted when the IIS pool recycled after the b1f9358 revert.
- (c) Add a post-deploy validation step to the runtime-core deployment runbook: within 5 minutes of any deploy or revert, confirm that all 8 sub-service monitors are in OK or have recently transitioned from No Data.
- (d) Per `level-7/deployment-patterns.json`: implement canary deployment for future reverts — route 1% of traffic to the reverted build, monitor 5 minutes, then cut over. Limits blast radius from a bad revert.

**Course module references:**
- `level-7/deployment-patterns.json` — "Canary limits blast radius by testing with a small percentage of traffic. Blue-green gives zero-downtime deployment with instant rollback." Applied: canary on the revert would have caught the APM disruption at 1% traffic scale before affecting all users. Blue-green would have made re-reverting a single traffic switch rather than an IIS recycle sequence.
- `level-10/observability.json` — "Alert on symptoms, not causes." Applied: `notify_no_data: false` means loss of APM spans (the signal a service is instrumented) goes undetected. Enabling `notify_no_data: true` ensures span absence is always surfaced.

**ICE score:** Impact 9 · Confidence 6 · Effort 5 → **10.8**
_(I: P0 with 3,056% error budget burn; 8 monitors still dark 4+ days later; full 5XX recovery only just confirmed. C: APM restart hypothesis plausible but unconfirmed without ES logs. E: monitor config easy; post-deploy runbook and canary ~1–2 sprints.)_

---

### F5 — GetSyncWidgetInfoAsync XHR Status=0 Failures (Recurring, Evidence Strengthened)

**Symptom (one line):** Frontend XHR calls to `GetSyncWidgetInfoAsync` return `status=0` (network-level abort), firing DD monitor 77419271; 3 firings on 2026-05-02 and 2 deduplicated alerts on 2026-05-06 confirm this is a recurring pattern, not isolated to the May 2 P0.

**Frequency:** 3 firings on 2026-05-02 (04:14Z, 10:13Z, 12:44Z EDT); 2 deduplicated alert-frontend-errors on 2026-05-06T12:09Z. Pattern spans 4 days.

**Triage-bot evidence:**
- `kb/incident-log.jsonl` line at 2026-05-02T14:35Z: "syncutil GetSyncWidgetInfoAsync XHR failures 50+ across 20 accounts; rate at normal 24h baseline, monitor back OK; 3rd recurrence today".
- `kb/incident-log.jsonl` 2026-05-06T12:09Z: 2 deduplicated alerts from `alert-frontend-errors` (alert_hash 622af3d0d30741c5 and 93e3139bc919cdca, grouped). While the specific error type is not confirmed without ES logs, the channel and timing (during the 5XX error tail period ending 13:11Z) is consistent with the XHR pattern.

**Fresh DD evidence:**
- Monitor 77419271 "GetSyncWidgetInfoAsync XHR status=0 failures" — state: OK as of report time. Last Alert: 2026-05-02. URL: https://app.datadoghq.com/monitors/77419271.
- Monitor 70171778 "Unexpected number of 5XX errors" recovered to OK at 2026-05-06T13:11Z, shortly after the May 6 12:09Z frontend alert deduplication — timing correlation suggests these are linked.

**Fresh ES evidence:** Unavailable — 403.

**Five-whys:**

```
Symptom: Users on 20+ accounts see XHR errors when the syncutil widget attempts to load.

Why 1: XHR calls to GetSyncWidgetInfoAsync return HTTP status=0 — the connection was
  reset or refused at the network level before the server sent a response.
  Evidence: incident-log line at 2026-05-02T14:35Z: "XHR status=0 failures".

Why 2: The failures correlate with platform infrastructure disruption (May 2 P0;
  May 6 5XX elevation). The syncutil/syncservices backend was noted as "healthy" at the
  time of May 2 investigations, suggesting the failures are caused by a shared infrastructure
  component (IIS, gateway) intermittently failing during the degraded periods.
  Evidence: 3 firings on May 2 (P0 day) and 2 deduplicated alerts May 6 (5XX tail day).
  Monitor 77419271 returns to OK when platform stabilises.

Why 3: The frontend XHR caller has no retry logic or circuit-breaker. When the backend drops
  the connection, the browser gets status=0 and reports an error immediately rather than
  retrying after a short delay.
  Evidence: Inferred from pattern — self-resolving within hours suggests transient network
  drops, which a single retry would absorb.

Why 4: Monitor 77419271 fires at a fixed count threshold without distinguishing transient
  network storms from sustained syncutil outages, driving 3 DMs from a single root cause.
  Evidence: 3 separate firings on May 2, same root cause, all self-resolved.

Why 5: The syncutil frontend integration has no formal SLO, no documented expected-failure
  rate, and no client-side resilience specification.
  Evidence: kb/known-issues.json = []; no CLAUDE.md entry for syncutil resilience targets.

Stop condition: Structural — no client-side resilience spec and no SLO for this integration path.
```

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):

| Metric | Value | Note |
|---|---|---|
| Frequency | 3 firings May 2 + 2 deduplicated May 6 | Pattern spans 4 days |
| MTTR | ~2.5h (last firing 12:44Z EDT May 2, resolved 17:21Z EDT) | |
| Availability impact | Transient; self-resolved | No sustained outage confirmed |
| Error budget burn | N/A (no formal SLO) | |
| Blast radius | 20+ accounts, 50+ errors per burst (May 2 data) | |

**Similar Jira (read-only cross-reference):**
- PL-44736: "Logstash CleanUp - ms-sync: Database does not exist" — P2, Ready for Dev, unassigned (2024-01-12). Tangentially related to sync services; different error class.
- No open ticket matching "GetSyncWidgetInfoAsync" or "XHR status=0" found.

**Recommendation:**
- (a) Add exponential-backoff retry (1 attempt, 500ms wait) on the frontend XHR call to `GetSyncWidgetInfoAsync`. Per `level-5/communication-failure.json`: a single retry with backoff would absorb transient network drops without user-visible error.
- (b) Add graceful degradation: if `GetSyncWidgetInfoAsync` fails after retry, display the sync widget in a disabled/read-only state rather than triggering an error event.
- (c) Correlate XHR alert 77419271 with overall platform P0 state. If runtime-core is known-down, suppress the XHR alert (it is a downstream symptom). Until formal correlation is available, add to `kb/known-issues.json` as an expected secondary signal during P0 events.

**Course module references:**
- `level-5/communication-failure.json` — "The network is unreliable — design for timeouts, retries, and duplicates. Use exponential backoff with jitter for retries; degrade gracefully when services are unavailable." Applied: the current frontend caller has no retry and no graceful degradation. A single retry with 500ms backoff eliminates the status=0 failure class during transient drops. Graceful degradation (disabled widget) eliminates the user-visible error class entirely.
- `level-10/circuit-breakers-and-bulkheads.json` — "Circuit breakers convert slow failures to fast failures; set timeouts on every external call — a missing timeout is a ticking time bomb." Applied: the XHR caller should have an explicit timeout (e.g., 5s). A circuit-breaker in the frontend layer would fast-fail and trigger the disabled-state UI rather than blocking the user during backend degradation.

**ICE score:** Impact 5 · Confidence 5 · Effort 4 → **6.3**
_(I: 20+ accounts affected; likely secondary symptom of platform P0s. C: retry logic hypothesis plausible but unconfirmed without ES logs. E: frontend change + monitor tuning ~1 week.)_

---

## Trend Analysis

_Comparing to prior run: `stability-reviews/2026-05/report.md` generated 2026-05-05T13:23:45Z._

| Metric | Prior run (2026-05-05) | This run (2026-05-06) | Δ |
|---|---|---|---|
| Total incident-log lines in window | 72 | 85 | +13 (1 day of poll activity) |
| Classified alert events | 1 needs-human, 6 deduped | 1 needs-human, 8 deduped | +2 deduped (May 6 frontend alerts) |
| Findings identified | 5 | 5 | No change |
| Signup SLO Alert duration | 6+ days | 7+ days | +1 day, no resolution |
| 8 sub-service APM monitors No Data | 3+ days | 4+ days | +1 day, no resolution |
| ES 403 blocking | 4+ days | 5+ days | +1 day, no resolution |
| 5XX error elevation | Ongoing (unresolved) | Resolved at 13:11Z May 6 | 4.5-day total duration |
| Top ICE recommendation | Add ES IP to allowlist (36.0) | Add ES IP to allowlist (36.0) | No change |

**Status of prior recommendations (from 2026-05-05 report):**

- **F1 (ES allowlist):** Still unaddressed. No Jira ticket; no observable action. The active Serilog migration makes this more urgent than yesterday.
- **F2 (prod-new-04 job identification):** Still unaddressed. Daily CPU alert continues.
- **F3 (Signup APM / SLO):** Still unaddressed. APM has not recovered; SLO still Alert. New Jira ticket PL-62669 (Invite User error) may be a related symptom but does not address the APM silence.
- **F4 (notify_no_data on sub-service monitors):** Still unaddressed. 8 monitors still No Data. However, the P0's extended impact is now better understood — full 5XX resolution confirmed today (4.5-day tail).
- **F5 (XHR retry):** Still unaddressed. Additional deduplicated alert-frontend-errors evidence on May 6 confirms the pattern persists.

**Note:** The 1-day gap between runs is too short to expect implementation progress. These items should be re-evaluated in the June 2026 report with the expectation of action.

---

## Open Follow-ups

_(Items from the May 5 report, now confirmed unaddressed. Escalation threshold: 2+ consecutive months.)_

- **Signup SLO breach + APM silence** — surfaced 2026-05-05, unchanged 2026-05-06 (7+ day SLO Alert, 4+ day APM No Data). Verify resolved by June 2026 report. If unaddressed: escalate to team lead (revenue pipeline impact).
- **8 runtime-core / ms-account-api sub-service APM monitors in No Data** — surfaced 2026-05-05, unchanged. Verify all return to OK or have notify_no_data enabled by June 2026 report.
- **ES 403 blocking triage bot** — surfaced 2026-05-05, unchanged. Verify ES accessible by June 2026 report. If unaddressed: this becomes a two-month blocker and should be escalated to whoever owns the Elastic Cloud deployment.

---

## Appendix: raw queries

```bash
# DD monitors — Alert and No Data in prod
python3 scripts/dd_search.py monitors --tags "env:prod" --state Alert --state "No Data"
# Run: 2026-05-06T13:23:38Z. Result: 21 monitors in Alert or No Data state.

# DD monitors — Alert only (full list)
python3 scripts/dd_search.py monitors --tags "env:prod" --state Alert
# Run: 2026-05-06T13:23:38Z. Result: 44 monitors; most are persistent/historical Alert states.

# DD metric — runtime-core-api error rate, 30-day window
python3 scripts/dd_search.py metric \
  --query "sum:trace.aspnet_core.request.errors{service:runtime-core-api,env:prod}.as_rate()" \
  --from-unix 1775481818 --to-unix 1778073818
# Result: 105 points; max 0.008125/s at 2026-04-27T12:00Z; non-zero throughout; current ~0.001/s.

# DD metric — runtime-core-api hit rate, 30-day window
python3 scripts/dd_search.py metric \
  --query "sum:trace.aspnet_core.request.hits{service:runtime-core-api,env:prod}.as_rate()" \
  --from-unix 1775481818 --to-unix 1778073818
# Result: 165 non-null points; max 117.5/s; avg 30.4/s; May 6 12:00Z = 34.0/s (normal).

# DD metric — Signup hit rate, 30-day window
python3 scripts/dd_search.py metric \
  --query "sum:trace.aspnet.request.hits{service:signup,env:prod}.as_rate()" \
  --from-unix 1775481818 --to-unix 1778073818
# Result: 150 non-null points through 2026-05-01T12:00Z (avg 0.020/s); zero after. Confirmed APM silence.

# ES search (all attempts returned 403)
python3 scripts/es_search.py search --query "level:ERROR" --from "now-30d" --limit 1
# Result: {"error": "es POST .../aws.found.io:443/*/_search -> 403: Host not in allowlist"}

# Jira JQL (read-only) — 3 queries
# 1. ES/triage-bot: project in (NCNG, PL) AND (text ~ "elasticsearch" OR text ~ "ES allowlist" OR text ~ "triage bot") AND resolution = Unresolved AND updated >= -90d
#    Result: 5 "move to serilog" tasks — no ES allowlist or triage-bot ticket.
# 2. Signup: project in (NCNG, PL) AND (text ~ "signup" OR text ~ "sign-up") AND resolution = Unresolved AND updated >= -90d
#    Result: PL-62669 (Invite User error, P1-High, To Do) most relevant; no SLO or APM ticket.
# 3. runtime-core/APM: project in (NCNG, PL) AND (text ~ "runtime-core" OR text ~ "APM" OR text ~ "deploy health" OR text ~ "notify_no_data") AND resolution = Unresolved AND updated >= -90d
#    Result: NCNG-1124 (Action Editor mongo failure, P3-Low); PL-62064 (PermissionsController security, P1-High In Test); no deploy-health or notify_no_data ticket.
```
