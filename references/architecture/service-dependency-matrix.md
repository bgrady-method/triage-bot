# Service × dependency matrix

> ⚠ **FALLBACK ONLY.** This file is a derived snapshot, not a source of truth. **Always prefer reading [methodcrm/DeveloperTools `method-infrastructure/08-interdependencies.md`](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md) directly** (via `gh api 'repos/methodcrm/DeveloperTools/contents/method-infrastructure/08-interdependencies.md?ref=bgrady/global-skills-export' --jq '.content' | base64 -d`). Use this file only when 08-interdeps is unreachable (GitHub down, no network), or when you need the at-a-glance H/S/A grid that 08-interdeps doesn't provide. **Per-service `CLAUDE.md` (in each `methodcrm/<repo>` repo, on `master`) wins over both for that service's specific stack.**

Used by `stability-review-prompt.md` Phase 6 (architecture lens). Tells the routine which backing stores a service can lose tolerantly vs which constitute hard dependencies — but only as a fallback to 08-interdeps.

**Drift risk.** This file is hand-maintained; it lags 08-interdeps by definition. If 08-interdeps says X and this file says Y, **08-interdeps is right and this file is stale**. Run `python scripts/dep_drift_check.py --gh` to surface drift between this file and the actual per-service `appsettings*.json` / `Web.config`.

See `service-dependency-matrix-audit.md` (sibling file) for the audit that produced this resync, and the open follow-ups (notably the "likely" cells in 08-interdeps that still need verification).

Rows: services. Columns: backing stores and other services. Cells:
- **H** = hard dependency. Service is unhealthy if this is unhealthy.
- **S** = soft dependency. Service degrades but continues (cache miss, optional feature).
- **A** = async dependency. Service writes to it; failure is buffered or retryable; user-visible only on the read side.
- **?** = uncertain ("likely" in 08-interdeps; unverified). Treat as soft until tightened.
- blank = not applicable.

## Backing stores

| Service / Worker                  | SQL | Mongo | Redis | RabbitMQ | ES   | S3   | OAuth2/Auth |
|-----------------------------------|:---:|:-----:|:-----:|:--------:|:----:|:----:|:-----------:|
| ms-gateway-api                    |     |       |   H   |          |  S   |      |     H       |
| ms-authentication-api             |  H  |   H   |   S   |          |      |      |             |
| ms-identity-api                   |  H  |       |   ?   |          |      |      |             |
| oauth2 (IdentityServer4)          |  H  |   H   |   H   |          |      |      |             |
| runtime-core (Runtime.Core.Api)   |  H  |   H   |   S   |    A     |  S   |  H   |     H       |
| runtime-core (Designer.Core.Api)  |  H  |   H   |       |    A     |      |      |     H       |
| runtime-core (Runtime.Core.Subscriber) | S | S |   H   |    H     |      |      |             |
| runtime-core (AppUpdate.Agent)    |  H  |   H   |       |    A     |      |      |             |
| runtime-core (Apps.Api 5200)      |  H  |   H   |   S   |    A     |      |      |     H       |
| runtime-core (AI.Core.Api)        |  H  |   H   |   S   |    A     |      |      |     H       |
| runtime-core (EDA.Orchestrator.Api)|  H |   H   |   S   |    H     |      |      |     H       |
| ms-search-api (a.k.a. Method.Search) |  |       |   ?   |          |  H   |      |     H       |
| ms-tables-fields-api              |  H  |       |   H   |    H     |      |      |     H       |
| ms-account-api                    |  H  |   H   |   ?   |    A     |      |      |     H       |
| ms-tags-api                       |  H  |   H   |   S   |    A     |      |      |     H       |
| ms-preferences-api                |  H  |   H   |   S   |    A     |      |      |     H       |
| ms-documents-api                  |  H  |   H   |   S   |          |      |  H   |     H       |
| ms-email-api ⚠️                    |  H  |   H   |   S   |    A     |      |      |     H       |
| ms-scheduler-api ❓                |  H  |       |       |    A     |      |      |     H       |
| ms-support-api                    |  H  |       |   ?   |          |      |      |     H       |
| ms-analytics-api                  |  H  |       |       |    H     |  ?   |      |     H       |
| qbo-sync-api                      |  H  |       |   ?   |    H     |      |      |     H       |
| qbo-webhooks-api                  |  H  |       |   ?   |    H     |      |      |     H       |
| ms-reminder-agent                 |  H  |       |       |    H     |      |      |             |
| legacy-email-agent                |  H  |       |       |    A     |      |      |             |
| legacy-authentication-api         |  H  |       |   ?   |          |      |      |             |

