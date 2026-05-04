# Recommendation rubric — ICE scoring

Used to rank recommendations in `stability-reviews/YYYY-MM/report.md`. Higher ICE = higher priority.

```
ICE = (Impact × Confidence) / Effort
```

Each component is rated 1-10. The formula intentionally weights **Effort** in the denominator — a high-impact, high-confidence change blocked by a year of work loses to a medium-impact change you can ship in a sprint.

## Impact (1-10)

How much pain this recommendation removes if implemented.

| Score | Calibration anchor |
|------:|-------------------|
| 1     | Cosmetic. Eliminates a low-frequency low-severity nuisance. |
| 3     | Removes one minor recurring class of alert noise (e.g., a known false-alarm). |
| 5     | Eliminates a medium-frequency known-issue-recurrence (10-30 alerts/month, low MTTR). |
| 7     | Eliminates a high-frequency or high-MTTR known-issue (50+ alerts/month, OR MTTR > 30 min × 2+ incidents/month). |
| 9     | Prevents a P0/P1-class outage with confirmed historical occurrence. |
| 10    | Prevents data loss, security breach, or platform-wide unavailability. |

Multi-cluster recommendations (one fix removes multiple findings) score on the *combined* pain removed.

## Confidence (1-10)

How sure we are the recommendation will work as intended, *not* how sure we are about the diagnosis.

| Score | Calibration anchor |
|------:|-------------------|
| 1     | Speculative. No analogue, no evidence the proposed change works. |
| 3     | Plausible by analogy to one similar system; not previously tried at Method. |
| 5     | The pattern is documented in industry literature (course module, Wikipedia, vendor docs); no Method-specific evidence. |
| 7     | Method has used this pattern elsewhere (cite the service or doc); evidence it works in our context. |
| 9     | Direct evidence: the change has been done in a related Method service and the data shows it removed the failure mode. |
| 10    | Reserved for changes that simply add monitoring of a known signal — instrumenting a metric is near-certain to surface what's there. |

Confidence is not a measure of certainty about the **diagnosis** (the 5-whys trace handles that). It is a measure of certainty about the **fix**.

## Effort (1-10)

Engineering cost from "decision made" to "in production".

| Score | Calibration anchor |
|------:|-------------------|
| 1     | Configuration change or single-line edit. < 1 day. |
| 3     | One file or one DD monitor + runbook entry. < 1 week. |
| 5     | Touches multiple services or requires a small-scale data migration. ~1-2 weeks. |
| 7     | New subsystem or significant refactor. 1-2 sprints. |
| 9     | Cross-team initiative requiring product input or third-party coordination. ~1 quarter. |
| 10    | Architectural rewrite. Multi-quarter. |

For Effort, score conservatively. The cost of underestimating is the recommendation slipping out of priority order; the cost of overestimating is the team challenging your number, which is fine.

## Score interpretation

| ICE range | Action |
|-----------|--------|
| ≥ 20      | Top of the report. Implement first. |
| 10-19     | Solid. Should make the next planning cycle. |
| 5-9       | Worth tracking; consider when adjacent work is happening. |
| < 5       | Surface for awareness; don't actively push. |

The cutoff between top-5 and the rest is set by **score order, not by score threshold**. Rank, then take 5.

## Worked example

**R1 — Add liveness alerting on `Runtime.Core.Subscriber.Agent`**

- Impact: 8. Removes a known-issue-recurrence with high blast radius (cache stale → every active account during the window sees stale UI). Not 9 because availability impact is small per-incident; not 7 because the pain is platform-wide.
- Confidence: 9. Adding a no-data monitor is a documented Method pattern; we know exactly what metric to watch and what the threshold should be.
- Effort: 3. New DD monitor (config), one runbook entry, one entry in `references/architecture/known-failure-modes.md`.
- ICE = `(8 × 9) / 3 = 24`. Top of the report.

**R5 — Define explicit SLOs for top 3 critical flows**

- Impact: 9. Prerequisite for the rest — without SLOs the calculations have no denominator.
- Confidence: 8. The pattern is well-documented (level-1/availability-and-slas.json, level-10/observability.json). Method has not formally adopted SLOs yet, hence not 9.
- Effort: 6. Cross-team work: requires SRE/observability owner, instrumenting error-budget burn, getting buy-in. ~1-2 sprints.
- ICE = `(9 × 8) / 6 = 12`.

R1 (ICE 24) ranks above R5 (ICE 12) despite R5 being a prerequisite, because R1 is shippable now and R5 needs a quarter of cross-team work. The report should still call out the prerequisite relationship in the recommendation text.

## Calibration drift

The rubric is calibrated against the team's own follow-through. If recommendations with ICE ≥ 20 routinely don't ship, Effort is being scored too low. If recommendations with ICE 5-10 routinely ship and remove pain, Impact is being scored too low. The next stability review's "Trend Analysis" section is the place to flag drift.
