---
status: placeholder
created_on: 2026-06-10
created_by: triage-bot
incident_date: 2026-06-04
service: ms-account-api
severity: P0
counts_toward_availability: true
related_ki:
  - ki-ms-account-api-cluster-info-deploy-failure
  - ki-microservices-method-int-upstream-502-bad-gateway
  - ki-html-error-response-newtonsoft-deserialize-pattern
---

# ms-account-api ClusterInfo deploy regression — 2026-06-04

## Title
ms-account-api `V3ClusterController.GetAccountClusterInfoAsync` deploy regression caused cascading 502s through MSAuth, MSIdentity, runtime-core, and gateway-routed tenant traffic.

## Duration
**2026-06-04 12:59 UTC → 14:09 UTC (08:59–10:09 EDT). ~70 minutes platform impact.**

The active customer-facing window is 12:59 UTC (first Nelson De Miranda swat post: "502 errors on runtime loads") to 14:09 UTC (Nelson confirms "Feels like we're back online?"). The actual unhealthy-deploy window may extend earlier — ms-account-api's bad deploy artifact was running before any user noticed.

## Impact
- Cross-cluster tenant routing broken: every service that asked ms-account-api "which SQL cluster does account X live on?" got a failure response. Downstream services with no fallback flooded retry queues.
- Customer-visible symptoms: 502s on screen loads, blank screens, auth retries, sign-in delays.
- Cumulative log signature in ES during the window:
  - 6,892 × `Error Fetching Release Feature Flag: V1TokenSessionHardening` (downstream symptom — AuthService unable to call ms-account-api for token-cache lookups)
  - 88 × `Unexpected character encountered while parsing value: <` (Newtonsoft choking on HTML 502 body)
  - 75 × `Error Calling Url: http://microservices.method.int/...Statuscode: BadGateway`
  - 68 × `MSAuth Call Failed. StatusCode:502 Message:<html>...`
  - 40 × `Could not determine DbClusterKey`
  - Multiple per-account `Connect on AlocetSystem,<account>: Could not fetch ClusterInfo from account microservice`
- Two ms-account-api Datadog monitors transitioned to OK at 14:15Z (high p90 latency, high average latency) ~7 min after human-confirmed recovery.

## Customer impact (best estimate)
All customers attempting interactive use during the window were affected. The ms-account-api `ClusterInfo` lookup is on the hot path of every cross-tenant request — sign-in, screen load, action execution, sync. Estimated tens of thousands of impacted users for ~70 minutes.

## Root cause
ms-account-api deploy artifact running 12:59–14:03 UTC broke the AlocetSystem `V3ClusterController.GetAccountClusterInfoAsync` endpoint at `account/Account.Api/Controllers/v3/V3ClusterController.cs`. Two candidate deploys from the prior 3 days:

- **PR #1014 (PL-62800, merged 2026-05-29)** — Health-check rework. Touches `Account.Api/Startup.cs` extensively: BsonSerializer.RegisterSerializer wrapped in `try/catch(BsonSerializationException) when (env == "Test")`; Hangfire-Mongo registration gated by `if (!Test)`; `config.AddAwsSecrets` gated by `if (!Test)`; new `services.AddSingleton<BuildMetadata>()`; multiple re-indented blocks. **High-risk startup-wiring surface.** A regression here would cause IIS worker processes to come up unhealthy on rollout, and the LB would round-robin between healthy and unhealthy workers — producing exactly the intermittent 502 pattern we saw.
- **PR #1013 (PL-62910, merged 2026-06-02)** — IDOR fix re-release. Touches `AccountStatusController.cs` (whitespace) and `AccountStatusService.cs` (+15/-3, added pre-existence authorization check, changed `CheckSecurity(Guid)` to `CheckSecurity(Guid, string)`). Cancel-Account flow, not ClusterInfo. Lower risk for this specific failure mode.

**Confidence on which PR**: PR #1014 is the higher-likelihood candidate. PR #1013 only touches the Cancel-Account flow which isn't on the ClusterInfo hot path.

**Confidence-gap requires engineering action to close**:
1. Find the TFS Build ID that ran 2026-06-04 morning and which commit it ran against. (Method deploys via Azure DevOps / TFS, not GitHub — `gh api` is blind. Build paths in stack traces like `D:\TFSAgent5\_work\142\s\AuthService\...` confirm TFS.)
2. Determine whether the deploy carried PR #1013 alone, PR #1014 alone, or both.
3. Pull IIS w3wp.exe Application Event Log (Event ID 1000 / 1001 / 1026 — .NET unhandled-exception events) from MSL03/04/05 around 13:00 UTC.

## Resolution
- 13:11 UTC: engineers rolled back ms-preferences-api first (wrong target — did NOT resolve)
- 13:26 UTC: rolled back additional services
- 14:03 UTC: **Yuri reverted ms-account-api**
- 14:08 UTC: Nelson "Feels like we're back online?"
- 14:09 UTC: backend confirmed restored; status page updated
- 14:15 UTC: ms-account-api DD latency monitors transition to OK

The ms-account-api revert was the resolving action. Recovery time from revert to confirmation was ~5 minutes.

## What this PIR cannot determine without engineering action
- Exact deploy SHA / TFS Build ID
- Whether the regression was PR #1013, PR #1014, or both
- Why ms-account-api was silent in DD APM during the failure window (possible candidates: logs going to file-only and the file-tail collector didn't catch crash logs before the file rotated; logs not shipping at all; service crashed before drain; DD APM retention artifact)
- Whether IIS w3wp recycle counts on MSL03/04/05 spiked during the window

These are the specific asks for the engineering team for the formal Confluence PIR.

## Placeholder status
**Placeholder — no Confluence PIR found in `.claude/pir-parsed.json` as of 2026-06-10.** Created so next stability-review (2026-07-07) counts this incident toward downtime instead of silently undercounting the 70-minute window.

When a real Confluence PIR is published, replace this file's frontmatter with `status: superseded` and the Confluence link.

## Cross-references
- KB: `ki-ms-account-api-cluster-info-deploy-failure`
- KB: `ki-microservices-method-int-upstream-502-bad-gateway`
- KB: `ki-html-error-response-newtonsoft-deserialize-pattern`
- Investigation: bot's 2026-06-04 swat investigation in `docs/investigations/` (if present)
- Memory: `feedback_investigation_lessons_2026_06_04.md` (rules 1–5)
- #swat thread: 2026-06-04 08:59 EDT onward, channel C01L5K42GQ6
