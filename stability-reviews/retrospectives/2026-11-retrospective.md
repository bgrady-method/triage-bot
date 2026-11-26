# Method Platform Retrospective — 2025-11 → 2026-11

_Generated: 2026-11-26 · Window: 2025-11-25 → 2026-11-25 (12 months) · Scope: the Method production platform (incidents, alert trends, fixes) and the alert channels that watch it: #alert-system, #alert-frontend-errors, #alert-runtime-monitoring, #swat and #team-incident-response._

> **Sources, in order of weight:**
> 1. The Software Development **post-incident report log** (Confluence SD blog "Post-Incident Report", 39 reports dated in the window).
> 2. The June 2026 **Postmortem Follow-Up & Stability Plan** (Confluence SD).
> 3. The triage KB of platform failure modes: `kb/known-issues.json`, 104 entries, read from `origin/alerting-system-grafana`, where the live data is (see §1).
> 4. The monthly **stability reviews**: Datadog and Elasticsearch error trends.
> 5. Alert history: `kb/incident-log.jsonl`, 7,560 lines.
> 6. A census of the alert channels in **Slack**.
>
> No personal names, customer account names, Slack message text or secrets are reproduced.

---

## Executive summary

- **39 production incidents got a post-incident report this year.** That is about 3 a month, peaking in **April 2026 (10)** and **May (6)**, then 0–4 a month after June. **Four were platform-wide** (sign-in or every screen down):
  - the morning release on 2026-04-25 (~93 min);
  - an ms-account-api deploy on 06-04 (~77 min);
  - legacy auth crypto on 06-16 (~3.5 h);
  - a gateway .NET runtime swap on 08-26 (~1 h 51 m).

  Together that is **~491 min of full outage, ≈ 99.91% availability** for the year. That is just above the 99.9% peer SLA, before counting partial outages.
- **The incidents are mostly self-inflicted.** **23 of 39 (59%) were caused by a change we shipped**: a release, deploy, migration, config change or feature flag. 9 were infrastructure or capacity, 5 third-party or abuse, and 2 latent data or code defects. Release-time breakage is the single biggest problem class, and it was still happening in August and November.
- **Improvements with the biggest impact:**
  1. **Deploy safety after the June postmortems.** A minimum-healthy-target safeguard on every HTTP service deploy, a third preferences node, and an auth cache plus recycle on the public API. There has been no deploy-capacity or auth-crypto recurrence since.
  2. **Internal DNS fixed** (Route 53 1024-PPS throttling, May 2026). There were 4 DNS-caused incidents and none after the May fix.
  3. **The gateway → microservices timeout cluster**, the noisiest platform alert of the summer (778 occurrences), improved from +1,025% to **−59%** by September and has not fired since **2026-09-24**.
  4. **Outbound email screening** (PL-62308) and SendGrid sub-user hardening came after three malicious-tenant suspensions (Feb, Apr, Apr). There has been no suspension since 2026-04-22.
  5. **oauth_token Mongo bloat** (~6 TB, growing ~8 GB/day) was fixed in June with a TTL index.
- **What is still a problem:**
  - **Release safety and late detection.**
    - The HTML-sanitizer release blocked saving and email for **~3 days** (Nov 20–23).
    - Email with attachments was stuck for **26 h** (Aug).
    - TenantId was nulled for **7 days** (Dec).
    - Fallback email was down **6 days** (Feb).
    - Many of these were found by customers, not alerts.
  - **Chronic alerting issues with no fix:**
    - runtime-core RTC p95 latency: 297 occurrences, no Jira;
    - ms-scheduler `recordId = -1`: 156 occurrences, a one-line fix proposed since July;
    - noisy CRM AMQP and notifications monitors;
    - `method-import-subscriber`: ~60–100k errors/30d with no error monitor.
  - **Redis / thread-pool pressure keeps returning.**
  - **Customer communication during incidents** was raised again on the Nov 23 P0.
- **How engaged the alert channels are:**
  - **#alert-runtime-monitoring**: ~433 human messages a year from ~27 people. It went from silent in Dec–Jan to 28–83 a month after its Feb 9 relaunch as a shared, on-duty channel.
  - **#alert-system**: ~528 messages from ~33 people, worked in bursts around incidents and releases.
  - **#alert-frontend-errors**: **1 human message all year**, against ~30–100 alerts a day.
  - Per alert, engagement is low everywhere. Across 39 monthly sample days only **~0.3% of alerts got a human thread reply**. When one did, it came in a median of ~4 min.

---

## 1. Data coverage and gaps

| Source | Coverage | Notes |
|---|---|---|
| Confluence PIR log (SD blog "Post-Incident Report") | **39 incidents** with reports dated 2025-12-10 → 2026-11-20 | One more platform-wide DNS outage (~45 min) sits in the log between 2025-10-06 and 2025-12-10 with no date. It is excluded from the counts. Three in-window entries are undated (a runtime blank screen, a v4-screen load error, Android tablet scrolling) and are placed by their position in the log. |
| Confluence "Postmortem Follow-Up & Stability Plan - June 2026" | the Jun 4 – Jun 16 incidents and their action items | Status as of 2026-06-22. |
| `kb/known-issues.json` (104 entries) | first_seen 2023-11 → 2026-11; 64 entries first seen inside the window | Read from `origin/alerting-system-grafana`. `main` stops at 2026-06-18 because the triage routine has committed to that branch since (Appendix C). |
| Stability reviews `2026-05` → `2026-09` | 30-day windows to 2026-09-01 | Datadog and Elasticsearch error trends per service; none since September (Appendix C). |
| `kb/incident-log.jsonl` (7,560 lines) | 2026-05-01 → 2026-11-25, with a **56-day gap 2026-09-25 → 11-19** | Alert-level trend data. Slack-sourced in May–Jun, Datadog-monitor-sourced after. |
| Slack alert channels | full year | Human-message census plus one sample day per month (§5). |
| Jira | **not usable for trend counts** | This account can see only 57 AS (support) tickets created in the window, while key numbering suggests ~1,200. The PIR log is used instead. |

