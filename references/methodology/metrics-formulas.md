# Metrics formulas

Reference for Phase 7 of `stability-review-prompt.md`. Every calculation in `stability-reviews/YYYY-MM/report.md` derives from one of these formulas. Show the substitution in the report so the reader can verify.

## Window conventions

- Default window: trailing 30 days (`now - 30d` to `now`), expressed as Unix epoch seconds.
- Total minutes in window: `30 × 24 × 60 = 43,200`.
- Total seconds in window: `30 × 86,400 = 2,592,000`.
- An "incident" = one continuous interval of unhealthy state. Two crashes 5 minutes apart in the same monitor are two incidents only if the monitor recovered between them.

## Availability

Definition: fraction of the window during which the service met its SLO.

```
A = (window_minutes - downtime_minutes) / window_minutes
```

Conversion to nines (round to 4 decimal places):

| Availability | Allowed downtime / 30d |
|--------------|------------------------:|
| 99% (two-nines)        | 432 min (7.2h) |
| 99.9% (three-nines)    | 43.2 min       |
| 99.95%                 | 21.6 min       |
| 99.99% (four-nines)    | 4.32 min       |
| 99.999% (five-nines)   | 25.9 sec       |

**Worked example (Subscriber.Agent):** Two outages in 90 days, ~45 min each → 90 min downtime in 90 days = 30 min in the trailing 30d window (proportional). `A = (43,200 − 30) / 43,200 = 0.99931 ≈ 99.93%`.

## Mean Time To Recovery (MTTR)

```
MTTR = sum(recovery_ts - open_ts) / count(incidents)
```

Sources:
- DD monitors: `last_triggered_ts` from `get_monitor.py --summary` (state: Alert) and the monitor's transition to OK.
- `kb/incident-log.jsonl`: per-cluster, infer open from the first occurrence in the cluster window and recovery from the next clean classification.
- Jira incident tickets (if used by the team): `created` and `resolutiondate` fields.

**Worked example:** 4 incidents with durations 12, 18, 30, 60 min → MTTR = 120/4 = **30 min**.

Edge cases:
- If an incident is still ongoing at window end, exclude it from MTTR (it inflates artificially) but include it in availability impact (treat the open duration as downtime through window end).
- If the routine cannot recover the recovery timestamp, mark MTTR as `(undetermined)` and record only frequency.

## Mean Time Between Failures (MTBF)

```
MTBF = total_uptime_minutes / count(incidents)
```

Less central than MTTR for a stability review, but useful when discussing whether a fix that doubled MTBF is worth the engineering cost.

**Worked example:** 4 incidents in 30 days, total downtime 120 min → uptime 43,080 min → MTBF = 43,080/4 = **10,770 min ≈ 7.5 days**.

## Error budget burn

Definition: fraction of the SLO's allowed downtime budget consumed in the window.

```
budget = (1 - SLO_target) × window_minutes
burn   = downtime_minutes / budget
```

A burn > 100% means the budget is exhausted. A burn < 33% means the SLO is loose (the service is far better than required — fine, but verify the SLO isn't aspirational).

**Worked example (Subscriber.Agent vs proposed 99.9%):**
- Budget = `(1 − 0.999) × 43,200 = 43.2 min`.
- Downtime = 30 min (from above).
- Burn = `30 / 43.2 ≈ 69%`.

If you instead propose 99.99% (four-nines): budget = 4.32 min, burn = `30 / 4.32 ≈ 694%`. Hence the recommendation to set the SLO at 99.9% — 99.99% is too tight for an event-driven background consumer.

## RPO and RTO (for DR / data-loss scenarios)

- **RPO (Recovery Point Objective):** the maximum tolerable amount of data loss, measured in time. "We can lose up to 5 minutes of writes."
- **RTO (Recovery Time Objective):** the maximum tolerable time the service can be unavailable.

These appear in recommendations where the cluster surfaced a backup/replication gap. Cite proposed RPO/RTO targets per service in `references/architecture/known-failure-modes.md`.

## Blast radius / impact

Estimate of the number of users (or tenants) affected during an incident.

```
blast = downtime_minutes × affected_users_per_minute
```

Where `affected_users_per_minute` derives from log volume during the window divided by minutes:

```
affected_users_per_minute ≈ unique_account_ids_in_logs / window_minutes
```

For multi-tenant Method:
- A single-tenant outage: `affected_users_per_minute = 1` (one account).
- A SQL cluster outage: `≈ count(accounts on that cluster)`.
- A gateway outage: `≈ count(active accounts platform-wide)`.

Pull cardinality from `scripts/sql_query.py --template account-lookup` or from DD logs aggregated by `@MainAccount`.

**Worked example:** Subscriber.Agent stop affected `tables-fields.view.change` consumption — every active account hitting any cached screen during the 30 min sees stale data. If 1,200 accounts are active, blast ≈ `30 × 1,200 = 36,000 user-minutes` of stale UX.

## ICE score (recommendation rubric)

```
ICE = (Impact × Confidence) / Effort
```

Each component is rated 1-10:
- **Impact**: how much pain this recommendation removes (incidents prevented × severity).
- **Confidence**: how sure we are the recommendation will work (evidence quality + analogues).
- **Effort**: engineering cost (1 = a few lines; 10 = a quarter of work).

Higher is better. See `references/methodology/recommendation-rubric.md` for component definitions and calibration anchors.

## Reporting precision

- Availability: 2 decimal places, never round up. `99.9999%` is dishonest unless you have 99.99% measurement.
- MTTR: 1 decimal place if minutes. Round to whole hours when MTTR > 90 min.
- Burn: integer percent. Burn 67.4% reports as `67%`.
- ICE: 1 decimal place. `8.4`, not `8.428571…`.

If a metric cannot be computed because the data isn't there, say so explicitly: `MTTR: undetermined (recovery timestamps not in incident-log)`. Do not invent.