⚠️ ms-email-api: 02-services.md tags this `8 (inactive)`. If truly inactive, rows above should be moved to a Legacy section. See audit §2a.
❓ ms-scheduler-api: no per-service `CLAUDE.md` and blank health URL in 02-services.md. Cells inferred from generic dotnet-microservice patterns; verify before relying.

## Service-to-service hard dependencies

```
ms-gateway-api      → ms-authentication-api (JWT validate; Redis-cached)
runtime-core        → ms-tables-fields-api (no-code metadata)
runtime-core        → ms-account-api       (account registry)
runtime-core        → ms-search-api        (full-text indexing — likely)
qbo-sync-api        → runtime-core         (action execution)
ms-* (most)         → ms-authentication-api (JWT validate, Redis-cached)
ms-* (Tier 2-3)     → ms-account-api       (account metadata)
ms-tables-fields-api→ /audittrail, /analytics (writes audit + analytics events; non-blocking)
```

EDA path (async): all services publish via RabbitMQ; `EDA.Orchestrator.Api` orchestrates cross-service events. See [08-interdeps `### Async path (EDA)`](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md#async-path-eda).

## How the routine uses this matrix

When clustering Phase 2 produces a recurring failure mode for service X, Phase 6 looks up X's row to enumerate the dependency surface. The recommendation can then propose:

- **For an H column with frequent unavailability** — circuit-breaker on the dependency (`level-10/circuit-breakers-and-bulkheads.json`), retry policy review, or eliminate the dependency altogether.
- **For an S column with frequent unavailability** — soft-dependency degradation is working; verify the user impact is small and decide whether to harden.
- **For an A column with frequent unavailability** — back-pressure / DLQ depth alerting (`level-10/back-pressure-and-flow-control.json`, `level-5/message-queues.json`).
- **For a `?` column** — treat as soft, but flag the uncertainty in the recommendation. Drift-check (`scripts/dep_drift_check.py`) tightens these over time.
- **For a backing store with frequent unavailability** — multiple services share it, so the recommendation is structural (capacity, replication, replacement) rather than per-service.

## Cross-tenant blast radius

Some services are per-tenant (each request scoped to one account). Others are platform-shared. A failure in a platform-shared service has a different blast-radius shape:

| Service | Scope |
|---------|-------|
| ms-gateway-api          | platform-shared |
| ms-authentication-api   | platform-shared |
| ms-identity-api         | platform-shared |
| oauth2                  | platform-shared |
| ms-search-api           | platform-shared (index per-tenant; one ES cluster) |
| Redis                   | platform-shared |
| RabbitMQ                | platform-shared |
| Elasticsearch           | platform-shared |
| ms-account-api          | platform-shared |
| runtime-core            | per-request, but shared instance |
| Per-tenant SQL DB       | per-tenant (one cluster's DBs) |
| Per-tenant Mongo DB     | per-tenant |

A platform-shared failure → blast radius = entire active user base. A per-tenant failure → blast radius = one account.

## IIS pool blast radius (maintainer-machine fact, kept here for Phase 6)

| Pool | Services that restart together |
|------|-------------------------------|
| `microservices` | archive, calendar-sync, import, sync (synclog), tables-fields, gmailaddon, plus the bare `microservices.methodlocal.int` site |
| `legacy` | legacy-authentication-api, legacy-billingsubscription-api, legacy-intercom-api, legacy-internal-api, legacy-miurl-api, legacy-openid-api, legacy-syncservice-api, legacy-importexport-ui, legacy-method-ui, legacy-public-api, legacy-screenxml-api, legacy-reportgeneration-api |
| `runtime-core` | runtime.methodlocal.com only (Apps/Designer/RestApi run in their own pools) |

Source: [methodcrm/DeveloperTools `method-infrastructure/08-interdependencies.md` lines 109–115](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md#L109-L115). When a Phase 2 cluster names a service in one of these pools, recommend pool-isolation or per-service pools.

## Maintenance

This file is **derived**, not independently authored. Update flow:

1. When a per-service `CLAUDE.md` changes (new Redis dep, new RabbitMQ consumer, etc.), update [methodcrm/DeveloperTools `08-interdependencies.md`](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md) **first**.
2. Then resync this file from 08-interdeps.
3. Run `python scripts/dep_drift_check.py` to verify no drift remains.
4. The triage-bot's stability-review routine (Phase 6) may also append to this matrix when cluster analysis surfaces a dependency neither doc captured — annotate the new row with `(routine-discovered YYYY-MM)` so it's distinguishable from canonical 08-interdeps rows.

If 08-interdeps and this file conflict on a non-routine-discovered row, **08-interdeps wins**. Do not re-edit this file independently.
