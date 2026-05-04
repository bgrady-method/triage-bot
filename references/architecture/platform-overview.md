# Method Platform — overview for stability work

Distilled from `CLAUDE.md` (this repo) and the cloned per-service CLAUDE.md files. Read by `stability-review-prompt.md` Phase 0 to seed architectural context.

This file is a stability-flavoured digest, not a replacement for `CLAUDE.md`. The routine still reads `CLAUDE.md` directly for the canonical service catalog and call graph.

## What Method is

A multi-tenant low-code/no-code business automation platform. Customers ("accounts" or "tenants") build no-code apps through a Designer; end-users run those apps through a Runtime. QuickBooks Online is the headline data integration partner. Each customer has its own SQL database (`account_<id>`) and its own Mongo database — strict per-tenant data isolation enforced at the repository layer.

## The five-layer architecture

```
USER-FACING LAYER     App Builder · Screen Designer · Tables & Fields editor · runtime UI
        │             (method-platform-ui, method-signup-ui, method-signin-ui)
        ▼
GATEWAY / AUTH        ms-gateway-api (Ocelot) · oauth2 · ms-authentication-api
        │             JWT cache in Redis. Single point of failure for all NEW sessions.
        ▼
RUNTIME / DESIGNER    runtime-core (Runtime.Core.Api · Designer.Core.Api · Apps.Api ·
        │             Runtime.Core.Subscriber · Runtime.AppUpdate.Agent ·
        │             AI.Core.Api · EDA.Orchestrator.Api · JournalAgent · Method.Search¹)
        │             ms-tables-fields-api · ms-search-api¹ · ms-account-api · ms-tags-api · …
        │             ¹ Method.Search and ms-search-api may be the same thing — see service catalog in CLAUDE.md
        ▼
RUNTIME-LAYER STATE   MongoDB    (Apps, Screens, Controls, Events, ActionSets)
        │
        ▼
DATA LAYER            SQL Server (acc* tables = QB-mirrored business data;
                                  Spider* tables = no-code metadata;
                                  per-tenant DBs across 5 clusters C1-C5)
```

Plus:
- **Redis** — JWT cache, screen-metadata cache, rate-limit counters.
- **RabbitMQ + MassTransit** — async messaging (EDA orchestrator, AppRoutine workers).
- **Elasticsearch / Logstash** — full-text search and Serilog log sink.
- **AWS S3 + CloudFront** — file storage and CDN.

## Critical-path facts (stability lens)

These shape "is this a P0?" reasoning. Memorize.

| Failure | Effect |
|---------|--------|
| `ms-authentication-api` down       | All NEW sessions fail. Existing JWTs work until expiry (typical: ~1h). Gateway `/health/check` unhealthy. |
| Redis down                          | JWTs uncached. Every gateway request hits `ms-authentication`. Latency rises sharply. |
| `microservices.methodlocal.int` IIS site down | Every microservice virtual app gone. Whole stack effectively dies. |
| `microservices` IIS pool recycle    | `archive`, `calendar-sync`, `import`, `sync`, `tables-fields`, `gmailaddon` all restart together. |
| `legacy` IIS pool recycle           | Every legacy ASP.NET site restarts together. |
| `runtime-core` pool stopped         | Runtime, Designer, RestApi, gateway-routed `/apps` endpoints all stop responding. |
| `Runtime.Core.Subscriber` stopped | Cache invalidation halts. Users see stale screens. **No alert exists for this today.** |
| RabbitMQ broker down                | Async events back up. AppRoutines queue. Cache invalidation halts. |
| SQL cluster down                    | All accounts on that cluster offline. C1-C5 distribution is uneven. |

## Call graph (one level of detail)

```
Browser / OAuth client / Mobile
        │
        ▼
ms-gateway-api (Ocelot)
  ├─ ms-authentication-api  (JWT issue/validate; Redis-cached)
  ├─ runtime-core (Runtime.Core.Api · Designer.Core.Api · Apps.Api)
  ├─ ms-tables-fields-api   (spider* tables — no-code metadata)
  ├─ ms-account-api         (AlocetSystem registry)
  ├─ ms-documents-api       (S3-backed file uploads)
  ├─ ms-email-api           (transactional email; flagged inactive in 02-services.md)
  ├─ ms-scheduler-api       (cron-style schedules)
  ├─ ms-search-api          (Elasticsearch-backed full-text search)
  ├─ qbo-sync-api           (QuickBooks Online sync)
  └─ legacy-* APIs          (BRE, billing, sync legacy, miurl)

Service-to-service calls (peer-to-peer HTTP, NOT routed through gateway):
  runtime-core ←→ ms-tables-fields-api · ms-account-api · ms-tags-api · ms-preferences-api
  qbo-sync-api ←→ runtime-core
  ms-* ←→ ms-authentication-api (JWT validate)

Async (RabbitMQ + MassTransit):
  Designer save → tables-fields.view.change → Runtime.Core.Subscriber → Redis invalidation
  Runtime action → AppRoutine queue → Subscriber executes → SQL writes → audit events
  EDA.Orchestrator.Api fans out cross-service business events
```

