# Method platform availability — trailing 14 days

**Window:** 2026-05-27 00:00 UTC → 2026-06-10 00:00 UTC (14 days, 20,160 minutes)
**Author:** triage-bot ad-hoc review
**Generated:** 2026-06-10
**Reason for ad-hoc report:** Ben asked for an audit of post-incident reports because he didn't believe the most recent headline. Audit confirmed two material incidents in this window with no published Confluence PIRs as of generation date. Placeholder PIRs filed at `stability-reviews/pir-placeholders/`. This report folds those placeholders into a fresh honest availability calculation.

## Headline

**Trailing-14-day customer-perceived availability: ~99.05%** (n=2 incidents, 190 min impact).

This is **0.85 percentage points below the 99.9% peer norm** and **0.29 pp below the most recent monthly stability-review headline of 99.34%** (windowed 2026-05-01 → 2026-05-25). The two windows don't overlap — the trailing 14 days are entirely new data, not a redoing of the May calculation.

The deterioration is **concentrated** in two named deploy-driven incidents, not distributed across systemic infrastructure failure. Both incidents had identified root causes and engineer-applied resolutions on the day of occurrence.

## Industry comparison

| Tier | Annual downtime budget | Per-14-day budget | Representative peers |
|---|---|---|---|
| 99.99% | 52 min/yr | 2.02 min | AWS S3, Cloudflare, Stripe |
| 99.95% | 4 h 23 min/yr | 10.08 min | Atlassian Enterprise, ServiceNow |
| 99.9%  | 8 h 45 min/yr | 20.16 min | Salesforce, HubSpot, Intuit QBO, Zoho — Method's direct peers |
| 99.5%  | 1 d 19 h/yr   | 100.8 min | Below industry |
| 99.0%  | 3 d 15 h/yr   | 201.6 min | Significantly below |

**Method this 14 days: 190 min downtime → 99.05% → just barely above the 99.0% floor and well below 99.5%.** This is **two notches below the 99.9% Method-peer norm**. If we exclude the 06-05 UI-only impairment (debatably not a platform-availability event), the figure improves to 99.65% — still below peer norm.

## Methodology

### What counted

| Date | Incident | Service(s) | Duration | Counted as |
|---|---|---|---|---|
| 2026-06-04 | ms-account-api ClusterInfo deploy regression | ms-account-api → cascade to MSAuth, MSIdentity, runtime-core, gateway | 70 min (12:59–14:09 UTC) | Full platform downtime |
| 2026-06-05 | m-one no-code reference-grid render regression | method-platform-ui (m-one) | 120 min (13:00–15:05 UTC) | UI-only impairment |

### What did NOT count

| Date | Event | Why excluded |
|---|---|---|
| 2026-05-27 | Support case re storage limits on account "certusa" | Customer data/account issue, not platform availability |
| 2026-06-04 evening | Two singleton legacy-Classic errors at 19:35–20:05 UTC | Tier-3 legacy, not critical-path; no impact on {gateway, auth, runtime-core, tables-fields} union |
| 2026-06-08–10 | miurl.cc antivirus false-positive (Avast/Norton flagged short URL domain) | Third-party antivirus issue; workaround applied via m.method.me domain switch. Not Method platform downtime. PL-63508 |

### Calculation

```
total_window_minutes        = 14 × 24 × 60        = 20,160
downtime_minutes (06-04)    = 70
downtime_minutes (06-05 UI) = 120                 (UI-only — see sensitivity below)
total_downtime_minutes      = 190
availability                = (20160 − 190) / 20160 = 0.99057 ≈ 99.05%
```

**Sensitivity:** if the 06-05 grid-rendering UI bug is excluded (treating "backend healthy + actions still fire" as not platform-down), availability rises to **99.65%** (70 min over 14 days). Either way, this trails the 99.9% Method-peer norm.

### Why the May 25 report is different