---

## 2. Incidents this year

### 2.1 The incident log

Dates are 2026 unless marked. "Wide" means sign-in or every screen was down for all customers.

| Date | Incident | Duration | Scope | Root-cause class |
|---|---|---|---|---|
| 2025-12-10 | Mongo migration (banner collections in every account DB) overloaded Mongo; new accounts saw no apps | ~2 h | New accounts | Change: migration |
| 2025-12-15 | REST API developer docs blank: a third-party CDN removed a script | ~2 h | API docs | Third-party |
| 2025-12 (≈ 15–22) | New-signup onboarding failed: a release-notes omission shipped a migration without its service | ~40 min | New signups | Change: release order |
| 2025-12-22 → 12-29 | Entity updates wrote TenantId = null after a query-column change (PL-58920) | **~7 days** | Multi-tenant data | Change: code |
| 01-28 | Release IIS saturation: a 401 burst during single-node rotation gave white screens | ~45 min | Many users | Change: release |
| 01-29 | Grid Builder v2 intermittent failures: a new node was missing from the release definition | 10–15 min | App Builder | Change: deploy config |
| 02-09 | Multi-tenant runtime pages with Call Routine failed after an app-name cache change | ~1.5 h | Tenant accounts | Change: code |
| 02-11 → 02-17 | SendGrid suspended the fallback sub-user after a malicious tenant sent phishing | **~6 days** | Fallback email | Third-party / abuse |
| 02-17 | App ribbon hidden after a manual app-publish config error | ~4 h | One stock app | Change: publish config |
| 03-02 → 03-03 | Intermittent error page from one new release-capacity server (untrusted-domain SQL login) | **~21 h** | Intermittent, all | Infra |
| 03-13 | QBDT real-time sync not triggering: DNS pointed at a misconfigured load-balancer target group | until fixed | QBDT customers | Infra |
| 04-01 | Field Crew empty-state overlay blocked users (feature flag turned off) | ~20 min | One app | Change: flag |
| 04-13 | **Elasticsearch outage**: native OOM on 2 of 3 nodes, no master, all writes failed | **5 h 35 m** | Logging, audit trail | Infra |
| 04-14 → 04-15 | SendGrid suspended the ops sub-user (phishing tenant) | ~11 h | Transactional email | Third-party / abuse |
| 04-17 | Some saves skipped QuickBooks/Xero sync (ServerTimeModified race) | ~8 h | Sync customers | Change: code |
| 04-21 → 04-22 | SendGrid suspended the ops sub-user again (incomplete clean-up of the earlier tenant) | ~10 h | Transactional email | Third-party / abuse |
| 04-25 | **Method down during morning release** (ms-preferences-api security-tag dependency) | **~93 min** | **Wide** | Change: release order |
| 04-26 | Billing subscription pages 500: a refactor removed a second API key | ~27 min | New customers | Change: code |
| 04-27 → 04-28 | Gmail sidebar "bandwidth quota exceeded" (Google-side) | ~30 h | Gmail add-on users | Third-party |
| 04-28 | Platform slowness ×3 from Redis pattern-delete SCAN spikes | 3 episodes | Many users | Infra (code pattern) |
| 04-30 | QBO real-time sync not enqueuing (old MassTransit + tracer) | ~6.5 h | All QBO customers | Infra |
| 05-04 | Classic UI app-pool crashes (EDA NuGet thread starvation) | 5 + 3 min | Classic users | Infra |
| 05-04 | Wrong legacy-sync version deployed; QBDT sync and new-account creation down | ~30 min | Sync, signups | Change: deploy |
| 05-06 | Calendar Sync deploy failed its health check (.NET 4.8 missing on the server) | ~14 min | Calendar sync | Change: deploy |
| 05-14 → | Internal DNS NXDOMAIN for microservices.method.int (Route 53 PPS throttling) | intermittent | Many services | Infra |
| 05-15 | MongoDB rs01 crash: file-descriptor limit after a migration added collections in every tenant DB | ~91 min | Degraded | Change: migration + infra |
| 05-20 | All 11 Windows hosts failed to resolve microservices.method.int | ~30 min | Many services | Infra |
| 06-04 | **Platform-wide outage**: an ms-account-api deploy flooded ms-preferences-api; gateway 502s | **~77 min** | **Wide** | Change: deploy |
| 06-04 | Action Editor lost grid-column references (regression from another fix) | ~2 h | Builders, PS | Change: code |
| 06-16 | Preferences rolling deploy left a single healthy node (near-outage) | until restored | At risk | Change: deploy |
| 06-16 | **Legacy auth 500s (crypto handle bug under API load): nobody could sign in** | **~3.5 h** | **Wide** | Infra (latent code under load) |
| 07-23 | Billing receipts blocked: the sender field pointed at a former employee | ~2 h | Billing receipts | Latent data |
| Jul–Aug (undated) | Runtime blank screen: new build assets used the wrong caching strategy | ~30 min | All sign-ins | Change: build |
| Jul–Aug (undated) | v4 stock screens errored: UI, App Builder and migration dependencies out of order | ~30 min | v4 screens | Change: release order |
| 08-06 → 08-10 | Unfinished Banner control shipped to prod via branch / squash-merge hygiene (P0) | up to ~4 days | App Builder | Change: code |
| 08-17 → 08-18 | Emails with attachments stuck in Processing (legacy S3 bucket/key convention) | **~26 h** | 44 accounts, 1,058 emails | Latent code |
| 08-26 | **Gateway down on both hosts**: an under-pressure .NET 10 install replaced the .NET 9 runtime | **~1 h 51 m** | **Wide** | Change: ops |
| Sep–Nov (undated) | Android tablets could not scroll runtime pages (a Kanban CSS rule on the shared container) | ~2.5 h | Android tablet users | Change: code |
| 11-20 → 11-23 | HTML-editor sanitizer release blocked saving HTML and sending email (P0) | **~3 days** | Several accounts | Change: release |

