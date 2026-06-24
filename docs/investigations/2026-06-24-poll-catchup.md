# Investigation: poll-catchup — 2026-06-24 14:10 UTC

Catch-up poll cycle after a ~4-day cron stall. This is a **holistic current-state
sweep**, not a per-alert investigation: the backlog (~420 empty-body block alerts
across 4 days) is far beyond single-cycle per-group investigation, the alert bodies
are not retrievable via the Slack MCP (content lives in Slack blocks), and the
authoritative monitoring sources (DD monitors, DD prod logs, ES) confirm the alerts
were point-in-time chronic signals that have self-recovered. The actionable finding
is the scheduler outage, not any production incident.

## Alert summary
- **Trigger:** manual catch-up run (cron has not fired since 2026-06-20 11:22Z)
- **Last successful poll cycle:** 2026-06-20 11:22:17Z (itself a manual 13h catch-up)
- **Gap:** ~4 days with no automated triage (the routine was effectively offline for production alerting)
- **Channels polled:** alert-system, alert-frontend-errors, alert-runtime-monitoring, swat, team-incident-response

## Classification
- **Result:** poll-cycle / no actionable incident
- **Confidence:** 0.9 (current state); backlog deferred by design
- **Action taken:** holistic current-state sweep + operational DM to Ben (cron stall)
- **Matched KB entry:** none new — backlog maps to existing chronic known-issues

## Investigation

### Time window
Backlog window: 2026-06-20 ~10:30Z → 2026-06-24 14:05Z. Current-state probes: last 3–6h to 14:10Z.

### Current production state — CALM, no active incident
| Signal | Result |
|---|---|
| #swat | **empty** in window (no human incident coordination) |
| #team-incident-response | 12 automated SWAT-runbook bot posts, all 2026-06-22 14:01–16:53Z; no human authors. Latest: `journalagent.service` `inactive (dead)` on MSL04 — clean exit (status=0), DEVOPS, **warning/informational** |
| DD monitors (Alert/No-Data/Warn) | 33 "firing" but **no service error-rate/latency monitor** among them — all chronic No-Data synthetics (Signup, Method-UI grid/dropdown release runs) + infra (Linux disk/cpu/mem, RabbitMQ mem, ms-account redis/sql/mongo) last-triggered months ago; 2 Alert-state = error-tracking "New issue to review" |
| DD prod error logs (last 3h) | **0** results for `env:prod status:error` |
| ES Error-level (last 6h) | 380 docs total — all chronic signatures (see below). No spike, no new exception, no cascade |
| Tool health | gh ok · dd ok · es ok · sql/mongo skipped (no SSH tunnel in this run) |

### ES error profile (last 6h) — chronic background, all known
| Count | Error |
|---|---|
| 44 | `The time zone ID 'America/New_York' was not found on the local computer.` (Linux/.NET tz config) |
| 27 | `Rainforest: ... Customer doesn't have a tokenized payment available` (BillAutoMtnSrv.PaymentService — business-logic) |
| 22 | `Rainforest: ... payments can only be processed in USD` (business-logic) |
| 16 | `The remote name could not be resolved: 'merchantaccount.quickbooks.com'` (external QBO endpoint) |
| 16 | `Unsupported SyncableMethodTypes.TimeActivity is unsupported.` (QBO sync) |
| 11 | `Payment processing failed` (Rainforest) |
| 8 | `A task was canceled.` (timeout noise) |
| 8 | grid XML screen 920 (app-specific, intentional guard exception) |

The Rainforest/payment errors surface in `#alert-transactions` (not polled — see KB note
`project_alert_transactions_gap`); they are customer-side business-logic errors (no tokenized
payment / non-USD), not a system outage.

### Backlog volume while blind (~4 days, empty-body block alerts)
| Channel | ~Count | Notes |
|---|---|---|
| alert-system | ~101 | newest 06-24 10:05 EDT; clusters today ~01:47, 05:02, 09:39–09:49 EDT |
| alert-frontend-errors | ~105 | quiet 06-23 16:08 → resumed 06-24 06:39–06:48 (RUM empty-body, ki-2026-05-21 shape) |
| alert-runtime-monitoring | ≥210 | noisiest; resumed today 07:53–09:13 EDT (runtime-core p95 shape, ki-2026-05-24) |
| team-incident-response | 12 | automated SWAT-runbook output only (06-22) |
| swat | 0 | — |

### Likely cause
No production incident. The scheduler (hourly cron) has not fired since 2026-06-20 11:22Z —
the 3rd stall event in a week (prior: 06-19 22:18Z, 06-20). Triage was offline for ~4 days.
The accumulated alerts are the normal chronic profile (gateway/microservices timeout RUM,
runtime-core p95, timezone-ID, Rainforest payments, QBO sync) which all self-recover.

### Evidence links
- DD monitors: https://app.datadoghq.com/monitors/manage?q=status%3A(Alert%20OR%20%22No%20Data%22)
- DD logs (prod errors): https://app.datadoghq.com/logs?query=env%3Aprod%20status%3Aerror&from_ts=1782299400000&to_ts=1782310200000&live=false
- Kibana: https://ca8e80d7f930400fb386a29477353efa.kb.us-west-1.aws.found.io:9243/app/discover#/?_g=(time:(from:'2026-06-24T08:00:00Z',to:'2026-06-24T14:10:00Z'))&_a=(query:(language:kuery,query:'Level:Error'))

## What we couldn't determine
- Per-alert detail for the backlog: alert bodies are empty via the Slack MCP (content in Slack blocks); investigation relies on DD/ES, which show calm state. SQL/Mongo not queried (no SSH tunnel in this run) — not needed, no customer-DB-specific signal.

## Suggested KB entry (if applicable)
None — no new pattern. Backlog maps to existing entries (ki-2026-05-21-gateway-microservices-timeout, ki-2026-05-24-runtime-core-rtc-p95-recurring).

## Lessons / follow-up
- **Primary:** the hourly cron is unreliable — 3rd multi-hour-to-multi-day stall in a week. The triage routine has no value if the scheduler doesn't fire. Investigate/replace the scheduler (or add a watchdog that pages when no poll-cycle line has been written in >2h).
- The heartbeat correctly flagged "degraded" twice during the 06-19/06-20 stall but there is no auto-escalation when the gap exceeds a day — consider a hard page after N missed cycles.
- Catch-up after a long stall needs a defined policy: per-alert replay of a multi-day backlog is infeasible and low-value; a current-state sweep + KB-recurrence reconciliation (as done here) is the right shape. Worth codifying in prompt.md.