## Multi-tenancy model

Every repository-layer query filters by `MainAccount`. The filter is the multi-tenancy boundary. Per-tenant SQL DBs are placed on one of 5 clusters (C1-C5) by sticky shard-key hash; tenants do not migrate clusters automatically as they grow. Per-tenant Mongo DBs are named after the account (lowercase). The `account_<id>` SQL DB and the lowercase-account Mongo DB are paired — a routine investigating "account X is broken" must check both.

`ms-account-api` owns the registry (which account exists, where it lives, what version of the platform it runs). `AlocetSystem` is the central registry DB.

## Background workers

Stability reviews must consider these explicitly because they are easy to miss in alert dashboards (don't appear in `trace.web.*` metrics):

- **Runtime.Core.Subscriber** — consumes RabbitMQ events. Critical for cache invalidation and AppRoutine execution. **No heartbeat monitor today.** (Some older docs call this `Subscriber.Agent`; the canonical name is `Runtime.Core.Subscriber` per `runtime-core/CLAUDE.md:11`.)
- **Runtime.AppUpdate.Agent** — app installation, publishing, version management.
- **legacy-email-agent** — email queue worker.
- **ms-reminder-agent** — reminder scheduler.

## Where stability lives today

- **Alerts:** Datadog monitors → `#alert-system`, `#alert-frontend-errors`, `#alert-runtime-monitoring`, `#swat`. Triage-bot polls these hourly.
- **Investigations:** This repo's `docs/investigations/<group_hash>.md` per cluster, plus `kb/incident-log.jsonl` for the structured ledger.
- **Logs:** Elasticsearch / Logstash (production), DD logs (Datadog APM-instrumented services).
- **Metrics:** Datadog APM golden signals; native NLog/Serilog → ES.
- **SLOs:** **None defined.** Performance targets exist in `runtime-core/CLAUDE.md` but are not formal SLOs.
- **DR / RPO-RTO:** **No documented targets.** Backups exist; recovery is rehearsed informally.
- **Postmortems:** **No standing process.** This routine is the first.

## Related infrastructure docs

[methodcrm/DeveloperTools `method-infrastructure/`](https://github.com/methodcrm/DeveloperTools/tree/bgrady/global-skills-export/method-infrastructure) holds the canonical infrastructure documentation. **`DeveloperTools` is not in `routines/stability-review.yaml` `repos:`** — fetch via `gh api 'repos/methodcrm/DeveloperTools/contents/method-infrastructure/<file>.md' --jq '.content' | base64 -d`. The stability-review routine reads these on demand:

| File | Read when… |
|------|-----------|
| `01-iis-inventory.md` | An IIS pool / app pool / site recycle is implicated. |
| `02-services.md` | Service catalog (40+ services, 9 tiers); pool / host / health URL lookups. |
| `03-gateway-routing.md` | Anything `ms-gateway-api` / Ocelot / JWT / CORS. |
| `04-databases.md` | SQL clusters, Mongo, Redis layout. **Always read for DB/cluster alerts.** |
| `05-auth-flow.md` | OAuth / identity / token issues. |
| `06-frontend-stack.md` | UI build / NX / CDN. |
| `07-build-and-deploy.md` | Deploy correlation, CI/CD. |
| `08-interdependencies.md` | **Read first when assessing impact.** The if-X-breaks-then-Y map. **Source of truth for `references/architecture/service-dependency-matrix.md`.** |

[methodcrm/DeveloperTools `ClaudeCode/claude-plugin/references/incident/`](https://github.com/methodcrm/DeveloperTools/tree/bgrady/global-skills-export/ClaudeCode/claude-plugin/references/incident) holds the canonical incident playbooks (`triage-process.md`, `classification.md`, `log-sources.md`, `bug-analysis-template.md`, `post-deploy.md`).

## What this file isn't

- Not a replacement for `CLAUDE.md` — that's source of truth.
- Not a full architecture book — it's a stability-flavoured digest.
- Not auto-updated. When `CLAUDE.md` changes, refresh this file in the same PR.