### 2.2 Trend

| Month | 2025-12 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09–10 | 11 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PIRs (dated) | 4 | 2 | 3 | 2 | **10** | 6 | 4 | 1 | 3 | 0 | 1 |
| of which platform-wide | 0 | 0 | 0 | 0 | 1 | 0 | 2 | 0 | 1 | 0 | 0 |

The three undated PIRs (Jul–Aug ×2, Sep–Nov ×1) are not in the monthly counts.

| Root-cause class | Count | Share | Examples |
|---|---:|---:|---|
| **Change we shipped** (release order, deploy, migration, config, flag, code) | **23** | **59%** | 04-25, 06-04 ×2, 06-16 deploy, 08-26, 11-20 |
| Infrastructure / capacity | 9 | 23% | ES OOM, DNS ×3, Redis SCAN, auth crypto under load |
| Third-party / abuse | 5 | 13% | SendGrid ×3, Google, CDN |
| Latent data / code defect | 2 | 5% | billing sender, S3 key convention |

**Durations.** The median incident lasted about **2 h**. The long tail is silent failures that ran for days before anyone connected them to a cause: TenantId 7 d, fallback email 6 d, unfinished Banner control on prod ~4 d, sanitizer 3 d, attachments 26 h, intermittent error page 21 h.

**Availability.** The four platform-wide outages total ~491 min. A year has 525,600 min, so availability is **≈ 99.91%** (`references/methodology/metrics-formulas.md`). That clears the 99.9% three-nines peer SLA (Salesforce, HubSpot, QBO, Zoho) by a margin of about one more 1-hour outage. Partial outages are not counted: QBO sync 6.5 h, ES 5.5 h, intermittent error page 21 h.

---

## 3. Platform changes and their impact (ranked)

| # | Change | When | Metric | Before | After | Evidence |
|---:|---|---|---|---|---|---|
| 1 | **Deploy safety after the June postmortems.** Refuse to pull a node when fewer than 2 targets are healthy (all HTTP services), a third preferences node, a 2-min auth cache on the public API, and a periodic app-pool recycle on legacy auth. | Jun 2026 | Deploy-capacity and auth-crypto incidents | 3 in Jun 4–16 (two near or full outages) | 0 recurrences in 5 months | Confluence stability plan; PIR log |
| 2 | **Internal DNS fix**: stop forwarding `.method.int` to the Route 53 link-local resolver past its 1024-PPS limit | May 2026 | DNS-caused incidents | 4 (one just before the window, Mar 13, May 14, May 20), incl. one platform-wide | 0 after May 20 | PIR log; KB DNS entry (2026-05-14) |
| 3 | **Gateway → microservices timeout cluster** worked down: the 06-05 rollback, then the follow-ups | Jun → Sep | ES error trend; KB occurrences | +1,025.7% (Jul review), 50–80 fires a week | −59.0% (Sep review); no fire since 2026-09-24 | `stability-reviews/2026-08/2026-08-04-report.md`, `2026-09/2026-09-01-report.md` (on `alerting-system-grafana`); `ki-2026-05-21` |
| 4 | **Outbound email screening** (PL-62308; held-for-review queue), sub-user rerouting, malicious-tenant clean-up | Apr → Sep | SendGrid suspensions | 3 in Feb–Apr (6 d, 11 h, 10 h of email impact) | 0 since 2026-04-22; screening posts in #alert-runtime-monitoring from Sep | PIR log; Slack |
| 5 | **oauth_token Mongo bloat**: expired tokens purged, TTL auto-delete index | 2026-06-03 | DB size / backup warnings | ~6 TB, +~8 GB/day, daily backup warning | no recurrence | `stability-reviews/2026-06/2026-06-10-report.md` F1; `ki-oauth-token-db-bloat` |
| 6 | **#alert-runtime-monitoring relaunch** as the shared CRM + Vertical-Apps monitoring channel | 2026-02-09 | Human messages / month | 0 (Dec, Jan) | 28–83 / month (Feb–Sep); threads end in tickets and threshold fixes | §5.2 |
| 7 | **Monitor tuning by teams**: TFS health-check noise excluded, mobile RUM self-noise fixed (PL-64578/79/80), SMS volume thresholds rebased, CRM monitors re-thresholded | Jul → Nov | Known-noise alerts | QA No-Data synthetics: 175 + 44 + 13 fires | grid-dropdown, warehouse and release synthetics silent since Aug 6–12 | KB last_seen; Slack threads |
| 8 | **ES capacity work** after the April outage; Redis and syncservice timeout changes | Jan → Apr | ES outages | 1 (5 h 35 m) | 0 since | PIR log |

