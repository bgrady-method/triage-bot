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

For canonical detail, see `DeveloperTools/method-infrastructure/08-interdependencies.md` in the cloned repo (read it lazily — it's the source of truth for "if X breaks, what else breaks").

## Service catalog

Every repo below is cloned at routine start. **Read `<repo>/CLAUDE.md` whenever an alert names that service.** Most have one; the few exceptions are flagged.

### Frontend
| Repo | Role |
|---|---|
| `method-platform-ui` | The customer-facing low-code app (React 17, NX monorepo). Two halves: `m-one/` modern, `MethodUI/` legacy. CLAUDE.md ✅ |
| `method-signup-ui` | Sign-up flow. CLAUDE.md ✅ |
| `method-ai` | AI agent specs framework (TypeScript, modular agents). CLAUDE.md ✅ |

### API gateway / auth
| Repo | Role |
|---|---|
| `ms-gateway-api` | The critical-path entry: Ocelot reverse proxy (.NET 9). Owns JWT cache in Redis, internal-route guard, geolocation, CORS. **If this is down, the whole stack is unreachable.** CLAUDE.md ✅ |
| `oauth2` | OAuth2 / OpenID provider. CLAUDE.md ✅ |
| `ms-identity-api` | Identity sessions. **CLAUDE.md missing — fall back to README + commits.** |

### Core business logic
| Repo | Role |
|---|---|
| `runtime-core` | The business-logic engine (.NET 7-8, Dapper + SqlKata, Mongo, Redis, RabbitMQ + MassTransit, multi-cluster SQL). Hosts Runtime.Core.Api (5000), Designer.Core.Api (5100), Apps.Api (5200), AI.Core.Api, EDA.Orchestrator.Api, JournalAgent, Method.Search. **The biggest fan-out service in the system.** CLAUDE.md ✅ |
| `ms-tables-fields-api` | Owns `spider*` tables — the no-code metadata layer (table/field/view/relationship definitions). Multi-env via Ninject `ISqlDbProvider`. CLAUDE.md ✅ |

### Microservices (per-domain APIs)
| Repo | Role |
|---|---|
| `ms-account-api` | Account management (AlocetSystem registry). CLAUDE.md ✅ |
| `ms-tags-api` | Tags. CLAUDE.md ✅ |
| `ms-preferences-api` | User preferences. CLAUDE.md ✅ |
| `ms-documents-api` | Document storage. CLAUDE.md ✅ |
| `ms-support-api` | Support functionality. CLAUDE.md ✅ |
| `ms-scheduler-api` | Scheduled jobs. **CLAUDE.md missing.** |

### Sync / integrations
| Repo | Role |
|---|---|
| `qbo-sync-api` | QuickBooks Online sync (bridges external SaaS ↔ Method via events). CLAUDE.md ✅ |
| `legacy-syncservice-api` | Legacy sync endpoints (.NET Framework, IIS `legacy` pool). |
| `ms-sync-util` | Sync utilities. |
| `ms-synclog-api` | Sync logging. CLAUDE.md ✅ |

### Email / notifications
| Repo | Role |
|---|---|
| `ms-email-api` | Email sending. CLAUDE.md ✅ |
| `legacy-email-agent` | Legacy email orchestration. CLAUDE.md ✅ |
| `ms-reminder-agent` | Reminder scheduler. CLAUDE.md ✅ |

### Legacy / support
| Repo | Role |
|---|---|
| `legacy-miurl-api` | URL redirection. CLAUDE.md ✅ |
| `legacy-billingsubscription-api` | Billing subscriptions. CLAUDE.md ✅ |
| `legacy-bre-api` | Business Rule Engine (legacy). **CLAUDE.md missing.** |

### Tooling
| Repo | Role |
|---|---|
| `DeveloperTools` | Method's internal dev tooling. **No top-level CLAUDE.md.** Holds `method-infrastructure/` (the canonical infra docs — see below) and `ClaudeCode/claude-plugin/` (shared Claude conventions and references). |

## Infrastructure references

`DeveloperTools/method-infrastructure/` is the canonical "how the local stack is wired" doc set. Read these on demand:

| File | When to read |
|---|---|
| `01-iis-inventory.md` | Alerts about IIS app pools, recycling, sub-apps. |
| `02-services.md` | RabbitMQ, Redis, Elasticsearch, Windows Services. |
| `03-gateway-routing.md` | Anything about `ms-gateway-api`, JWT flow, Ocelot routes. |
| `04-databases.md` | SQL clusters (C1-C5), Mongo, Redis layout. **Always read for SQL/Mongo alerts.** |
| `05-auth-flow.md` | OAuth, identity, token-related alerts. |
| `06-frontend-stack.md` | UI build, NX, CDN issues. |
| `07-build-and-deploy.md` | Deploy correlation, CI/CD failure shapes. |
| `08-interdependencies.md` | **Read this first when assessing impact** — the if-X-breaks-then-Y map. |

Plus `DeveloperTools/ClaudeCode/claude-plugin/references/incident/` has the canonical incident playbooks (`triage-process.md`, `classification.md`, `log-sources.md`, `bug-analysis-template.md`, `post-deploy.md`).

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
3. For infrastructure-shaped alerts (IIS, RabbitMQ, Redis, ES, SQL cluster), `cat DeveloperTools/method-infrastructure/<relevant>.md`.
4. When in doubt about impact, `cat DeveloperTools/method-infrastructure/08-interdependencies.md`.
5. Don't load every CLAUDE.md proactively — context budget matters. Lazy-load by service-name match.

## Known gaps

- `ms-identity-api`, `ms-scheduler-api`, `legacy-bre-api`, `DeveloperTools` (top-level) — no CLAUDE.md. Investigation falls back to README + git log.
- No service-catalog doc lives in any one place outside this file. Keep this section current as repos are added.
- Domain glossary is incomplete — extend as the routine encounters terms it didn't recognize. The KB curation routine (`kb-approver`) doesn't update this file; updates here are manual.
