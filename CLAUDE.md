# CLAUDE.md — orientation for the triage-bot routine

This file is the first thing the routine should read on every fire, after `prompt.md`. It captures the parts of Method's architecture and domain that are stable and useful across all alerts. Per-service implementation details live in each service's own `CLAUDE.md` — read those lazily, only for the service named in the alert you're triaging.

## What this repo is

`bgrady-method/triage-bot` is the Slack-alert-driven investigation routine. It polls four Slack channels every hour, classifies new alerts (false-alarm / known-issue-recurrence / new-with-clear-fix / needs-human), DMs findings to Ben, and accumulates a knowledge base of recurring issues. Read `prompt.md` for the per-step procedure, `playbooks/` for the per-tool investigation order, and `docs/runbook.md` for operational controls.

## Method's architecture, at a glance

Method is a low-code/no-code business automation platform built on a five-layer architecture:

```
USER-FACING LAYER (App Builder, Screen Designer, Tables & Fields)
         │   manipulates
         ▼
RUNTIME LAYER  — MongoDB                (Apps, Screens, Controls, Events, ActionSets)
         │   reads/writes
         ▼
DATA LAYER — SQL Server                 (acc* tables = QB sync, Spider* tables = no-code metadata,
                                         per-tenant data — one DB per customer)
```

Plus Redis (caching, JWT cache), Elasticsearch (full-text search + Serilog log sink), RabbitMQ (async messaging via MassTransit / EDA).

### High-level call graph

```
External clients (browser, OAuth client, mobile)
                │
                ▼
   methodportallocal.com (method-platform-ui)
   signin.methodlocal.com (method-signin-ui)
   signup.methodlocal.com (method-signup-ui)
   auth.methodlocal.com   (oauth2)
                │ HTTPS, Method-JWT or cookie
                ▼
   api.methodlocal.com/v2  ms-gateway-api
     ─ Ocelot reverse proxy
     ─ JWT cache (Redis)
     ─ Calls ms-authentication for JWT validate
                │
   ┌────────────┼──────────────┐
   │            │              │
   ▼            ▼              ▼
microservices.   eda.          runtime.
methodlocal.int  methodlocal.  methodlocal.com
                 int           designer.…
                                restapi.…
   │
   └─ peer-to-peer HTTP for service-to-service (does NOT route back through gateway)
```

