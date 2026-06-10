---
status: placeholder
created_on: 2026-06-10
created_by: triage-bot
incident_date: 2026-06-05
service: method-platform-ui (m-one)
severity: P0
counts_toward_availability: ui-only
ui_only: true
backend_healthy: true
jira: NCNG-1445
---

# m-one no-code grid-rendering regression — 2026-06-05

## Title
m-one no-code reference grid columns rendered blank on screen load. Client-side rendering bug; backend healthy throughout. Actions continued to fire correctly.

## Duration
**2026-06-05 13:00 UTC → 15:05 UTC (09:00–11:05 EDT). ~120 minutes UI impairment.**

P0 logged at the start of the window; rollback initiated 10:44 EDT (14:44 UTC); recovery confirmed 11:05 EDT (15:05 UTC).

## Impact
- UI-only: reference grid columns showed blank in no-code apps.
- Backend was fully functional. Actions still fired. Data integrity unaffected.
- Workaround: users could still execute actions and manipulate data through other UI paths; only the reference-grid display was broken.

## Availability classification
This is the contested case. Counted as **UI-only impairment** (`counts_toward_availability: ui-only`) rather than full platform downtime, because:
- Customers could still log in, sign up, and execute actions.
- Backend services were healthy.
- "Platform availability" definitions split: by stricter SLA wording ("feature-correct rendering"), this counts; by laxer wording ("platform accessible"), it doesn't.

The 14-day availability report will count this as **120 min UI-impaired** but distinguish from full downtime. Industry framing should annotate it accordingly.

## Root cause
Client-side rendering regression in the m-one grid component. Specifics not investigated by the bot (UI bugs are out of scope for the bot's classification thresholds — needs frontend domain expertise).

Engineering team identified the breaking change in a method-platform-ui release that morning. Rollback resolved.

NCNG-1445 is the tracking Jira for the bot to reference. The real PIR (if written) lives in Confluence.

## Resolution
- 10:44 EDT (14:44 UTC): rollback initiated
- 11:05 EDT (15:05 UTC): recovery confirmed

Recovery time from rollback to confirmation was ~21 minutes (frontend deploys take longer than backend reverts because CDN cache invalidation and worker boot are involved).

## Placeholder status
**Placeholder — no Confluence PIR found in `.claude/pir-parsed.json` as of 2026-06-10.** Counted as UI-only impairment for the next stability-review's availability calculation.

When a real Confluence PIR is published, replace this file's frontmatter with `status: superseded` and the Confluence link.

## Cross-references
- Jira: NCNG-1445
- #swat thread: 2026-06-05 09:00 EDT onward, channel C01L5K42GQ6
- KB: no entry created — UI bug below the 0.85 confidence threshold for bot to write a KB entry