What has not changed: **release-time defects**. The share of incidents caused by a change did not fall after June: **16 of 29 (55%)** before 2026-06-16 and **7 of 10 (70%)** from then on, counting the undated PIRs by their place in the log. The June safeguards stopped *capacity* failures during deploys. They did not stop bad code or bad ordering reaching production.

---

## 4. What continues to be a problem

### 4.1 Release safety and silent failures

- **Change-induced incidents are 59% of the year** and keep coming: Aug 6 (Banner control via branch hygiene), Aug 26 (runtime swap under pressure), Nov 20 (sanitizer).
- Three recurring sub-patterns:
  - **Release-order / dependency** problems: Dec signup, Apr 25 outage, v4 screens.
  - **Migrations run against every tenant DB**: Dec 10 Mongo load, May 15 Mongo FD exhaustion.
  - **Fixes that break a neighbour**: Jun 4 Action Editor, Apr 26 billing key, Apr 17 sync race.
- **Detection is late for silent failures.** The longest incidents were found by customers, not alerts: TenantId (7 d), fallback email (6 d), sanitizer (3 d), attachments (26 h), intermittent error page (21 h). The June plan's "detect every incident within minutes" goal and the deep auth health check were still marked in progress on 2026-06-22.
- **Flags are the fastest recovery when they exist.** Field Crew was turned off in ~20 min; the sanitizer flag was eventually turned off, after 3 days.

### 4.2 Chronic alerting issues (open, still firing)

| KB entry | Lifetime occurrences | fix_status | Last seen | Gap |
|---|---:|---|---|---|
| runtime-core RTC Screen Load / Action Execution p95 (`ki-2026-05-24`) | 297 | investigating | 2026-11-25 | No Jira. A new correlate on 11-24: paged rest-api queries saturating one SQL host. |
| CRM AMQP consumer quiet-period flap (`ki-2026-07-04`) | 205 | noise, unconfirmed | 2026-11-25 | Threshold change recommended twice; not done. |
| ms-scheduler-api `recordId = -1` (`ki-2026-07-03`) | 156 | proposed | 2026-11-24 | A one-line guard, top ICE (54) in two reviews; unfiled for 20 weeks. |
| EDA consumer stopped publishing (`ki-2026-07-03-eda…`) | 73 | escalated-for-review | 2026-11-20 | No decision recorded. |
| notifications p95 monitor noise (`ki-2026-07-07`) | 53 | noise, unconfirmed | 2026-11-25 | Tripped by the daily batch. |
| tables-fields linked-field NRE / view-regen failures (`ki-2026-05-28…`, `ki-2026-07-28…`) | 20 + 9 | needs-human | 2026-11-20/25 | Single-tenant metadata corruption that blocks customers' table edits. |
| *(no KB entry)* Twilio bulk-SMS callbacks starve the mobile-notifications thread pool | 5 fires 11-17 → 11-24 | — | 2026-11-24 | A sync Redis `Get` on the request thread; defect proposed. |
| **Unmonitored error streams**: `method-import-subscriber` and 13 other services | 62,794 errors/30d (Sep) | — | — | No error-rate monitor (`2026-09-01-report.md` F3). |

### 4.3 Recurring infrastructure pressure

- **Redis / Valkey and thread pools**: Apr 28 SCAN slowness, the RTC p95 chronic issue, Nov mobile-notifications thread-pool starvation, and Nov Valkey egress shaping (triage notes 2026-11-21).
- **MSL hosts**: audit-trail and import subscribers drive CPU alerts all year. Upsizing was discussed in March, and a memory-exhaustion episode was logged on 2026-11-19.
- **Third-party exposure**: SendGrid, Google and the CDN together caused 5 incidents. Rainforest payment latency/503 monitors fired 26 + 25 times in Jul–Aug.

### 4.4 Follow-through and communication

- **Zero of the top-5 stability-review recommendations shipped** in July, August or September (`2026-08-04-report.md`, `2026-09-01-report.md` trackers).
- On the Nov 23 P0, support asked in #swat for customer communication and impact counts; affected accounts could not be fully counted. Status-page and incident comms were not part of the June plan.

### 4.5 Alert noise and volume

- **Repeat notifications**: on 2026-11-23 one Centreon disk warning was posted 34 times in 5.7 h before a one-message fix.
- **#alert-frontend-errors** ran ~30–100 alerts a day (Dec–Sep sample days) with no human readers. It fell to 10 on 2026-11-03 (§5.3).

---

## 5. Alert-channel engagement

### How each column is measured

Each channel gets one row per month. Two kinds of measurement are mixed, and the column headers say which is which.

- **Census columns** (every message in the month):
  - *Human messages*: Slack search with `include_bots: false`, paged to the end. Thread replies included.
  - *Distinct responders*: the distinct human author IDs among those messages.
  - *Incident-log alert rows*: from `kb/incident-log.jsonl`. Only May–Jun 2026 are Slack-sourced and comparable (§1).