For canonical detail, see [methodcrm/DeveloperTools `method-infrastructure/08-interdependencies.md`](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md) (read lazily — it's the source of truth for "if X breaks, what else breaks", and for the dependency cells in `references/architecture/service-dependency-matrix.md`).

## Service catalog

Most repos below are cloned at routine start (see `routines/triage.yaml` `repos:`). For repos that aren't cloned, **read the per-service CLAUDE.md from GitHub via `gh api 'repos/methodcrm/<repo>/contents/CLAUDE.md' --jq '.content' | base64 -d`**. Lazy-load by service-name match — don't fetch all of them.

### Frontend
| Repo | Role |
|---|---|
| `method-platform-ui` | The customer-facing low-code app (React 17, NX monorepo). Two halves: `m-one/` modern, `MethodUI/` legacy. CLAUDE.md ✅ |
| `method-signin-ui` | Sign-in flow (`signin.methodlocal.com`). |
| `method-signup-ui` | Sign-up flow. CLAUDE.md ✅ |
| `method-ai` | AI agent specs framework (TypeScript, modular agents). CLAUDE.md ✅ |

### API gateway / auth
| Repo | Role |
|---|---|
| `ms-gateway-api` | The critical-path entry: Ocelot reverse proxy (.NET 9). Owns JWT cache in Redis, internal-route guard, geolocation, CORS. **If this is down, the whole stack is unreachable.** CLAUDE.md ✅ |
| `oauth2` | OAuth2 / OpenID provider (IdentityServer4). Distinct from `legacy-authentication-api`. CLAUDE.md ✅ |
| `ms-authentication-api` | Method's custom JWT issuer / validator. Mongo + SQL + Redis. CLAUDE.md ✅ |
| `ms-identity-api` | Identity sessions. **CLAUDE.md missing — fall back to README + commits.** |
| `legacy-authentication-api` | Legacy auth endpoints (`services.methodlocal.com/authservice`). IIS `legacy` pool. |

### Core business logic
| Repo | Role |
|---|---|
| `runtime-core` | The business-logic engine (.NET 7-8, Dapper + SqlKata, Mongo, Redis, RabbitMQ + MassTransit, multi-cluster SQL, S3). Core hosts: `Runtime.Core.Api` (5000), `Designer.Core.Api` (5100), `Apps.Api` (5200), `Runtime.Core.Subscriber`, `Runtime.AppUpdate.Agent`. Additional hosts: `AI.Core.Api`, `EDA.Orchestrator.Api`, `JournalAgent`, `JournalService`, `Method.Search` (Search.Api — but see `ms-search-api` below for the question of whether it's separate). **The biggest fan-out service in the system.** CLAUDE.md ✅ |
| `ms-tables-fields-api` | Owns `spider*` tables — the no-code metadata layer (table/field/view/relationship definitions). Multi-env via Ninject `ISqlDbProvider`. CLAUDE.md ✅ |

### Microservices (per-domain APIs)
| Repo | Role |
|---|---|
| `ms-account-api` | Account management (AlocetSystem registry). CLAUDE.md ✅ |
| `ms-tags-api` | Tags. CLAUDE.md ✅ |
| `ms-preferences-api` | User preferences. CLAUDE.md ✅ |
| `ms-documents-api` | Document storage (S3-backed). CLAUDE.md ✅ |
| `ms-support-api` | Support functionality. CLAUDE.md ✅ |
| `ms-scheduler-api` | Scheduled jobs. **CLAUDE.md missing.** |
| `ms-search-api` | Full-text search (Elasticsearch). Tier 2 repo per `02-services.md:26`. **Note alias confusion**: `runtime-core/CLAUDE.md:13` lists "Method.Search (Search.Api)" as an additional host — the matrix-audit (`references/architecture/service-dependency-matrix-audit.md` §4) flags this as an unresolved ambiguity. Treat as separate service; if alerts only fire on `runtime-core` host paths, scope to runtime-core. |
| `ms-analytics-api` | Subscribes to runtime-core RabbitMQ events. Tier 3 (.NET Framework). |

### Tier 3 .NET Framework microservices (share IIS `microservices` pool — recycle blasts all together)

These don't typically own alerts but matter for blast-radius reasoning. When `runtime-core` or `ms-tables-fields-api` shows odd timing correlations with unrelated services, suspect a `microservices` pool recycle.

| Repo | Role |
|---|---|
| `ms-archive-api` | Account archival. |
| `ms-gmail-addon-api` | Gmail add-on backend. |
| `ms-google-calendarsync-api` | Google Calendar sync. |
| `ms-synclog-api` | Sync logging. CLAUDE.md ✅ |
| `ms-mailchimp-api` / `ms-mailchimp-agent` | MailChimp integration (own pool: `development`). |
| `ms-health-api` | Health-check aggregator. |

### Sync / integrations
| Repo | Role |
|---|---|
| `qbo-sync-api` | QuickBooks Online sync (bridges external SaaS ↔ Method via events). CLAUDE.md ✅ |
| `qbo-webhooks-api` | QBO webhook receiver. Same repo as `qbo-sync-api`, separate IIS host (`webhooks.methodlocal.com`). |
| `xero-sync` | Xero sync. Tier 2. |
| `legacy-syncservice-api` | Legacy sync endpoints (.NET Framework, IIS `legacy` pool). |
| `ms-sync-util` | Sync utilities. |

### Email / notifications
| Repo | Role |
|---|---|
| `ms-email-api` | Email sending (SendGrid). **02-services.md:24 tags this `(inactive)`** — verify before assuming this owns a current alert. CLAUDE.md ✅ |
| `legacy-email-agent` | Legacy email orchestration. CLAUDE.md ✅ |
| `ms-reminder-agent` | Reminder scheduler. CLAUDE.md ✅ |

### Legacy / support
| Repo | Role |
|---|---|
| `legacy-miurl-api` | URL redirection. CLAUDE.md ✅ |
| `legacy-billingsubscription-api` | Billing subscriptions. CLAUDE.md ✅ |
| `legacy-bre-api` | Business Rule Engine (legacy). **CLAUDE.md missing.** |
| Plus ~12 more `legacy-*` services | All share IIS `legacy` pool. See [methodcrm/DeveloperTools `02-services.md` Tier 7](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#tier-7) for the full list. |

### Tooling
| Repo | Role |
|---|---|
| `DeveloperTools` | Method's internal dev tooling. **No top-level CLAUDE.md.** Holds `method-infrastructure/` (the canonical infra docs — see below) and `ClaudeCode/claude-plugin/` (shared Claude conventions and references). **⚠ Not currently cloned by any routine** (`routines/triage.yaml`, `routines/stability-review.yaml`); references below resolve via GitHub URL or `gh api`, not local cat. |

## Infrastructure references

`methodcrm/DeveloperTools` `method-infrastructure/` is the canonical "how the local stack is wired" doc set. Read these on demand. **`DeveloperTools` is not currently cloned by the routines** — fetch via `gh api 'repos/methodcrm/DeveloperTools/contents/<path>' --jq '.content' | base64 -d` or open the GitHub URL directly:

| File | When to read | URL |
|---|---|---|
| `01-iis-inventory.md` | Alerts about IIS app pools, recycling, sub-apps. | https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/01-iis-inventory.md |
| `02-services.md` | Service catalog (40+ services) by tier; pool, host, health URL. | https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md |
| `03-gateway-routing.md` | Anything about `ms-gateway-api`, JWT flow, Ocelot routes. | https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/03-gateway-routing.md |
| `04-databases.md` | SQL clusters (C1-C5), Mongo, Redis layout. **Always read for SQL/Mongo alerts.** | https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/04-databases.md |
| `05-auth-flow.md` | OAuth, identity, token-related alerts. | https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/05-auth-flow.md |
| `06-frontend-stack.md` | UI build, NX, CDN issues. | https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/06-frontend-stack.md |
| `07-build-and-deploy.md` | Deploy correlation, CI/CD failure shapes. | https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/07-build-and-deploy.md |
| `08-interdependencies.md` | **Read this first when assessing impact** — the if-X-breaks-then-Y map. **Source of truth for `references/architecture/service-dependency-matrix.md`.** | https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md |

Plus `methodcrm/DeveloperTools/ClaudeCode/claude-plugin/references/incident/` has the canonical incident playbooks (`triage-process.md`, `classification.md`, `log-sources.md`, `bug-analysis-template.md`, `post-deploy.md`).

## Domain glossary

Common terms that appear in alerts and stack traces:

| Term | Meaning |
|---|---|
| **Account** | A Method tenant. Each account has its own SQL DB (`account_<id>` or named like `m11ben17nov2023`) and its own Mongo DB (lowercase account name). |
| **MainAccount** | The account identifier used as the row-level filter at the repository layer. Repository-level enforcement is the multi-tenancy boundary. |
| **App** | A no-code application: container of screens + data model + actions. |
| **Screen** | A page within an app. Has controls, events, layout. |
| **Control** | A backend widget definition (`BTN`, `GRD`, `DRP`, etc.). Frontend renders it. |
| **Action / ActionSet** | An executable operation or sequence — 50+ types (`InsertRecord`, `Conditional`, `Loop*`, `CallAnotherActionSet`, `RetrieveValueFromTable`, etc.). |
| **AppRoutine** | Server-side scheduled workflow. Quick (<5 min) or Slow (>20 min) queue. |
| **BRE** | Business Rule Engine. `NewBRE` (modern, EDA-based) vs `LegacyBRE` (original). Per-account toggle via `NewBRE.BreEnabledAccounts`. |
| **Tailoring** | Per-account customization that survives platform upgrades. |
| **EncryptedRecordID** | Obfuscated record ID exposed in URLs / responses to prevent enumeration. |
| **Spider tables** | The `spider*` SQL tables that drive the no-code UI builder. Owned by `ms-tables-fields-api`. |
| **acc tables** | The `acc*` SQL tables that hold QuickBooks-mirrored business data. |
| **`accEntity` + `sEntityType`** | The unified Customer/Vendor/Employee table; `sEntityType` is the discriminator. |
| **Tenant DB / Per-tenant DB** | A customer's individual SQL database. Schema is variable because of customizations. |
| **Method-JWT** | Internal-format JWT issued by `ms-authentication-api`, cached in Redis by the gateway. |
| **EDA** | Event-Driven Architecture orchestrator (`eda.methodlocal.int`). RabbitMQ + MassTransit. |

## Critical-path facts (impact reasoning)

Memorize these — they shape "is this a P0?":

- **`ms-authentication-api` down** → gateway `/health/check` unhealthy, all NEW sessions fail, existing JWTs work until expiry.
- **Redis down** → JWTs uncached, every request hits `ms-authentication`. Latency rises.
- **`microservices.methodlocal.int` IIS site down** → every microservice virtual app gone. Whole stack effectively dies.
- **`microservices` IIS pool recycle** → `archive`, `calendar-sync`, `import`, `sync`, `tables-fields`, `gmailaddon` all restart together.
- **`legacy` IIS pool recycle** → every legacy ASP.NET site (`services.methodlocal.com`, billing, sync legacy, etc.) restarts together.
- **`runtime-core` pool stopped** → runtime, designer, RestApi, and gateway-routed `/apps` endpoints all stop responding.

## How the routine should use this file

1. `cat CLAUDE.md` (this file) at the start of every poll cycle, after `prompt.md`. Hold it in working context for the duration of the cycle.
2. For each alert: identify the named service(s) from the alert text. For each: `cat <repo>/CLAUDE.md` from the cloned repo. Skip repos whose CLAUDE.md is missing — fall back to `README.md` + `git log --since="7 days ago" --oneline`.
3. For infrastructure-shaped alerts (IIS, RabbitMQ, Redis, ES, SQL cluster), fetch the relevant `methodcrm/DeveloperTools/method-infrastructure/<file>.md` (DeveloperTools is not cloned — use `gh api 'repos/methodcrm/DeveloperTools/contents/method-infrastructure/<file>.md' --jq '.content' | base64 -d`).
4. When in doubt about impact, fetch `08-interdependencies.md` the same way.
5. Don't load every CLAUDE.md proactively — context budget matters. Lazy-load by service-name match.

## Known gaps

- `ms-identity-api`, `ms-scheduler-api`, `legacy-bre-api`, `DeveloperTools` (top-level) — no CLAUDE.md. Investigation falls back to README + git log.
- **`methodcrm/DeveloperTools` is referenced ~10x across this repo but isn't in `routines/triage.yaml` or `routines/stability-review.yaml`.** All `DeveloperTools/method-infrastructure/...` references resolve via `gh api` / GitHub URL until the YAMLs are updated. Adding it to the routines' `repos:` blocks would let the existing relative paths work.
- Per-service repos are also not all cloned by the routines — only `m-one`, `tables-fields`, `api-gateway` (GH names) per `routines/triage.yaml`. Other repos must be fetched via `gh api` on demand.
- The canonical service catalog is [methodcrm/DeveloperTools `02-services.md`](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md) (40+ services, 9 tiers). The catalog above mirrors a subset; when in doubt about whether a service exists, check 02-services.md.
- Domain glossary is incomplete — extend as the routine encounters terms it didn't recognize. The KB curation routine (`kb-approver`) doesn't update this file; updates here are manual.
