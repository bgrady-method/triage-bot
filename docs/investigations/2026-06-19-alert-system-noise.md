# Investigation: #alert-system empty-body noise — 2026-06-19 (consolidated)

Consolidated report for 4 low-impact root-cause groups in #alert-system from the
cron-outage backlog (32 messages, 04:11Z–06:37Z Jun19). All were block-only
(Slack MCP does not surface the attachment body), so they share one investigation.

## Group primaries
| group_hash | bot | members | window |
|---|---|---|---|
| 6da29752c41c83a1 | B05PN7JG87L | 12 | 05:49–06:32Z Jun19 |
| c99bec0c301f74f9 | B03GBAMHUTB (Flow Designer Connector) | 18 | 06:13–06:37Z Jun19 |
| b7d198f7c2445587 | B011R3D650X (Datadog) | 1 | 04:11Z Jun19 |
| dc2b95c9786f84db | B011R3D650X (Datadog) | 1 | 06:37Z Jun19 |

## Classification
- **Result:** needs-human → all gated to low-impact (escalation_score 0; below actionable_score_threshold 2)
- **Confidence:** 0.40
- **Action taken:** actionable-low-impact (no DM)
- **Matched KB entry:** none

## Investigation

### Time window
2026-06-19T04:00:00Z → 06:45:00Z

### Tools run
| Tool | Query / args | Result summary |
|---|---|---|
| Slack MCP | conversations.history CPHHABKAA | 32 msgs, all empty body / block-only |
| DD monitors | `--state Alert --state "No Data"` | nothing relevant in Alert (only stale template monitor 227951254, last fired Oct 2025) |
| ES aggregate | `level:Error` by fields.Application, 04:00–06:45Z | 225 errors across 12 services, no concentration |
| ES aggregate | `level:Error` by messageTemplate | TCP timeout 30, HTTP-resp-log 24, "Get Series Info failed recordId -1" 22, "Inventory Management Traits Retrieval Failed" 16 |
| ES aggregate | Method.Data.RestApi errors by message, 12h | tenant-specific: Invalid column name 'BalanceRemaining'/'OpportunityStageName'/'TxnDate', "Database 'jafedecorating' does not exist" |

### Key findings
- 225 errors over 2.75h spread across QBDT.SyncServices (49), Method.Data.RestApi (48), ms-scheduler-api (22), Account.Api (18), AppRoutineSubscriber.Agent (16), native-mobile (12), email-subscriber (11) — **no single service spiking**; this is ordinary distributed background.
- The RestApi errors are tenant-specific schema/customization drift ("Invalid column name", "Database does not exist") — account-specific, not a systemic incident.
- No DD monitor is in Alert for this window.

### Likely cause
Background noise. The #alert-system channel carries many block-only bot posts (Flow Designer Connector, B05PN7JG87L) whose content the bot cannot read via Slack MCP. With no DD monitor firing and only distributed tenant-specific ES errors, there is no actionable incident signal.

### Evidence links
- Kibana: https://logstash.method.me/app/discover#/?_g=(time:(from:'2026-06-19T04:00:00Z',to:'2026-06-19T06:45:00Z'))&_a=(query:(language:kuery,query:'level:Error'))

## What we couldn't determine
The actual content of the Flow Designer Connector / B05PN7JG87L alert blocks — Slack MCP returns empty bodies for these. Severity is inferred from corroborating DD/ES signals (none found), not from the alert text itself.

## Suggested KB entry (if applicable)
None — too low-signal to seed a KB entry from. If these block-only posts recur with a real DD/ES correlate, revisit.

## Lessons / follow-up
- **Recurring visibility gap:** #alert-system block-only bot posts (Flow Designer Connector especially) are unreadable via the Slack MCP. This is the 3rd+ cycle flagging it. Worth either (a) a Datadog/EDA monitor that posts a text summary, or (b) wiring the alert source to include a plain-text fallback, so triage can classify on content rather than falling back to "distributed background, no DM."