- **Sample-day columns** (one fixed day per month, the first Tuesday; 2025-11 uses 2025-11-25, the first Tuesday in the window):
  - *Alerts*: bot or integration messages from `slack_read_channel`. "100+" means the page cap was hit.
  - *Touched*: alerts from that day with a human thread reply, from `is:thread on:<day>` with bots included.
  - *% touched*: touched ÷ alerts.
  - *First reply*: time from the alert to its first human reply.
- **Reactions** cannot be searched per bot message. They were only counted on the detailed-mode sample days in §5.4, where they add at most one alert per day.

2025-11 = 11-25 → 11-30; 2026-11 = 11-01 → 11-25. Monthly alert volume is not censused, because a full read of a year of alerts is too large. A single day per month is an indicator, not a monthly total.

### 5.1 #alert-system (`CPHHABKAA`)

| Month | Human messages | Distinct responders | Incident-log alert rows | Sample day | Alerts (sample day) | Touched | % touched | First human reply |
|---|---:|---:|---:|---|---:|---:|---:|---|
| 2025-11 | 9 | 3 | — | 11-25 | 32 | 1 | 3% | 4 m (plus a top-level message asking who was investigating, 4 m into a Centreon storm) |
| 2025-12 | 34 | 10 | — | 12-02 | 22 | 0 | 0% | — |
| 2026-01 | ~100 | 15 | — | 01-06 | 21 | 1 | 5% | 3 m |
| 2026-02 | 52 | 13 | — | 02-03 | 11 | 0 | 0% | — |
| 2026-03 | ~59 | 13 | — | 03-03 | 21 | 0 | 0% | — |
| 2026-04 | 36 | 9 | — | 04-07 | 8 | 0 | 0% | — |
| 2026-05 | 29 | 8 | 576 | 05-05 | 21 | 0 | 0% | — |
| 2026-06 | 59 | 9 | 654 | 06-02 | 41 | 0 | 0% | — |
| 2026-07 | 14 | 7 | (DD-sourced) | 07-07 | 37 | 0 | 0% | — |
| 2026-08 | 12 | 5 | (DD-sourced) | 08-04 | 22 | 0 | 0% | — |
| 2026-09 | 74 | 11 | (DD-sourced) | 09-01 | 9 | 1 | 11% | 33 m |
| 2026-10 | 14 | 8 | (tooling down) | 10-06 | ~100 | 0 | 0% | — |
| 2026-11 | 36 | 15 | (DD-sourced) | 11-03 | 7 | 0 | 0% | — (one thread reply that day was on an earlier alert) |
| **12 months** | **~528** | **~33** | | | **352** | **3** | **0.9%** | median ≈ 4 m when touched |

### 5.2 #alert-runtime-monitoring (`C063V5HTTFU`)

| Month | Human messages | Distinct responders | Incident-log alert rows | Sample day | Alerts (sample day) | Touched | % touched | First human reply |
|---|---:|---:|---:|---|---:|---:|---:|---|
| 2025-11 | 7 | 2 | — | 11-25 | 7 | 0 | 0% | — |
| 2025-12 | 0 | 0 | — | 12-02 | 4 | 0 | 0% | — |
| 2026-01 | 0 | 0 | — | 01-06 | 7 | 0 | 0% | — |
| 2026-02 | 65 | 10 | — | 02-03 | 1 | 0 | 0% | — (channel relaunched 02-09) |
| 2026-03 | 43 | 8 | — | 03-03 | 10 | 0 | 0% | — |
| 2026-04 | 28 | 7 | — | 04-07 | 100+ (one app-update error burst) | 0 | 0% | top-level human message ~10 m after the burst |
| 2026-05 | 45 | 8 | 357 | 05-05 | 100+ | 0 | 0% | — |
| 2026-06 | 52 | 8 | 213 | 06-02 | 29 | 0 | 0% | top-level human message ~3 m after an alert |
| 2026-07 | 83 | 14 | (DD-sourced) | 07-07 | 38 | 0 | 0% | — |
| 2026-08 | 39 | 9 | (DD-sourced) | 08-04 | 32 | 0 | 0% | — |
| 2026-09 | 54 | 11 | (DD-sourced) | 09-01 | 43 | 0 | 0% | — |
| 2026-10 | 10 | 4 | (tooling down) | 10-06 | 58 | 0 | 0% | — |
| 2026-11 | 7 | 5 | (DD-sourced) | 11-03 | 53 | 1 | 2% | 24 m |
| **12 months** | **~433** | **~27** | | | **482+** | **1** | **≤0.2%** | 24 m (n = 1) |

### 5.3 #alert-frontend-errors (`C03TYHGRS23`)

