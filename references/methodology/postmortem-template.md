# Postmortem report — section template

Used at Phase 8 of `stability-review-prompt.md`. The monthly report at `stability-reviews/YYYY-MM/report.md` follows this structure exactly — the routine should not invent additional sections.

```
# Method Platform Stability Review — YYYY-MM

_Generated: <ISO-8601 ts> · Window: <window_start> → <window_end> (30d) · Routine: stability-review_

## Executive Summary

- Triage-bot processed **<N>** alert clusters in the window: <K> known-issue-recurrence, <L> false-alarm, <M> needs-human, <P> new-with-clear-fix.
- **Top 5 recommendations** (ranked by ICE score):
  1. **<title>** — ICE <score>. <one-line summary>.
  2. **<title>** — ICE <score>.
  3. …
- Availability snapshot per critical service (vs proposed SLO):
  | Service | Window availability | Proposed SLO | Burn |
  |---------|--------------------:|--------------|-----:|
  | <svc>   | 99.78%              | 99.9%        | 220% |
  | …       |                     |              |      |
- Total error budget consumed across listed services: **<X>%**.

## Methodology

- Sources read: `kb/incident-log.jsonl` (lines <a>..<b>), `docs/investigations/*.md` (<count> reports), `kb/known-issues.json`, `kb/false-alarms.json`.
- Fresh DD queries: <count> (`scripts/dd_search.py`).
- Fresh ES queries: <count> (`scripts/es_search.py`).
- Jira JQL queries (read-only): <count>.
- Course modules consulted: <unique count>.
- Five-whys protocol: `references/methodology/five-whys-template.md`.

## Findings

(One subsection per cluster. Order by ICE score descending.)

### F<n> — <Cluster title>

**Symptom (one line):** <…>

**Frequency:** <e.g., "11 alerts in 30d, 3 distinct alert_hashes, all known-issue-recurrence">

**Triage-bot evidence:**
- `kb/incident-log.jsonl` lines <l1>, <l2>, <l3> (alert_hash=<h>, channel=<c>)
- `docs/investigations/<file1>.md` — <one-line takeaway>
- `kb/known-issues.json#<id>` (occurrences: <n>; fix_status: <s>)

**Fresh DD evidence:**
- Monitor <id> "<name>" — <state, last_triggered_ts>. URL: <…>.
- Metric `<query>` — <delta vs 24h baseline>. URL: <…>.

**Fresh ES evidence:**
- Aggregation `<query>` over `<index>` — <top buckets>. Kibana URL: <…>.

**Five-whys:**
(Insert per `references/methodology/five-whys-template.md` shape.)

**Calculations** (formulas: `references/methodology/metrics-formulas.md`):
| Metric | Value | Note |
|---|---|---|
| Frequency | <n>/month |  |
| MTTR | <minutes> | mean(close_ts − open_ts) over <n> incidents |
| Availability impact | <%> | vs window denominator |
| Error budget burn | <%> | vs <SLO target>% target |
| Blast radius | <users / tenants> | derived from log volumes |

**Similar Jira (read-only cross-reference):**
- <KEY-NNNN>: "<summary>" — status: <…>, assignee: <…>
- <KEY-NNNN>: "<summary>" — status: <…>
- (or: "no similar tickets found via JQL: `<query>`")

**Recommendation:**
- <a> <action>
- <b> <action>
- <c> <action>

**Course module references:**
- `level-N/<slug>.json` — <principle applied>
- `level-M/<slug>.json` — <principle applied>

**ICE score:** Impact <1-10> · Confidence <1-10> · Effort <1-10> → **<score>**.
(Formula: I × C ÷ E.)

---

### F<n+1> — <next cluster>

…

## Trend Analysis

(Skip the section if no prior report exists. Otherwise:)

| Metric | Last month | This month | Δ |
|---|---|---|---|
| Total alert clusters | <…> | <…> | <…> |
| % known-issue-recurrence | <…> | <…> | <…> |
| Top-3 alert_hash by frequency | <…> | <…> | (compare) |
| Listed-services availability avg | <…> | <…> | <…> |

**Status of prior recommendations:**
- F1 from `stability-reviews/YYYY-MM-prior/report.md`: <implemented / in-flight / unaddressed> — evidence: <…>.
- F2 from prior report: <…>.

## Open Follow-ups

(Anything escalated across multiple runs without resolution. Threshold: 2+ consecutive months unaddressed.)

- <Cluster title> — first surfaced YYYY-MM, still <unaddressed / in-flight>. Recommended escalation: <to whom>.

## Appendix: raw queries

(For reproducibility. Verbatim queries used by the routine, with timestamps.)

```bash
# DD monitors search
python scripts/dd_search.py monitors --tags "service:<svc>,env:prod" --state Alert --state "No Data"

# DD log aggregation
python scripts/dd_search.py logs --query "<…>" --from <epoch> --limit 100

# DD metric query
python scripts/dd_search.py metric --query "<…>" --from-unix <…> --to-unix <…>

# ES error aggregation
python scripts/es_search.py --query "<…>" --from <…> --to <…> --aggregate <…>

# Jira JQL (read-only)
mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql cloudId=<…> jql='<…>'
```
```

## Idempotence

If `stability-reviews/<YYYY-MM>/report.md` already exists when the routine runs (manual trigger after a scheduled run, or a re-run for any reason), overwrite it but prepend a header:

```
> _Updated <ISO-8601 ts> — superseding earlier run_
```

The latest run is canonical. Earlier runs are preserved in git history.