`stability-reviews/2026-05/2026-05-25-availability-since-inception.md` reported **99.34% customer-perceived** and **99.89% sign-in-strict** across 24 days (2026-05-01 → 2026-05-25). Ben's recalled "99.9%" was almost certainly the sign-in-strict sub-metric. There is no honest customer-perceived 99.9% claim in any current report.

The May 25 window doesn't overlap this report's window; the headlines aren't contradictory, they're sequential. But the trend is **downward**: 99.34% → 99.05% over 14 days is meaningful, not noise.

## Concentration vs distribution call

Both incidents in this window were **deploy regressions discovered in production**, not infrastructure failure:

- **2026-06-04**: ms-account-api deploy artifact running 12:59–14:03 UTC broke the AlocetSystem `V3ClusterController.GetAccountClusterInfoAsync` endpoint. Rollback of ms-account-api at 14:03 UTC resolved within 5 min. Two PR candidates (PR #1013, PR #1014) for the regression; PR #1014's startup-wiring rework is the higher-risk surface.
- **2026-06-05**: method-platform-ui m-one no-code grid-rendering regression broke reference-grid column display. Rollback resolved within ~21 min. NCNG-1445.

Pattern is **"deploys are landing breakage in prod"**, not "infrastructure is degrading." The May 25 report's recommendations around canary deploys, deploy-correlated DD events, and traffic-drop monitors remain the right direction — and the 14 engineering recommendations from the 2026-06-04 root-cause analysis (Polly circuit breakers, Content-Type validation, ClusterInfo stale-while-revalidate cache, TFS→DD deploy events, etc.) directly address this concentration. None have been filed as Jira tickets yet; that's the gap.

## Annualization caveat

**Do not annualize this 14-day number to "99.05% annually."** Two incidents in 14 days is a tiny sample. Two ways this could be misleading in either direction:

- **Pessimistic mis-annualization**: 190 min / 14d × 365d = 4,957 min/yr ≈ 99.06% — only valid if incidents continue at this rate, which assumes the deploy-regression pattern is sustained. Even one perfect month would pull the annual figure significantly above the trailing-14-day number.
- **Optimistic mis-annualization**: assuming the two incidents are flukes and the rest of the year will see zero downtime is also wrong — the May 25 report's 99.34% over a longer window is the lower-variance estimate.

The honest framing: **the trailing 14 days were below peer norm because of two concentrated deploy regressions; the annual figure is more likely in the 99.3–99.6% band based on the longer 25-day May window, which is still below the 99.9% peer norm**.

## What this report does NOT close

1. **The formal PIR gap.** Two material incidents (2026-06-04, 2026-06-05) lack Confluence-published PIRs as of 2026-06-10. Placeholders are filed at `stability-reviews/pir-placeholders/` so the next stability-review counts them. Engineering should publish formal PIRs and replace the placeholders.
2. **The 14 engineering recommendations from 2026-06-04 are not in Jira.** They're tracked only in this repo's plan file. The stability-review process will be upgraded (separate commit) to add a Phase 3c recommendation-tracker that requires Jira tickets per recommendation to be visible by the next monthly review.
3. **The root cause of 2026-06-04 down to a specific TFS Build ID** requires engineering action — `gh api` is blind to Method's Azure DevOps / TFS deploys, and ms-account-api logs during the failure window are absent from DD APM (likely a log-shipping gap). See the placeholder PIR for the specific asks.

## Reference

- `stability-reviews/pir-placeholders/2026-06-04-ms-account-api-cluster-info-deploy.md`
- `stability-reviews/pir-placeholders/2026-06-05-m-one-grid-rendering-regression.md`
- `stability-reviews/2026-05/2026-05-25-availability-since-inception.md` (prior window, 99.34% headline)
- `kb/known-issues.json` — `ki-ms-account-api-cluster-info-deploy-failure`, `ki-microservices-method-int-upstream-502-bad-gateway`, `ki-html-error-response-newtonsoft-deserialize-pattern`
- Memory rule: `feedback_report_industry_framing.md`