| Month | Human messages | Distinct responders | Incident-log alert rows | Sample day | Alerts (sample day) | Touched | % touched | First human reply |
|---|---:|---:|---:|---|---:|---:|---:|---|
| 2025-11 | 0 | 0 | — | 11-25 | 28 | 0 | 0% | — |
| 2025-12 | 0 | 0 | — | 12-02 | 46 | 0 | 0% | — |
| 2026-01 | 0 | 0 | — | 01-06 | 52 | 0 | 0% | — |
| 2026-02 | 0 | 0 | — | 02-03 | 72 | 0 | 0% | — |
| 2026-03 | 0 | 0 | — | 03-03 | 100+ | 0 | 0% | — |
| 2026-04 | 0 | 0 | — | 04-07 | 60 | 0 | 0% | — |
| 2026-05 | 1 | 1 | 898 | 05-05 | 76 | 0 | 0% | — |
| 2026-06 | 0 | 0 | 850 | 06-02 | 37 | 0 | 0% | — |
| 2026-07 | 0 | 0 | (DD-sourced) | 07-07 | 36 | 0 | 0% | — |
| 2026-08 | 0 | 0 | (DD-sourced) | 08-04 | 65 | 0 | 0% | — |
| 2026-09 | 0 | 0 | (DD-sourced) | 09-01 | 73 | 0 | 0% | — |
| 2026-10 | 0 | 0 | (tooling down) | 10-06 | 48 | 0 | 0% | — |
| 2026-11 | 0 | 0 | (DD-sourced) | 11-03 | 10 | 0 | 0% | — |
| **12 months** | **1** | **1** | | | **703+** | **0** | **0%** | never |

Because this channel had one human message all year, every month's touch rate is 0% from the census alone; the sample days only add volume. Sample-day volume fell from 46–100+ a day (Dec–May) to **10 on 2026-11-03** (and 21 on 2026-11-23). That is the first sustained drop, but nobody watches what is left.

### 5.4 Human messages per 100 alerts, and detailed-mode samples

May–Jun 2026 only, where incident-log alert rows are Slack-sourced.

| Channel | Month | Alert rows | Human messages | Human msgs per 100 alerts |
|---|---|---:|---:|---:|
| #alert-system | 2026-05 | 576 | 29 | 5.0 |
| #alert-system | 2026-06 | 654 | 59 | 9.0 |
| #alert-runtime-monitoring | 2026-05 | 357 | 45 | 12.6 |
| #alert-runtime-monitoring | 2026-06 | 213 | 52 | 24.4 |
| #alert-frontend-errors | 2026-05 | 898 | 1 | 0.1 |
| #alert-frontend-errors | 2026-06 | 850 | 0 | 0.0 |

Additional samples read in detailed mode (thread and reaction metadata):

| Sample | Alert messages | With a human thread or reaction | % touched | Time to first human response |
|---|---:|---:|---:|---|
| #alert-system, 2025-11-03 (weekday) | 13 | 0 threads (one Centreon alert acknowledged in the Centreon tool) | 0% | Centreon ack in ~25 s; no Slack reply |
| #alert-runtime-monitoring, 2026-09-24 (an above-average day) | 34 | 2 threads (2 and 9 replies) + 1 reaction | ~6–9% | ~1 h and ~3.5 h for the two threaded alerts |
| #alert-system, 2026-11-23 (recent weekday) | 58 | 1 top-level human message | ~2% | 5 h 42 m after the first of 34 repeated disk warnings |

### #swat and #team-incident-response

#swat is an incident channel worked by humans: 20+ human messages in 11-21 → 11-23 alone, around one P0. It was not censused month by month. #team-incident-response is not visible to public search, so it is not measured here.

### 5.5 Commentary

- **#alert-runtime-monitoring is the success story**, and the cause was a process change, not tooling. The 2026-02-09 relaunch gave it named on-duty teams and an emote convention. It went from silent to the most conversational alert channel. Threads there routinely end in a ticket, a threshold change or a "known noise" verdict. The October–November dip (10 and 7) needs watching: it coincides with fewer new monitors and no channel-level change.
- **#alert-system is worked, but in bursts.** It peaks during incidents and releases (Jan ≈ 100 around app-update and EDA issues; Sep 74 around the tags-queue incident) and goes quiet otherwise (Jul–Aug and Oct ≈ 12–14). Most messages are ops actions (restarts, recycles, purges) and questions about whether a release caused an alert, not alert-by-alert acknowledgement. Repeat notifications drown the signal.
- **#alert-frontend-errors is effectively unwatched.** It had about 900 alerts a month in May–June, ~1,500 a month extrapolated from the Nov 2025 sample, and one human message all year. Its monitor (77419271, browser XHR errors) is also the single largest source of new false-alarm entries in Nov 2026 (single-session client network drops).
- **#swat is human-driven and healthy.** Incident channels are not the engagement problem.
- **Concentration risk.** Roughly a third of #alert-runtime-monitoring messages come from one person, and a large share of those are prompts asking a team whether anyone is investigating. Engagement depends on that one person prompting.
- **Effect of automated triage on channel engagement.** The triage routine posts its findings outside the alert channels: to the operator by DM through June, then to #triage-results. It therefore could not change in-channel behaviour, and whether its analysis reaches the owning teams is **unmeasured** (Appendix C).

---

## 6. Recommendations (ICE-scored per `references/methodology/recommendation-rubric.md`)

