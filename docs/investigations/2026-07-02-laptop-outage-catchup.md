# Investigation — laptop-outage catch-up (2026-07-02)

**Type:** manual, operator-driven (not a cron cycle)
**Outage window:** 2026-06-26T05:34:26Z → 2026-07-02T12:34:22Z (~6 d 7 h)
**Analyst:** triage-bot (interactive, driven by Ben)

## 1. Why we were dark

The triage host laptop entered sleep on battery and the battery drained. The Windows
System event log shows the clock froze mid-sleep and jumped on resume:

> `The system time has changed to 2026-07-02T12:34:22.500Z from 2026-06-26T05:34:26.181Z`

| Event | UTC | Eastern (EDT) |
|---|---|---|
| Last alive (clock froze) | 2026-06-26 05:34:26Z | 2026-06-26 01:34:26 AM |
| Powered back on (AC + resume) | 2026-07-02 12:34:22Z | 2026-07-02 08:34:22 AM |

Corroborated by the last triage git commit (`fa6663d`, heartbeat `04:07Z` = 06-26 00:07 EDT).
Effective coverage actually lapsed the evening of 06-25 (that heartbeat already reported
"0 polls today, cron stuck" — the known headless-auth-401 condition).

When the host resumed, the scheduled routines fired at 12:40Z and the triage cron ran a
degraded (no Slack MCP) 6-day-gap catch-up at **12:44Z**, covering ki-28 / ki-21 /
ImportSubscriber. This manual pass covers what that automated degraded cycle could not.

## 2. Verdict: NO production incident during the outage

| Source | Result |
|---|---|
| `#swat` | Empty (one channel-join). No incidents. |
| `#team-incident-response` | Only automated `swat-rb-*` health-check runbooks + a process announcement. No human-declared incident. |
| DD monitors (now) | All OK. "No Data" entries are Synthetics release-runs + chronically-empty infra sub-monitors. |
| Critical path (ES) | gateway ~325 errors / 6 d (~54/day background), auth 8, oauth 0 — no spike. |
| ES top errors | All chronic knowns; the largest is *declining* (see §3). |

## 3. Findings

### A. `newimport-api` health 503 on both import nodes — 06-27 08:44–08:48Z  → KB `ki-2026-06-27-newimport-export-path-missing-503` (NEW)
`Method.Import.Api /newimport/health/check` returned HTTP 503 on **MSL03** and **MSL04**.
Exactly one dependency unhealthy: `ExportFilePath` → `Export path '/mnt/temp_backups/methodimport/'
does not exist or is not accessible`. Redis / RabbitMQ / Mongo / SQL c1–c5 all healthy; process up.
A mount/dir-availability failure (same `temp_backups` family as `ki-2026-06-19` MSL04 CIFS).
**Health-probe only** — the request-level DD Import monitors (299551459 / …465 / …472 / …499) were
all OK, so this never hit the normal alert path; it surfaced only via the SWAT runbook.
**Owner: Admin. Needs an ops check** of `/mnt/temp_backups` on both nodes (SSH bastion down this
session — could not verify current mount state). Most actionable item of the outage.

### B. `MethodUIClassic` TimeZoneNotFoundException — chronic, declining  → KB `ki-2026-06-17` (REFRESHED, occ 4→5)
`TimeZoneNotFoundException: 'America/New_York'` via `UserPageCodeBehindHelper.fncNativeFieldDateAndTime`.
ES over 06-26→07-02 = **3,198 hits** — the single largest error bucket — but the signature is
unchanged and the rate is *falling*:

| Dimension | Value |
|---|---|
| Accounts (ONLY two) | `thestoragegroup` 2,869 · `supplyshield` 329 |
| Hosts | PROD-CLASSIC-01 1,587 · PROD-CLASSIC-02 1,611 |
| App | MethodUIClassic |
| Latest | 2026-07-01T20:39:09Z |
| Prior week (06-19→06-26) | 4,196 → flat-to-declining |

Account-data driven (the two accounts store an IANA tz id the classic runtime can't resolve).
Not a missed incident. Mitigation: rewrite those two accounts' stored tz to `Eastern Standard Time`.
The 12:44Z automated cycle logged "0 hits" only because it checked a ~65-min poll window.

### C. Chronic background (no action — already known-shaped)
- SQL connection-pool exhaustion — 1,287, all on PROD-CLASSIC-02 (classic pool).
- `runtime-designer` null-field warnings (06-29) — warning-level, service healthy (200).
- Rainforest payment errors (230+137) — `#alert-transactions` territory, not polled here.
- QBO sync / base64 / padding buckets — steady chronic noise.

### D. Housekeeping
- `approutine-agent.txt` = 3.2 GB on prod-rt-04 (disk fine at 31%; rotation overdue).

## 4. Process change to note
**06-30 13:57Z — Arash Pakbaz:** as of 06-30 teams must respond to their own SWAT alerts
(DevOps = backup). Automated `swat-rb-*` runbooks now post investigations to `#team-incident-response`.
Relevant to how triage reasons about routing going forward.

## 5. Actions taken
- `kb/known-issues.json`: refreshed `ki-2026-06-17` (occ 4→5, last_seen→2026-07-01T20:39:09Z, note updated); created `ki-2026-06-27-newimport-export-path-missing-503`.
- `kb/incident-log.jsonl`: appended catch-up summary + two finding lines.
- `docs/actionable/2026-07-02.md`: newimport ops item.
- No outbound Slack sent (operator-driven session).

## 6. Open items for a human
1. **Admin:** verify `/mnt/temp_backups/methodimport/` mount on MSL03 + MSL04 (finding A).
2. Apply the `ki-2026-06-17` mitigation (two-account tz rewrite) — chronic, unfixed since 06-03.
3. Consider a synthetic on `/newimport/health/check` so health-probe 503s page without the SWAT runbook.
