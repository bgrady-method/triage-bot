---
name: stability-five-whys
description: "Run a structured 5-whys + SLO analysis for the monthly stability-review routine. TRIGGER: invoke from the stability-review routine when synthesising a top recurring incident pattern from the previous month's incident-log. Walks the canonical methodology refs (five-whys-template, recommendation-rubric, postmortem-template, metrics-formulas) so the report uses Method-standard structure and metrics."
allowedTools: [Read]
---

# stability-five-whys — monthly stability-review methodology

The monthly stability-review routine analyses the prior 30 days of `kb/incident-log.jsonl` plus the `docs/investigations/` reports, and produces a dated markdown report under `stability-reviews/<YYYY-MM>/<YYYY-MM-DD>-report.md`. This skill bundles the methodology refs the routine should use.

## When to use

Inside the stability-review routine, in the synthesis phase — when you've identified a top recurring pattern (e.g. "X service had Y errors over 30 days, peaked on Z deploys") and need to:

- Run a 5-whys drill-down on the root cause
- Compute SLO impact / golden-signal deltas with Method's standard formulas
- Frame the recommendation against Method's recommendation rubric (severity × cost × effort)
- Produce a postmortem-shaped section in the report

## How

Read these refs (paths relative to repo root):

| Ref | When to use |
|---|---|
| `references/methodology/five-whys-template.md` | Root-cause drill-down for any recurring pattern (≥3 occurrences in 30 days) |
| `references/methodology/recommendation-rubric.md` | Scoring + ranking the recommendations the report ends with |
| `references/methodology/postmortem-template.md` | Long-form section structure when one pattern warrants its own postmortem |
| `references/methodology/metrics-formulas.md` | SLO % / error-rate / p95-latency / availability calculations |

Plus `references/architecture/known-failure-modes.md` for cross-checks against patterns we already know about.

## Hard rules

1. **No human prompt.** Stability-review is unattended. Anywhere the methodology says "discuss with the team," substitute "flag uncertainty in the report itself with `> [needs human review]:` markers and continue."
2. **Cite incident-log lines and investigation reports inline.** Every claim in the report needs a `[hash]` reference back to the source.
3. **One report per fire**, dated. Never overwrite a prior month's report — investigate-then-append, not edit-in-place.
4. **Conservative mode applies if `wc -l kb/incident-log.jsonl` < the threshold in `kb/config.json.stability_review.conservative_until`** — when conservative, mark recommendations as `tentative` and require ≥2 corroborating data sources.

## Reference

This skill is a wrapper that points at the methodology files. Update those files when the methodology changes; update this SKILL.md only when the *list of refs* changes.