| # | Recommendation | Impact | Confidence | Effort | ICE | Why |
|---:|---|---:|---:|---:|---:|---|
| 1 | **Ship the ms-scheduler-api `recordId <= 0` guard** (carry-forward) | 6 | 9 | 1 | **54.0** | 156 alert fires, a one-line fix, the top item in two reviews (§4.2) |
| 2 | **Give #alert-frontend-errors an owner, or retire it.** Route monitor 77419271 to the owning team with the same on-duty convention that revived #alert-runtime-monitoring, or downgrade it to a daily digest. | 7 | 8 | 2 | **28.0** | 1 human message a year against ~30–100 alerts a day (§5.3); the runtime-monitoring relaunch shows the convention works (§3 #6) |
| 3 | **Synthetic deep checks for the silent-failure paths**: sign-in including the legacy-auth encrypt path, send an email with an attachment, an accounting-sync enqueue, a tenant entity save round-trip | 8 | 8 | 3 | **21.3** | The longest incidents (7 d, 6 d, 3 d, 26 h, 21 h) were silent and customer-found (§4.1); the June plan already names a deep auth health check |
| 4 | **Ship risky user-facing changes behind a flag by default**, with a documented kill switch in the release notes | 7 | 8 | 3 | **18.7** | Field Crew recovered in 20 min by flag; the sanitizer took 3 days. 23 of 39 incidents were change-induced (§2.2). |
| 5 | **Incident comms playbook**: a status-page update within 30 min of a P0 and an affected-account query template | 5 | 7 | 2 | **17.5** | Raised by support on the Nov 23 P0 (§4.4) |
| 6 | **Error-rate monitors for the silent burners** (`method-import-subscriber` and the 13 other services found in the Sep review) | 5 | 10 | 3 | **16.7** | ~63k errors/30d with 0% monitor coverage (§4.2) |
| 7 | **Release-dependency gate**: a release cannot go out unless its declared service, migration and UI dependencies ship together. Run tenant-wide migrations throttled, with an FD/connection budget. | 9 | 6 | 4 | **13.5** | Release order caused the 04-25 outage, the Dec signup failure and v4 screens; migrations caused 12-10 and 05-15 (§4.1) |
| 8 | **File and own the RTC p95 / Redis thread-pool work**: async cache reads in mobile-notifications, a rest-api paging limit on the hot SQL host | 7 | 6 | 4 | **10.5** | 297 occurrences, plus the recurring Redis/thread-pool pressure (§4.3) |

---

## Appendix A — script output

Command:

```
python scripts/retro_stats.py --ref origin/alerting-system-grafana --as-of 2026-11-25 --top-kb 12
```

(Run with the `--ref` flag because the live data is on that branch; see §1 and Appendix C. Weeks W40–W46 are absent because there are no rows during the outage.)

```
Lines parsed: 7560 (skipped 0); span 2026-05-01 19:24Z -> 2026-11-25 21:08Z

Classification totals: grouped 2964, known-issue-recurrence 1676, poll-cycle 1213, needs-human 833,
false-alarm 452, heartbeat 378, deduplicated 20, stability-review 9, weekly-digest 9,
new-with-clear-fix 4, manual-catchup 1, operational-notice-followup 1
```

| Week | Alert rows | Needs-human | KIR | KIR share | Surfaced (DM/post) | Suppressed | Cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-W18 | 71 | 66 | 0 | 0% | 66 | 0 | 2.70 |
| 2026-W19 | 313 | 91 | 0 | 0% | 91 | 0 | 6.93 |
| 2026-W20 | 318 | 71 | 0 | 0% | 70 | 0 | 0.81 |
| 2026-W21 | 812 | 132 | 24 | 15% | 109 | 40 | 4.63 |
| 2026-W22 | 364 | 31 | 99 | 76% | 21 | 109 | 0.48 |
| 2026-W23 | 545 | 40 | 93 | 69% | 25 | 109 | 0.81 |
| 2026-W24 | 564 | 27 | 135 | 83% | 25 | 137 | 1.19 |
| 2026-W25 | 609 | 19 | 105 | 83% | 20 | 107 | 1.92 |
| 2026-W26 | 60 | 11 | 27 | 71% | 12 | 26 | 0.96 |
| 2026-W27 | 221 | 56 | 89 | 61% | 30 | 114 | 8.97 |
| 2026-W28 | 413 | 46 | 272 | 72% | 130 | 218 | 23.60 |
| 2026-W29 | 88 | 4 | 65 | 83% | 36 | 36 | 3.10 |
| 2026-W30 | 236 | 18 | 122 | 59% | 77 | 83 | 12.29 |
| 2026-W31 | 315 | 34 | 164 | 57% | 160 | 118 | 13.19 |
| 2026-W32 | 217 | 30 | 112 | 55% | 86 | 88 | 19.04 |
| 2026-W33 | 110 | 14 | 76 | 72% | 45 | 56 | 12.69 |
| 2026-W34 | 82 | 10 | 62 | 77% | 28 | 50 | 8.13 |
| 2026-W35 | 124 | 30 | 78 | 63% | 41 | 80 | 14.78 |
| 2026-W36 | 67 | 19 | 34 | 52% | 24 | 35 | 9.95 |
| 2026-W37 | 9 | 3 | 1 | 12% | 5 | 3 | 0.20 |
| 2026-W38 | 46 | 10 | 25 | 57% | 25 | 19 | 1.37 |
| 2026-W39 | 67 | 16 | 33 | 49% | 26 | 33 | 2.89 |
| 2026-W47 | 199 | 42 | 38 | 30% | 20 | 73 | 7.00 |
| 2026-W48 | 110 | 13 | 22 | 31% | 14 | 21 | 13.75 |

Alert rows per channel per month (same data, grouped monthly; **May–Jun are Slack-sourced, later months mostly DD-sourced**):

