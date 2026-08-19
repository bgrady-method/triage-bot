# Investigation outcomes

What a finished investigation is *for*. `classification.md` decides which bucket an alert lands in; this file says what the investigation must leave behind regardless of bucket.

**This is a rubric, not a schema.** Nothing here is a field to fill or a section to emit. It's the standard an investigation is judged against — including by the tuning harness (`scripts/eval/`), which scores candidate approaches on these dimensions. Expect this file to be revised by what that tuning learns.

## The test that matters

> Could an engineer who has never seen this alert act from this report alone?

Not "is it accurate" — accurate and useless is a real failure mode. The report is a **handoff to a stranger**. Anyone who picks it up (Ben, the owning team, a future cycle re-reading the KB) should be able to act without redoing the discovery.

## The five outcomes

| # | Outcome | What good looks like | What fails |
|---|---|---|---|
| 1 | **Root cause** | The *mechanism*. "The v182 bundle declares a `Name` field that already exists on that view, so tables-fields rejects it with HTTP 400 / ErrorCode 50" | "tables-fields is throwing 400s" — that's the symptom restated |
| 2 | **Resources** | Links whose queries actually return rows; the right datasource for the signal | A Kibana link attached by reflex to a latency-only, DD-sourced finding |
| 3 | **Next steps** | Ordered, concrete, executable without further discovery | "Check the logs", "investigate further", "monitor the situation" |
| 4 | **Possible resolutions** | Candidates with tradeoffs + confidence, or an explicit "needs human design" | Silence — leaving the reader to invent the fix from scratch |
| 5 | **Verdict** | Action required now / later / not at all, **and why**. This is what the gate consumes. | A classification with no statement of what the reader should do about it |

Plus the sixth thing that makes the other five trustworthy: **honest unknowns**. What's still open, what was *tried*, why it failed. A gap that survived three targeted attempts is a much stronger `needs-human` than one nobody probed.

## Depth scales with the class — terse is not shallow

Measured on 2026-07-15: `needs-human` reports ran 76 and 108 lines; the 18 `known-issue-recurrence` reports ran ~51 lines each. **That is correct behaviour, not a defect.** A known issue with a written playbook doesn't need its mechanism re-derived every hour — it needs to be *matched correctly* and counted.

The outcomes still apply to a recurrence; they're just mostly inherited from the KB entry. What a recurrence report must add is the thing the KB can't know: **did this occurrence actually match, and did anything change?**

## Exemplar

`docs/investigations/2026-07-15-2bc49da0e23cdcf0.md` (Sales Orders v182 push storm) is the reference for a `needs-human` report. It earns each outcome:

- **Root cause** with a timing chain: publish at 13:13:13.53Z → first bundle failure 3.7s later → first Redis circuit-breaker **10s after that**, which is how it establishes Redis as an *effect*.
- **Resources**: ES aggregations and DD metric queries with actual numbers (5,571 started / 170 failed; 4.5× volume; p95 10.72s), each traceable.
- **Next steps**: five, ordered, each actionable — atomic bundles, throttle the fan-out, reconcile the 196 accounts, add a job-failure monitor, KB hygiene.
- **Resolutions** with the owning team named as inert text (Hard rule #13).
- **Verdict**: `needs-human` @ 0.88 — correct, because the fix is architectural, not single-file.
- **Unknowns**: says plainly it can't distinguish *why* those 196 accounts collide, names both candidate mechanisms, and says which tool would settle it.

Note what it does **not** do: it doesn't inflate confidence to look decisive, and it doesn't reach for `new-with-clear-fix` because the honest fix spans design, not a line.

## Anti-patterns

Each of these has actually happened. They're the reason this file exists.

1. **Symptom as root cause.** "Gateway 5xx" is where the investigation starts, not where it ends.
2. **Dead links.** A link whose backing query returns nothing costs the reader time and teaches them to distrust every other link in the report. Verify the query returns rows, and use the datasource that carries the signal — DD APM for latency-only findings.
3. **Bare monitor-id matching.** Three KB entries bare-matched the push storm on `monitors/<id>` and **all three were wrong** — inverted causality, wrong service, and real-but-independent. A monitor id is not a signature.
4. **Zero-corroboration recurrence.** `4d6fa5f4` (2026-07-15) bumped a KB entry to occurrence #19 on an evidence query returning **0 hits**, at confidence 0.7, and posted. A match with no evidence isn't a match; it's a guess with a KB id attached.
5. **Cause/effect inversion.** Verify the proposed cause *precedes* the effect. Redis looked causal until the timestamps were ordered.
6. **Sampling artifacts read as concentration.** A `--limit 5` log sample can look account-concentrated by chance. Widen before concluding.
7. **Trusting the alerting service.** The service whose monitor fired is often a bystander. The push storm fired monitors on tables-fields and runtime-core-api; the culprit was `app-update-agent`, which had no monitor at all.

## Relationship to the gate

The verdict is the interface. The gate (`prompt.md` step 7) decides *who hears about it*; this rubric governs whether the verdict deserves to be believed. A gate resting on a weak verdict is worse than no gate — it suppresses confidently.
