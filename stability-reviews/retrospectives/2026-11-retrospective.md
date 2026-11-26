# Alerting & Triage Retrospective — 2025-11 → 2026-11

_Generated: 2026-11-25 · Window: 2025-11-25 → 2026-11-25 (12 months) · Scope: the three alert channels (#alert-system, #alert-frontend-errors, #alert-runtime-monitoring), the two incident channels (#swat, #team-incident-response) and the triage-bot that watches them._

> **Where the data lives.** `main` stops on **2026-06-18**. The routine kept running after that, but its commits land on **`origin/alerting-system-grafana`**: 1,380 commits ahead of `main`, current to today. This report reads the triage data (`kb/incident-log.jsonl`, 7,560 lines; `kb/known-issues.json`, 104 entries; `kb/false-alarms.json`, 49 entries; `stability-reviews/2026-0[5-9]/`) from that branch through `git show`, not from this branch's working tree. See [Data coverage](#1-data-coverage-and-gaps).

---

## Executive summary

- **Biggest improvement: the known-issue KB plus suppression and impact-scored escalation (2026-05-21/22).** Needs-human groups fell from **66–132 a week** (W18–W21) to **19–40 a week** (W22–W25). Human-facing posts fell from **~91–109 a week to ~20–25 a week** (≈ −75%). The known-issue-recurrence (KIR) share of classified groups rose from **0% to 69–88%**. Root-cause grouping (2026-05-04) folds **5,960 alert rows into 2,976 groups** (−50%). A false-alarm KB (from July) absorbs another **452 classifications**.
- **Biggest platform wins the bot helped drive:**
  - **oauth_token Mongo bloat** was fixed on 2026-06-03: expired tokens removed, auto-delete index added. It has not recurred.
  - **The gateway → microservices timeout cluster** (`ki-2026-05-21`, 778 lifetime occurrences) went from an ES error trend of **+1,025% → +42% → −59%** (Jul → Aug → Sep reviews). It has not fired since **2026-09-24** (61 days).
  - **#alert-runtime-monitoring was relaunched** as a shared monitoring channel on 2026-02-09. Human activity went from **0 messages a month (Dec–Jan) to 28–83 a month (Feb–Sep)**, and the channel's own threads produced dozens of monitor-threshold fixes and tickets.
- **What is still a problem:**
  - **Chronic, unfixed known issues:**
    - runtime-core RTC p95 latency (`ki-2026-05-24`, **297** occurrences, no Jira);
    - ms-scheduler-api `recordId = -1` (`ki-2026-07-03`, **156** occurrences, a one-line fix proposed since July and still unfiled);
    - the CRM AMQP quiet-period monitor flap (**205**, the threshold is still unchanged);
    - the notifications p95 monitor noise (**53**).
  - **Zero of the top-5 stability-review recommendations shipped** in July, August or September.
- **The bot itself is the second-biggest reliability problem.**
  - It was **dark for 56 days** (2026-09-25 → 2026-11-19), with no heartbeat and no alert to anyone, plus shorter gaps in late June and mid-July.
  - **Slack read access has been gone since ~2026-06-18.** Since then it runs in "degraded" mode from the Datadog monitor list, so it cannot see Centreon, Grafana or Logstash-ML alerts and cannot reply in alert threads.
  - Atlassian access has been unauthenticated for 4+ consecutive reviews.
  - `main` is 5 months stale.
- **Engagement is uneven:**
  - **#alert-runtime-monitoring**: ~433 human messages a year from ~27 people. It is the healthiest channel.
  - **#alert-system**: ~528 messages from ~33 people. Healthy but bursty: Jan ≈ 100, Jul–Aug and Oct ≈ 12–14 a month.
  - **#alert-frontend-errors**: **1 human message in 12 months**, against roughly 1,500 alerts a month at the start of the window. It is effectively unwatched.
  - Per-alert engagement is low everywhere. Across 39 monthly sample days (one per channel per month), only **4 of ~1,540 alerts (~0.3%) got a human thread reply**. When one did, the reply came in a median of ~4 minutes. A busy runtime-monitoring day reached ~6% touched. A sampled ordinary day had a disk warning re-posted **34 times over 5.7 h** before anyone acted.
  - Engagement is also concentrated: one person accounts for roughly a third of runtime-monitoring messages, mostly prompting a team to look.

---

## 1. Data coverage and gaps

| Era | Dates | Repo triage data | Slack data | Notes |
|---|---|---|---|---|
| (a) Pre-bot baseline | 2025-11-25 → 2026-04-30 | none | human-message search, two single-day volume samples | The KB has 5 PIR-seeded entries dated before May. |
| (b) Bot era on `main` | 2026-05-01 → 2026-06-18 | `main` and `alerting-system-grafana` (identical up to `b4805a14`) | as above | Slack-sourced polling: alert rows ≈ Slack alert messages. |
| (c) Bot era on `alerting-system-grafana` | 2026-06-19 → 2026-09-24 | `alerting-system-grafana` only | as above | Mostly **degraded** (Datadog-sourced) cycles: alert rows = DD monitor transitions, not Slack messages. |
| (d) Bot outage | 2026-09-25 → 2026-11-19 | **no rows at all** (no poll, no heartbeat) | as above | The catch-up cycle on 2026-11-19 logged a "56-day gap … cron/host likely down". |
| (e) Bot resumed | 2026-11-19 → 2026-11-25 | `alerting-system-grafana` only | as above | Degraded mode (no Slack MCP, Atlassian unauthenticated). |

**Bot-liveness finding.** The bot is running today: #triage-results (`C0B0Q3KHC07`) has posts from 2026-11-24 and 2026-11-25. It is not committing to `main`. Every stability review since 2026-07-07 notes that the live branch is `alerting-system-grafana` and that `routines/*.yaml` (`push_branches: ["main"]`) is stale. Gaps longer than 36 h in `kb/incident-log.jsonl`:

- 2026-05-07 → 05-13 (6 d)
- 2026-06-20 → 06-24 (4 d)
- 2026-06-26 → 07-02 (6 d; the "manual outage catch-up" commit `ebfb6fc3`)
- 2026-07-15 → 07-23 (8 d)
- 2026-09-06 → 09-09 (3.5 d)
- **2026-09-25 → 2026-11-19 (55.7 d)**

**Approximation caveats.**

- **Human-message counts are exact enough** for trend use. They come from Slack search with bots excluded, paged to the end. Thread replies are included. Bot and integration posts are excluded. Two short windows were reconstructed across page boundaries (±5 messages). Counts cover public channels only, so #team-incident-response and #triage-results returned no results because they are private or bot-only.
- **Alert volume.** For era (b) it is the incident-log alert rows (Slack-sourced). For other eras it is a single-day sample, a weekday in each era. Era (c) and (e) incident-log rows count Datadog monitor transitions and are **not comparable** to Slack message counts. In particular, #alert-frontend-errors rows drop ~90% after June because degraded mode only sees DD monitors, not because the channel went quiet.
- **"% of alerts touched" and "time to first human reply"** come from thread metadata (`slack_read_channel` detailed mode) on sampled days, not from a full census.
- No Slack message text, personal names or secrets are reproduced here. People are counted, not named.

---

## 2. Changes made (timeline)

Tooling commits are from `git log` on `main` and `origin/alerting-system-grafana`. Per-cycle `triage …`/`poll-cycle …` commits are excluded. Platform fixes come from `kb/known-issues.json`, the stability reviews and Slack.

| Date | Change | Type | Source |
|---|---|---|---|
| 2026-02-09 | `#alert-impact-monitoring` renamed `#alert-runtime-monitoring` and relaunched as the shared CRM + Vertical-Apps alert-monitoring channel (use emotes when on duty) | Process | Slack channel event |
| 2026-05-01 | Triage-bot scaffolded: hourly pull-mode polling of the alert channels via Slack MCP | Tooling | `7874678f`, `7d77a616` |
| 2026-05-01 | Architecture/service catalog `CLAUDE.md` loaded each cycle | Tooling | `18c899d8` |
| 2026-05-04 | v0.6 root-cause **grouping** of alerts before investigating | Tooling | `f0e73c60` (PR #1) |
| 2026-05-04 | v0.7 service-aware investigation + per-group investigation reports | Tooling | `554d3dd7` (PR #2) |
| 2026-05-04 | Monthly **stability-review** routine | Tooling | `83743cc5` |
| 2026-05-06 | Every outbound Slack message logged to `docs/messages/` | Tooling | `3d1e3353` |
| 2026-05-20 | Stop posting to #swat; DM only | Tooling | `e8cdd115` |
| 2026-05-20/21 | Durable local scheduling (Task Scheduler) + auto-push | Tooling | `37e57f8f`, `7fc47a08` |
| 2026-05-21 | KB-approver removed (agents write KB directly); KB seeded with 5 PIR entries | Tooling | `00c082af`, `3c779fba` |
| 2026-05-21 | **Layer 1: known-issue-recurrence DM suppression** with re-surface | Tooling | `35c8b4fe` |
| 2026-05-21 | **Layers 2–4: impact-scored escalation, daily digest, PIR ingestion** | Tooling | `30cb0180` |
| 2026-05-22 | Finer scoring; `docs/actionable/` replaces the digest DM | Tooling | `548b9f87` |
| 2026-05-25 / 06-01 | PIR ingest +9 / +39 KB entries | Tooling/KB | `82881080`, `aef0b9c3` |
| 2026-06-03 | **oauth_token bloat fixed**: expired tokens removed, TTL auto-delete index | Platform | Slack #alert-system; `ki-oauth-token-db-bloat` last_seen 2026-06-03 |
| 2026-06-04 | Hard rule: fetch `origin/<default>` before reading code (stale-clone misattribution) | Tooling | `7a2eed8d` |
| 2026-06-05 | ms-account-api deploy regression rolled back (P0, ~70 min) | Platform | `ki-2026-05-21` fix_status, `2026-06-10-report.md` |
| 2026-06-09 | Active-swat-incident shortcut | Tooling | `051e7ef5` |
| 2026-06-10 | Tighter KB matching + precedence rules | Tooling | `2cde8ecd` |
| 2026-06-17 | Monitor #team-incident-response; `ownership.md` as identify-only routing | Tooling | `6aed8013` |
| 2026-06-18 | Grafana-as-code SLO alerts (separate from triage scoring) | Tooling | `813c4836`, `a9194a13` |
| 2026-06-19 | **Output swap:** findings → #triage-results channel, health → DM | Tooling | `3df088c6` |
| ~2026-06-18 → | Slack MCP unavailable; **degraded mode** (DD monitor scan-diff) becomes the norm | Tooling (regression) | `2026-07-07`/`08-04` reports |
| 2026-07-04 → | False-alarm KB grows to 49 entries | KB | `kb/false-alarms.json` |
| 2026-07-31 → 08-25 | Mobile RUM self-noise tickets filed and partly fixed (PL-64578/64579/64580) | Platform | Slack #alert-runtime-monitoring |
| 2026-08-19 | Poll #alert-no-code-next-gen; datasource-aware KIR evidence; deterministic investigation pipeline + scoring with eval corpus; Slack-write guard hook; watchdog task; weekly digest | Tooling | `bd35739e`, `ff3b713f`, `249e9f6d`, `b3eb932b`, `b95c10ea` |
| 2026-09-25 | ms-tags-api subscriber routing hotfix after the tags error queue grew past 74k | Platform | Slack #alert-system |
| 2026-09-25 → 11-19 | **Routine host down 56 days**; the watchdog did not surface it | Tooling (outage) | incident-log gap; catch-up note 2026-11-19 |
| 2026-11-18 | SMS volume monitor thresholds raised to the new weekday baseline | Platform | Slack #alert-runtime-monitoring |

---

## 3. Biggest-impact improvements (ranked by measured delta)

Weekly numbers come from `scripts/retro_stats.py --ref origin/alerting-system-grafana` (appendix A). "Surfaced" means a DM or a #triage-results post put in front of a human.

| # | Improvement | Metric | Before | After | Evidence |
|---:|---|---|---|---|---|
| 1 | **KB + KIR suppression + impact-scored escalation** (05-21/22) | Needs-human groups / week | 66, 91, 71, 132 (W18–W21) | 31, 40, 27, 19 (W22–W25) | appendix A weekly table; `35c8b4fe`, `30cb0180` |
| | | Surfaced to a human / week | 66–109 | 20–25 | appendix A |
| | | KIR share of classified groups | 0% → 15% | 69–88% (W22–W29) | appendix A |
| 2 | **Root-cause grouping** (05-04) | Investigations per alert | 1 : 1 | 2,976 groups for 5,960 alert rows (−50%); 2,964 rows folded in as satellites | appendix A totals; `f0e73c60` |
| 3 | **False-alarm KB** (July →) | Alerts closed as known false alarms | 0 | 452 classifications over 49 FA entries (Jul 205, Aug 122) | `kb/false-alarms.json`, appendix A |
| 4 | **Gateway → microservices timeout** rollback + follow-ups | ES error trend (30 d) | +1,025.7% (Jul review) | +42.3% (Aug) → **−59.0%** (Sep); no fire since 2026-09-24 | `stability-reviews/2026-08/2026-08-04-report.md`, `2026-09/2026-09-01-report.md`; `ki-2026-05-21` last_seen |
| | | KIR rows / week | 50–80 (W22–W24) | 0 (W47–W48) | appendix A per-KB table |
| 5 | **oauth_token bloat fix** (06-03) | DB growth / alerts | ~8 GB/day growth; daily backup-with-warning | expired tokens purged, TTL index; 0 KIR since 06-03 | `2026-06-10-report.md` F1; `ki-oauth-token-db-bloat`; Slack #alert-system |
| 6 | **#alert-runtime-monitoring relaunch** (02-09) | Human messages / month | 0 (Dec), 0 (Jan) | 65 (Feb), 43, 28, 45, 52, 83 (Jul), 39, 54 | §5 table |
| 7 | **KB growth itself** | KB entries fixed/mitigated | 5 PIR seeds | 104 known issues, 44 resolved/mitigated with no recurrence | `kb/known-issues.json`; appendix A |

Cross-check: the 2026-06-10 review independently measured needs-human DMs −46% and KIR matches +92.6% month over month (`stability-reviews/2026-06/2026-06-10-report.md`). That agrees with rows 1 and 7.

---

## 4. What continues to be a problem

### 4.1 Chronic known issues (open, still firing)

| KB entry | Lifetime occurrences | fix_status | Last seen | What is missing |
|---|---:|---|---|---|
| `ki-2026-05-24-runtime-core-rtc-p95-recurring` | 297 | investigating | 2026-11-25 | No Jira, no owner action in 6 months. Latency only; a new correlate (rest-api paged queries saturating one SQL host) was logged on 11-24. |
| `ki-2026-07-04-crm-amqp-consumer-monitor-family-quiet-period-flap` | 205 | monitoring-noise-suspected-unconfirmed | 2026-11-25 | Threshold change recommended in Aug and Sep reviews (ICE 12–15); not done. |
| `ki-2026-07-03-ms-scheduler-api-seriesid-negative-recordid` | 156 | proposed | 2026-11-24 | **Top ICE (54.0) in both the Aug and Sep reviews.** One-line guard, unfiled for 20 weeks. |
| `ki-2026-07-03-eda-consumer-amqp-stopped-publishing` | 73 | escalated-for-review | 2026-11-20 | No decision recorded. |
| `ki-2026-07-07-notifications-p95-latency-monitor-noise` | 53 | monitoring-noise-suspected-unconfirmed | 2026-11-25 | A daily batch trips the monitor; needs a min-hits guard. |
| `ki-2026-07-02-tables-fields-fieldtablenameref-null-linked-fields` | 20 | needs-human | 2026-11-20 | Still recurring. |
| *(no KB entry yet)* Twilio bulk-SMS callback burst / mobile-notifications thread-pool starvation | 5 bot-seen fires 11-17 → 11-24 | — | 2026-11-24 | A defect has been proposed. The KB seed is waiting on a decision, so every weekday burst escalates. |

Not every open entry is still a problem. These have gone quiet and are candidates to close, not to work on: `ki-2026-07-03-method-ui-grid-dropdown-performance-test-nodata` (175 occurrences, last seen 2026-08-12), the warehouse dashboard no-data (44, last seen 08-06), ms-account-api 4xx noise (52, last seen 08-10), and the synthetics sign-in transient (38, last seen 08-10).

### 4.2 Recommendations that never shipped

From the recommendation trackers: in `2026-08-04-report.md`, **0 of the 5** July top recommendations had shipped. In `2026-09-01-report.md`, **0 of the 5** August ones had. The repeat items:

- ship the ms-scheduler guard;
- add a real error-rate monitor for `method-import-subscriber` (104,125 → 62,794 errors/30d with 0% monitor coverage);
- retire the 8 chronic No-Data QA monitors;
- fix the ms-account-api `IsMLMEnabled` schema drift;
- re-threshold the CRM AMQP monitors;
- re-authenticate Atlassian (4 reports running).

Only the oauth_token fix (June, F1) is evidenced as done.

### 4.3 Tool and bot reliability

| Gap | Duration / scope | Evidence |
|---|---|---|
| Routine host down, no heartbeat, nobody alerted | 2026-09-25 → 2026-11-19 (56 d); also 4–8 d gaps in late Jun and mid-Jul | incident-log gaps (§1); catch-up note on 2026-11-19 |
| Slack MCP unavailable → degraded mode | ~2026-06-18 → today | Can't see non-Datadog alerts (Centreon, Grafana, Logstash ML), so the KIR share fell to 30–31% in W47–W48. Can't reply in alert threads. Heartbeats on 11-19 → 11-21. |
| Atlassian MCP unauthenticated | 4+ consecutive reviews | `2026-09-01-report.md` header |
| ES 401 (17 d), SSH bastion down (no account-impact lookups) | June | poll-cycle notes 2026-06-18 |
| GitHub token 403 on `methodcrm` → stale local clones | Aug–Sep | `2026-09-01-report.md` F1 |
| `main` 5 months stale; routine YAML says `main` | since 2026-06-18 | `git rev-list origin/main..origin/alerting-system-grafana` = 1,380 |
| Spend | $171 lifetime; peak weeks $19–24 (W28, W32) during degraded backlog cycles | appendix A |

### 4.4 Alert noise the bot does not reach

- **Repeat notifications.** On the sampled ordinary weekday (2026-11-23), 34 of #alert-system's 59 messages were one Centreon disk WARNING re-posted every 10 minutes for 5 h 42 m. A human then fixed it in one message.
- **#alert-frontend-errors volume** fell from **52 messages** on the 2025-11-03 sample day to **21** on 2026-11-23 (single-day samples, so treat it as directional). It still has **1 human message in 12 months**: §5.

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
| 2026-10 | 14 | 8 | (bot down) | 10-06 | ~100 | 0 | 0% | — |
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
| 2026-10 | 10 | 4 | (bot down) | 10-06 | 58 | 0 | 0% | — |
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
| 2026-10 | 0 | 0 | (bot down) | 10-06 | 48 | 0 | 0% | — |
| 2026-11 | 0 | 0 | (DD-sourced) | 11-03 | 10 | 0 | 0% | — |
| **12 months** | **1** | **1** | | | **703+** | **0** | **0%** | never |

Because this channel had one human message all year, every month's touch rate is 0% from the census alone; the sample days only add volume. Sample-day volume fell from 46–100+ a day (Dec–May) to **10 on 2026-11-03** (and 21 on 2026-11-23, §4.4). That is the first sustained drop, but nobody watches what is left.

### 5.4 Human messages per 100 alerts, and detailed-mode samples

Era (b) only, where incident-log alert rows are Slack-sourced.

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
| #alert-system, 2025-11-03 (pre-bot weekday) | 13 | 0 threads (one Centreon alert acknowledged in the Centreon tool) | 0% | Centreon ack in ~25 s; no Slack reply |
| #alert-runtime-monitoring, 2026-09-24 (an above-average day) | 34 | 2 threads (2 and 9 replies) + 1 reaction | ~6–9% | ~1 h and ~3.5 h for the two threaded alerts |
| #alert-system, 2026-11-23 (recent weekday) | 58 | 1 top-level human message | ~2% | 5 h 42 m after the first of 34 repeated disk warnings |

### #swat and #team-incident-response

#swat is an incident channel worked by humans: 20+ human messages in 11-21 → 11-23 alone, around one P0. It was not censused month by month. #team-incident-response is not visible to public search, so it is not measured here.

### 5.5 Commentary

- **#alert-runtime-monitoring is the success story**, and the cause was a process change, not tooling. The 2026-02-09 relaunch gave it named on-duty teams and an emote convention. It went from silent to the most conversational alert channel. Threads there routinely end in a ticket, a threshold change or a "known noise" verdict. That is the human version of what the bot's KB does. The October–November dip (10 and 7) lines up with the bot outage and with fewer new monitors, so it needs watching.
- **#alert-system is worked, but in bursts.** It peaks during incidents and releases (Jan ≈ 100 around app-update and EDA issues; Sep 74 around the tags-queue incident) and goes quiet otherwise (Jul–Aug and Oct ≈ 12–14). Most messages are ops actions (restarts, recycles, purges) and questions about whether a release caused an alert, not alert-by-alert acknowledgement. Repeat notifications drown the signal.
- **#alert-frontend-errors is effectively unwatched.** It had about 900 alerts a month in May–June, ~1,500 a month extrapolated from the Nov 2025 sample, and one human message all year. Its monitor (77419271, browser XHR errors) is also the single largest source of new false-alarm entries in Nov 2026 (single-session client network drops).
- **#swat is human-driven and healthy.** Incident channels are not the engagement problem.
- **Concentration risk.** Roughly a third of #alert-runtime-monitoring messages come from one person, and a large share of those are prompts asking a team whether anyone is investigating. Engagement depends on that one person prompting.
- **Effect of the bot on channel engagement.** In era (b) the bot DMed the operator rather than posting in-channel, so it could not change channel behaviour directly. From 2026-06-19 it posts to #triage-results, which is not covered by public search. Whether its analysis reaches the channel teams is **unmeasured**. The bot's notes in degraded mode explicitly say it cannot check operator engagement either.

---

## 6. Recommendations (ICE-scored per `references/methodology/recommendation-rubric.md`)

| # | Recommendation | Impact | Confidence | Effort | ICE | Why |
|---:|---|---:|---:|---:|---:|---|
| 1 | **Ship the ms-scheduler-api `recordId <= 0` guard** (carry-forward) | 6 | 9 | 1 | **54.0** | 156 fires, a one-line fix, top item in two reviews (§4.1) |
| 2 | **Add an external dead-man's switch for the triage routine.** Alert a human (not the bot's own channel) when there has been no poll-cycle for more than 6 h. | 8 | 9 | 2 | **36.0** | A 56-day silent outage; the watchdog task did not catch it (§4.3) |
| 3 | **Decide the fate of #alert-frontend-errors.** Route monitor 77419271 to its owning team with an on-duty emote convention (as for runtime-monitoring), or downgrade it to a daily digest, or retire it. | 7 | 8 | 2 | **28.0** | 1 human message a year against ~900–1,500 alerts a month (§5) |
| 4 | **Merge `alerting-system-grafana` into `main`** (or make it the default branch) and fix `routines/*.yaml` push targets | 6 | 9 | 2 | **27.0** | 1,380 commits of KB, investigations and tooling invisible on `main` (§1) |
| 5 | **Restore Slack read access for the routine** (MCP connector or bot-token `channels:history`) | 8 | 8 | 3 | **21.3** | Degraded mode can't see non-DD alerts or reply in threads; the KIR share fell to ~30% (§4.3) |
| 6 | **Throttle re-notification** on Centreon (and Grafana) checks: notify on state change plus every 60 min, not every 10 | 5 | 8 | 2 | **20.0** | 34 identical posts in 5.7 h on the sample day (§4.4) |
| 7 | **File a Jira and an owner for runtime-core RTC p95** (`ki-2026-05-24`) | 7 | 6 | 3 | **14.0** | 297 occurrences, the longest-running open item, no ticket (§4.1) |

---

## Appendix A — script output

Command:

```
python scripts/retro_stats.py --ref origin/alerting-system-grafana --as-of 2026-11-25 --top-kb 12
```

(Run with the `--ref` flag because the live data is on that branch; see §1. Weeks W40–W46 are absent because there are no rows during the outage.)

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

- **Repo data.** `git fetch origin`; `git log --format='%ad|%h|%s'` on `origin/main` and on `origin/main..origin/alerting-system-grafana`, excluding per-cycle commits. `scripts/retro_stats.py` (JSON-parses every line; ISO and epoch `ts`), as in appendix A. Stability reviews read: `2026-06-10`, `2026-08-04`, `2026-09-01` (Executive Summary and trackers).
- **Slack human activity.** `slack_search_public` with `filters: in:<#channel> after:2025-11-24 [before:…]`, `include_bots: false`, `sort: timestamp`, paged to the end. Each result was tallied by month and distinct author ID; the 20-page cap was handled by re-querying with `before:`. Channels: `CPHHABKAA` (#alert-system), `C063V5HTTFU` (#alert-runtime-monitoring), `C03TYHGRS23` (#alert-frontend-errors), `C01L5K42GQ6` (#swat, last month only), `C0B6233UN4S` (#team-incident-response, no public results), `C0B0Q3KHC07` (#triage-results, no human results).
- **Slack samples.** `slack_read_channel`:
  - concise mode for volume: per month, the first Tuesday (2025-11-25, 12-02, 2026-01-06, 02-03, 03-03, 04-07, 05-05, 06-02, 07-07, 08-04, 09-01, 10-06, 11-03) for all three alert channels, using `oldest`/`latest` set to that day in US Eastern time; also #alert-system and #alert-frontend-errors on 2025-11-03 and 2026-11-23;
  - `slack_search_public` with `filters: in:<#channel> is:thread on:<sample day>` and `include_bots: true` for alert threads and human first-reply times on those days (skipped where the human-message census shows no human message that day);
  - detailed mode for thread and reaction metadata: #alert-system 2025-11-03, #alert-runtime-monitoring 2026-09-24;
  - the latest #triage-results posts for bot liveness.
- **Read-only.** No Slack posts, Jira writes or KB edits were made for this report.