| Channel | 2026-05 | 06 | 07 | 08 | 09 | 11 |
|---|---:|---:|---:|---:|---:|---:|
| alert-system | 576 | 654 | 1,084 | 341 | 44 | 68 |
| alert-frontend-errors | 898 | 850 | 89 | 142 | 28 | 43 |
| alert-runtime-monitoring | 357 | 213 | 15 | 126 | 80 | 177 |
| swat | 47 | 43 | 0 | 0 | 0 | 0 |
| team-incident-response | 0 | 14 | 24 | 0 | 0 | 0 |

Top KB entries by KIR rows (totals; weekly split in the script output): gateway-microservices-timeout 543 · runtime-core RTC p95 263 · CRM AMQP quiet-period flap 193 · grid-dropdown QA no-data 139 · EDA consumer stopped publishing 68 · notifications p95 noise 50 · ms-account-api 4xx noise 49 · synthetics sign-in transient 34 · getaccountbysubdomain NRE 32 · ms-scheduler seriesId 30 · warehouse dashboard no-data 29 · runtime-core Redis cache-timeout burst 26.

KB timeline: 104 entries, 44 resolved/mitigated, 60 open (`fix_status` breakdown: resolved 34, needs-human 27, mitigated 10, monitoring-noise-suspected-unconfirmed 7, in-progress 6, proposed 5, others ≤ 3 each).

## Appendix B — methodology

- **Incidents.** Confluence SD blog "Post-Incident Report" (page 133496969, version 80, read 2026-11-26): every entry above the 2025-06-16 heading, filtered to the window by its stated duration or date. Durations and root-cause classes are taken from the "Duration" and "Root Cause" fields; the class labels are this report's. Plus "Postmortem Follow-Up & Stability Plan - June 2026" (page 1049427980) for the June action items.
- **Jira.** `project = "AS" AND created >= "2025-11-25"` returned 57 visible issues, too few to use for trends (§1).

- **Repo data.** `git fetch origin`; `git log --format='%ad|%h|%s'` on `origin/main` and on `origin/main..origin/alerting-system-grafana`, excluding per-cycle commits. `scripts/retro_stats.py` (JSON-parses every line; ISO and epoch `ts`), as in appendix A. Stability reviews read: `2026-06-10`, `2026-08-04`, `2026-09-01` (Executive Summary and trackers).
- **Slack human activity.** `slack_search_public` with `filters: in:<#channel> after:2025-11-24 [before:…]`, `include_bots: false`, `sort: timestamp`, paged to the end. Each result was tallied by month and distinct author ID; the 20-page cap was handled by re-querying with `before:`. Channels: `CPHHABKAA` (#alert-system), `C063V5HTTFU` (#alert-runtime-monitoring), `C03TYHGRS23` (#alert-frontend-errors), `C01L5K42GQ6` (#swat, last month only), `C0B6233UN4S` (#team-incident-response, no public results), `C0B0Q3KHC07` (#triage-results, no human results).
- **Slack samples.** `slack_read_channel`:
  - concise mode for volume: per month, the first Tuesday (2025-11-25, 12-02, 2026-01-06, 02-03, 03-03, 04-07, 05-05, 06-02, 07-07, 08-04, 09-01, 10-06, 11-03) for all three alert channels, using `oldest`/`latest` set to that day in US Eastern time; also #alert-system and #alert-frontend-errors on 2025-11-03 and 2026-11-23;
  - `slack_search_public` with `filters: in:<#channel> is:thread on:<sample day>` and `include_bots: true` for alert threads and human first-reply times on those days (skipped where the human-message census shows no human message that day);
  - detailed mode for thread and reaction metadata: #alert-system 2025-11-03, #alert-runtime-monitoring 2026-09-24;
  - the latest #triage-results posts for bot liveness.
- **Read-only.** No Slack posts, Jira writes or KB edits were made for this report.

## Appendix C — the alert-triage tooling (context for the data above)

Most of the alert-level numbers in this report come from the triage routine in this repo. Its own health limits what they can show, so it is summarised here.

- **Where the data lives.** Since 2026-06-18 the routine has committed to `origin/alerting-system-grafana` (1,380 commits ahead of `main`), not `main`. Every stability review since 2026-07-07 notes this.
- **Coverage gaps.**
  - The routine was **dark for 56 days** (2026-09-25 → 2026-11-19), with no poll and no heartbeat. There were also 4–8 day gaps in late June and mid-July.
  - Slack read access has been missing since ~2026-06-18. Since then it reads Datadog monitors only, so Centreon, Grafana and Logstash-ML alerts are not in the incident log after June.
  - Atlassian access has been unauthenticated for 4+ reviews, so no PIR sync and no Jira cross-reference.
- **What it changed for alert handling (weekly, from Appendix A):**
  - Root-cause grouping (05-04) folded 5,960 alert rows into 2,976 groups.
  - Known-issue suppression and impact-scored escalation (05-21/22) cut needs-human groups from 66–132 a week to 19–40, and human-facing posts from ~91–109 a week to ~20–25.
  - The known-issue share of classified groups went from 0% to 69–88%.
  - A false-alarm KB (from July) absorbed 452 classifications.
- **Tooling recommendations** (outside the platform ranking above):
  - an external dead-man's switch on the routine (no poll in more than 6 h → alert a human);
  - merge `alerting-system-grafana` into `main`;
  - restore Slack read access.
- **Scripts.** `scripts/retro_stats.py` produces Appendix A. `--ref <branch>` reads the KB and log straight from a git ref.

