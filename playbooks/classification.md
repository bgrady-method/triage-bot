# Classification rubric

The routine classifies every alert into exactly **one of four buckets** before deciding what to do. The classification is the most important output of the run — it determines what Ben sees in his DM and (in v2) whether a PR gets opened.

## The four buckets

| Bucket | Meaning | Day-1 action |
|---|---|---|
| `false-alarm` | The alert fired but the system is fine. Known-noisy monitor, transient blip, expected behavior. | DM Ben with `proposed_false_alarm` JSON; thread-reply 🤖 to the alert; no further action |
| `known-issue-recurrence` | The alert matches a `kb/known-issues.json` entry. The fix is known (or in-progress). | DM Ben with the playbook from the KB entry + `occurrences-this-week` count |
| `new-with-clear-fix` | A new failure mode, but logs + code point at a single-file change with high confidence. | v1: DM Ben with the proposed diff inline. v2 (only after gate): open a PR. |
| `needs-human` | Anything else. Real failure, unclear scope, multi-file change, novel error, unfamiliar service. | DM Ben with the full investigation summary; he decides. |

## Day-1 conservative bias

For the first **50 runs** (tracked via `kb/incident-log.jsonl` line count), the routine **must default to `needs-human`** unless one of:
- It hit a `kb/known-issues.json` or `kb/false-alarms.json` entry (literal or regex match), OR
- The investigation produced a confidence score ≥ 0.95 with all of: matching exception name, matching error message, matching service, recent identical log.

Why: the KB is empty at launch. The bot will see novelty everywhere and over-classify. We'd rather over-DM Ben than miss a real fire.

## Confidence calibration

Confidence is a number 0..1 the routine produces and writes to `incident-log.jsonl` for every classification. Ben's reactions on DMs are the ground truth used to calibrate it.

| Confidence | Meaning |
|---|---|
| ≥ 0.95 | Identical signature to a previous run with the same root cause. Safe to act on KB-driven actions. |
| 0.85 – 0.95 | Strong evidence (golden signal anomaly + matching log line + matching service). Eligible for v2 auto-PR if the diff is single-file and the KB entry has a `fix_template`. |
| 0.70 – 0.85 | Plausible but not certain. DM-only. |
| < 0.70 | Hand-wave. Default to `needs-human`. |

When the routine is unsure between two buckets, **bias toward the higher-friction one** (`needs-human` over `new-with-clear-fix`; `known-issue-recurrence` over `false-alarm`).

## Underlying bug taxonomy (when the bucket is `needs-human` or `new-with-clear-fix`)

Borrowed from Method's [Debugging Best Practices](https://method.atlassian.net/wiki/spaces/SD/pages/167575850). Useful when summarizing *what kind* of bug it looks like:

| Type | Signal | Action |
|---|---|---|
| **Data Issue** | One account affected across multiple environments | Fix the data, document corruption root cause |
| **Environment / Config Issue** | Multiple accounts but only in one environment | Compare env configs, feature flags, DB copy state |
| **Code Issue** | Multiple accounts across multiple environments | Systemic defect — fix in code with regression tests |

Include the bug-type guess in the DM summary when the bucket is `needs-human`.

## Examples

**false-alarm**
```
Channel: alert-runtime-monitoring
Text:    "tables-fields p95 latency 450ms threshold 400ms"
Match:   kb/false-alarms.json#"daily-1am-warmup-spike"
         (cron-driven cache prewarm always nudges p95 between 1:00-1:05 ET)
Action:  thread-reply with reason; no DM
Confidence: 0.97
```

**known-issue-recurrence**
```
Channel: alert-runtime-monitoring
Text:    "Deadlock found when trying to get lock; tables-fields BulkAddField"
Match:   kb/known-issues.json#"ki-2026-04-12-tables-fields-deadlock"
Action:  DM Ben w/ playbook; this week: 7th occurrence; jira PL-12345 in-progress
Confidence: 0.93
```

**new-with-clear-fix** (v1 = DM with diff; v2 = PR)
```
Channel: alert-frontend-errors
Text:    "TypeError: Cannot read properties of undefined (reading 'fields')"
Investigation:
  - Stack trace points at apps/m-one/src/.../FieldList.tsx:142
  - Code at L142: `props.fields.map(...)`. No null guard.
  - Same error pattern: 38 occurrences in last 24h, all from one customer.
  - One-line fix: `(props.fields ?? []).map(...)`
Confidence: 0.88
Action (v1): DM Ben w/ proposed diff inline. (v2: open PR with the same diff.)
```

**needs-human** (the default for anything ambiguous)
```
Channel: swat
Text:    "P1: API errors spiking, customer XYZ reports total outage"
Investigation:
  - Datadog: error rate 12x baseline, started 14:31, no firing monitor yet
  - ES: SqlException timeouts across multiple services
  - Recent deploys: api-gateway @ 14:28
  - SQL health-check on customer XYZ DB: connection succeeds, no obvious issue
Action:  DM Ben with full summary; he decides whether to roll back the deploy or page DB
Confidence: 0.6 (root cause not yet isolated)
```

## What classification does *not* do

- It does not page anyone. SWAT alerts already paged a human; the bot just gathers context.
- It does not file Jira tickets in v1. (If we add that in v2, it goes via existing `log-defect` skill patterns, not a new path.)
- It does not silence monitors. Ever.
