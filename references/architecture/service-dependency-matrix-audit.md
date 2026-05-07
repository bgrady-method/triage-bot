# Service dependency matrix — audit & rectification report

Audit of `service-dependency-matrix.md` (sibling file) against the rest of the Method codebase. Conducted 2026-05-04 against IIS state on the maintainer's dev box, `methodcrm/ms-gateway-api` source, `methodcrm/DeveloperTools/method-infrastructure/`, `methodcrm/DeveloperTools/Method-CLI/projects.yaml`, and every per-service `CLAUDE.md` across the `methodcrm/*` GitHub org.

**TL;DR** — the matrix is the most aged of seven places that claim to enumerate Method services. It lists 17 services (vs 40+ in `02-services.md`), names some of them wrong (`Method.Search` vs `ms-search-api`; `Subscriber.Agent` vs `Runtime.Core.Subscriber`), and undercounts dependencies on at least 9 of its 17 rows. Its own footer cites `CLAUDE.md` as the precedence source, but the operational source of truth is `DeveloperTools/method-infrastructure/08-interdependencies.md`. Recommended fix: promote 08-interdeps explicitly, resync the matrix once, add a self-contained drift-check script, and stop independently maintaining the matrix.

> **Portability note.** This report is read by the routine running on a Linux cloud VM. References to per-service files and `DeveloperTools` use GitHub URLs (https://github.com/methodcrm/...). The `triage` cloud routine clones `methodcrm/DeveloperTools` and 25 service repos as siblings, so `cat DeveloperTools/method-infrastructure/...` works there at runtime. The `heartbeat` and `stability-review` routines do **not** clone those repos — they must use `gh api` to fetch any external content. Use the `?ref=<branch>` query string when fetching: `master` for service repos, `bgrady/global-skills-export` for `DeveloperTools` (the `method-infrastructure/` docs only live on that branch today). References to triage-bot's own files (this repo) are relative.

---

## 1. Source map — where service / dependency claims live

| Source | Scope of claim | Trust |
|---|---|---|
| `references/architecture/service-dependency-matrix.md` (this repo) | 17 services × 7 backing stores, H/S/A cells | **Audited target — drifted** |
| `CLAUDE.md` (this repo) §Service catalog (lines 56–115) | ~23 repos by category | Index, not authority |
| [methodcrm/DeveloperTools `method-infrastructure/02-services.md`](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md) | 40+ services across 9 tiers, repo / solution / pool / health URL | **Most comprehensive catalog** |
| [methodcrm/DeveloperTools `method-infrastructure/08-interdependencies.md`](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md) lines 75–90 | Per-service data-layer table | **Closest analogue to the matrix** — but uses "likely" markers |
| [methodcrm/DeveloperTools `method-infrastructure/04-databases.md`](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/04-databases.md) | Per-cluster SQL / Mongo / Redis layout | Authoritative for stores, not services |
| [methodcrm/DeveloperTools `Method-CLI/projects.yaml`](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/Method-CLI/projects.yaml) | Repo registry, build steps, health-check endpoints | Canonical for "what repos exist" |
| [methodcrm/DeveloperTools `Method-CLI/iis.yaml`](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/Method-CLI/iis.yaml) lines 291–364 | IIS site → pool mapping | Canonical for pool sharing |
| `mtd iis sites status` / `Get-IISAppPool` (Windows-only, run by the maintainer) | 40+ pools running locally | Ground truth for "what's deployed" |
| Per-service `CLAUDE.md` (16 found across `methodcrm/*` repos) | Per-service stack, DBs, queues | Authoritative *for that one service* |
| [methodcrm/ms-gateway-api `gateway/API/`](https://github.com/methodcrm/ms-gateway-api/tree/master/gateway/API) (`Program.cs`, `appsettings.json`, `Middlewares/OcelotPipelineMiddleware.cs`, `Util/RouteConfigurationExtensions.cs`, `Util/LogHelper.cs`, `ocelot.*.json`) | The actual gateway wiring | **Code wins over docs** |
| OnboardingDocs (referenced in maintainer's local tree) | (empty directory — no files) | Dead reference |

---

## 2. Service-roster gaps

### 2a — Rows that are stale or misnamed

| Matrix row (line) | Issue | Source |
|---|---|---|
| `Method.Search` (line 32) | Repo is `ms-search-api`, Tier 2, separate solution `search.sln`, IIS pool `ms-search-api`. [methodcrm/runtime-core `CLAUDE.md:13`](https://github.com/methodcrm/runtime-core/blob/master/CLAUDE.md#L13) calls it "Method.Search (Search.Api)" *as a sub-host* — a third name. Only one of these can be a row. | [02-services.md:26](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L26); [runtime-core/CLAUDE.md:13](https://github.com/methodcrm/runtime-core/blob/master/CLAUDE.md#L13) |
| `runtime-core (Subscriber.Agent)` (line 20) | Actual class is `Runtime.Core.Subscriber` (no "Agent"). Matrix also omits sub-hosts: `Apps.Api` (5200), `AI.Core.Api`, `EDA.Orchestrator.Api`, `JournalAgent`, `JournalService`. | [runtime-core/CLAUDE.md:11–13](https://github.com/methodcrm/runtime-core/blob/master/CLAUDE.md#L11-L13) |
| `ms-email-api` (line 27) | 02-services.md tags this `8 (inactive)`. Matrix lists it as live. | [02-services.md:24](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L24) |
| `ms-scheduler-api` (line 28) | Health URL blank in 02-services.md; no per-service `CLAUDE.md`. Cells in matrix can't be verified against any source. | [02-services.md:25](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L25); `CLAUDE.md:88` (this repo) |
| `oauth2` (line 17) | Only one row, but Postman has both `OAuth.postman_collection.json` and `OAuth2 - IdentityServer.postman_collection.json` — two different services. The single-row representation collapses a real distinction. | `methodcrm/DeveloperTools/AdHocTools/PostMan/Collections/`; [oauth2/CLAUDE.md:22](https://github.com/methodcrm/oauth2/blob/master/CLAUDE.md#L22) (IdentityServer4 4.1.2) |

### 2b — Services missing from matrix entirely

Tier annotations from `02-services.md`. Each row matters because it adds to either critical-path or to a pool-sharing blast radius the matrix can't currently surface.

| Tier | Service | Why Phase 6 cares |
|---|---|---|
| 1 | `ms-identity-api` | Identity sessions; Pri 3 in [02-services.md:13](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L13). Matrix's "OAuth2/Auth" column conflates this with auth. |
| 2 | `ms-support-api` | Tier 2 dotnet microservice. [02-services.md:27](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L27) |
| 2 | `ms-search-api` | The actual repo behind "Method.Search". [02-services.md:26](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L26); [08-interdeps:83](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md#L83) lists ES as primary store + likely Redis. |
| 2 | `xero-sync` | Parallel to qbo-sync-api. [02-services.md:28](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L28) |
| 3 | `ms-analytics-api` | Subscribes to runtime-core RabbitMQ events. [02-services.md:35](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L35); [runtime-core/CLAUDE.md:25](https://github.com/methodcrm/runtime-core/blob/master/CLAUDE.md#L25) |
| 3 | `ms-archive-api`, `ms-gmail-addon-api`, `ms-google-calendarsync-api`, `ms-synclog-api` | All four share IIS pool `microservices` with `ms-tables-fields-api`. Recycling that pool blasts six services at once — a matrix-relevant fact the matrix can't show today. | [02-services.md:36–39](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L36-L39); [08-interdeps:97,111](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md#L97) |
| 3 | `ms-mailchimp-api`, `ms-mailchimp-agent`, `ms-health-api` | [02-services.md:40–43](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L40-L43) |
| 4 | `method-platform-ui`, `method-signin-ui`, `method-signup-ui`, `portal-signin-ui` | Frontend tier. Matrix is service-only, but UIs sit upstream of `ms-gateway-api` and any downtime of the gateway is user-facing through them. | [02-services.md:49–52](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L49-L52) |
| 5 | `legacy-authentication-api` | Distinct from `oauth2`. [02-services.md:59](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L59) |
| 6 | `qbo-webhooks-api` | Same repo as qbo-sync-api but separate IIS host. [02-services.md:66](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L66) |
| 7 | `legacy-syncservice-api`, `legacy-billingsubscription-api`, `legacy-bre-api`, `legacy-miurl-api`, `legacy-internal-api`, `legacy-public-api`, plus ~12 more | All share IIS pool `legacy`. Pool recycle takes them all down. | [02-services.md:73](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L73); [08-interdeps:112](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md#L112) |

---

## 3. Cell-level dependency errors

Each row cites the contradicting source. "Reality" is what at least two of (per-service CLAUDE.md, 08-interdeps, source code) agree on.

| Service | Matrix says | Reality | Source |
|---|---|---|---|
| `ms-gateway-api` | Redis H, OAuth2 H | + **Elasticsearch S** (Serilog log sink) | [API.csproj:41](https://github.com/methodcrm/ms-gateway-api/blob/master/gateway/API/API.csproj#L41) (`Serilog.Sinks.ElasticSearch`); [Util/LogHelper.cs:18,56](https://github.com/methodcrm/ms-gateway-api/blob/master/gateway/API/Util/LogHelper.cs#L18-L56); [appsettings.json:12](https://github.com/methodcrm/ms-gateway-api/blob/master/gateway/API/appsettings.json#L12) `ESLogURL`; [08-interdeps:77](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md#L77) |
| `ms-authentication-api` | SQL H, Redis S | + **MongoDB H** (qr_users, authorization_codes), MySQL alongside SQL Server | [ms-authentication-api/CLAUDE.md:34](https://github.com/methodcrm/ms-authentication-api/blob/master/CLAUDE.md#L34) |
| `oauth2` | SQL H | + **MongoDB H**, **Redis H**, 6 external OIDC providers (Google, Microsoft, Xero, Intuit, Apple, Facebook) | [oauth2/CLAUDE.md:22](https://github.com/methodcrm/oauth2/blob/master/CLAUDE.md#L22) (IdentityServer4 4.1.2) |
| `ms-tables-fields-api` | Redis S | Redis is the **primary cache for spider* metadata** — closer to H. RabbitMQ is also primary, not async. | [ms-tables-fields-api/CLAUDE.md:11–18](https://github.com/methodcrm/ms-tables-fields-api/blob/master/CLAUDE.md#L11-L18); [02-services.md:34](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L34) ("Redis cache, RabbitMQ via MassTransit"); [08-interdeps:81](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md#L81) (Yes, not "likely") |
| `ms-account-api` | SQL H, Redis S, OAuth2 H | + **MongoDB**, + **RabbitMQ A** (MassTransit 7.2) | [ms-account-api/CLAUDE.md:409](https://github.com/methodcrm/ms-account-api/blob/master/CLAUDE.md#L409) |
| `ms-tags-api` | SQL H, OAuth2 H | + **MongoDB**, + **Redis**, + **RabbitMQ** | [ms-tags-api/CLAUDE.md:226–227,268](https://github.com/methodcrm/ms-tags-api/blob/master/CLAUDE.md#L226-L268) |
| `ms-preferences-api` | SQL H, OAuth2 H | + **MongoDB H** (account-specific + shared), + **Redis S** (60-day TTL), + **RabbitMQ A**, MySQL alongside SQL Server | [ms-preferences-api/CLAUDE.md](https://github.com/methodcrm/ms-preferences-api/blob/master/CLAUDE.md) (stack section) |
| `ms-documents-api` | SQL H, S3 H, OAuth2 H | + **MongoDB H** (Documents.Metadata, Documents.SecuredLinks). Redis exists but with MemoryCache fallback flagged as tech debt. | [ms-documents-api/CLAUDE.md:224](https://github.com/methodcrm/ms-documents-api/blob/master/CLAUDE.md#L224) |
| `ms-email-api` | SQL H, RabbitMQ A, OAuth2 H | + **MongoDB H** (EmailNotification, EmailBuilderTemplate), + **Redis S**; SQL is `Sql_c1, Sql_c2` only, **not c1–c5** | [ms-email-api/CLAUDE.md:9,39,40](https://github.com/methodcrm/ms-email-api/blob/master/CLAUDE.md#L9-L40) |
| `runtime-core (Runtime.Core.Api)` | SQL H, Mongo H, Redis S, RabbitMQ A, ES S, OAuth2 H | + **S3 H** (file storage); ES is at minimum S, possibly H since Method.Search is hosted inside runtime-core | [runtime-core/CLAUDE.md:13,27,53,57](https://github.com/methodcrm/runtime-core/blob/master/CLAUDE.md#L13-L57) |

---

## 4. Naming inconsistencies

Same thing, two or three names — these prevent cross-source joins (a script that lists "everything that uses Redis" can't merge sources today):

- **`oauth2` ≠ `OAuth2` ≠ legacy OAuth.** Repo is `oauth2` (lowercase, IdentityServer4 4.1.2 per [oauth2/CLAUDE.md:22](https://github.com/methodcrm/oauth2/blob/master/CLAUDE.md#L22)). Auth doc uses `OAuth2` (capitalized). Postman has *both* `OAuth.postman_collection.json` *and* `OAuth2 - IdentityServer.postman_collection.json` — these are different services. The matrix collapses them; 02-services.md splits some but not all.
- **`Method.Search` vs `ms-search-api` vs runtime-core sub-host.** Matrix line 32 calls it `Method.Search`. [02-services.md:26](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/02-services.md#L26) says `ms-search-api`, separate Tier 2 repo, `search.sln`, pool `ms-search-api`. [runtime-core/CLAUDE.md:13](https://github.com/methodcrm/runtime-core/blob/master/CLAUDE.md#L13) lists `Method.Search (Search.Api)` *inside* runtime-core's "Additional Services". One of (a) it moved repos, (b) it's both, or (c) one of the docs is wrong. `CLAUDE.md:77` (this repo) perpetuates the runtime-core-hosted version.
- **`Subscriber.Agent` vs `Runtime.Core.Subscriber`.** Matrix says `Subscriber.Agent` (line 20). [runtime-core/CLAUDE.md:11](https://github.com/methodcrm/runtime-core/blob/master/CLAUDE.md#L11) says `Runtime.Core.Subscriber`. There is no "Agent" suffix in the actual class. (Note: this repo's `references/architecture/known-failure-modes.md` F1 and `platform-overview.md` lines 50, 77, 92 also use the wrong name; fixed in the same PR.)

---

## 5. Authority cycle (the meta-problem)

The matrix's footer (line 79) says:

> "Keep this file in sync with `CLAUDE.md`. When in conflict, `CLAUDE.md` wins; this file follows."

But this repo's `CLAUDE.md` doesn't contain dependency cells — it's an index of repos with one-line role descriptions. Line 173 of that file explicitly defers further:

> "When in doubt about impact, `cat DeveloperTools/method-infrastructure/08-interdependencies.md`."

So the actual precedence chain is:

```
matrix → triage-bot/CLAUDE.md → 08-interdependencies.md → per-service CLAUDE.md → source code
```

Five links, each with independent drift. The matrix says "CLAUDE.md wins", but operationally **08-interdeps wins** — and even 08-interdeps hedges with "likely" markers it has never tightened up. None of the seven sources in §1 has a generator script keeping it consistent with the others.

> **Routine-environment caveat.** `DeveloperTools` is not in `routines/triage.yaml` or `routines/stability-review.yaml` — so the cloud routine *cannot* `cat DeveloperTools/method-infrastructure/08-interdependencies.md` today. It must use the GitHub URLs above. See §6 step 4 for the proposed YAML fix.

---

## 6. Rectification suggestions

Three options ordered by ambition. Recommend Option B.

### Option A — One-shot resync
Rewrite the matrix to mirror 08-interdeps + per-service CLAUDE.md from §3. Add the missing services from §2b. Done in a single PR. Cheapest and easiest.

**Why not:** Six months from now the same drift recurs, because nothing structural changed. The matrix and 08-interdeps still claim the same domain independently.

### Option B — Recommended: derive + verify, single source of truth

1. **Promote `DeveloperTools/method-infrastructure/08-interdependencies.md` to the source of truth for service dependencies.** The matrix becomes a derived view, not an independent claim.
2. **Replace the matrix's footer (lines 73–79) with:**
   > *"Derived from `methodcrm/DeveloperTools` `method-infrastructure/08-interdependencies.md`. When that file conflicts with this one, that file wins. Per-service `CLAUDE.md` wins over both for that service's specific stack."*
3. **Resync the matrix once** against the §3 corrections. Tighten 08-interdeps's "likely" markers by spot-checking each one against the per-service `appsettings.json` / `Web.config` — the grep recipes already exist in [08-interdeps:158–177](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md#L158-L177).
4. **Add a self-contained drift-check script** at `scripts/dep_drift_check.py` in *this repo*. Python, no `mtd` dependency, runs on Linux, no services need to be live. Behavior:
   - Walks sibling-cloned service repos (those listed in `routines/*.yaml` `repos:`).
   - Greps each repo's `appsettings*.json` / `Web.config` for connection-string markers (`ConnectionStrings:`, `ConnectionOptions:Redis|RabbitMQ`, `mongodb://`, `amqp://`, `IAmazonS3`, `Elasticsearch`).
   - Parses `references/architecture/service-dependency-matrix.md` for declared dependencies.
   - Reports drift in a single "stale" / "missing" list.
   - CI step on every triage-bot PR; quarterly cron in stability-review.
5. **Add `methodcrm/DeveloperTools` to `routines/triage.yaml` and `routines/stability-review.yaml` `repos:`** so all the existing `DeveloperTools/method-infrastructure/...` references in `CLAUDE.md`, `prompt.md`, `stability-review-prompt.md`, and `references/architecture/platform-overview.md` resolve at runtime. Currently they don't.
6. **Move the matrix's "Cross-tenant blast radius" table (lines 55–69) into 08-interdeps** so per-service blast radius is adjacent to per-service dependencies. Two facts, one place. (Out-of-repo change — file a PR against `methodcrm/DeveloperTools`.)
7. **Resolve naming aliases once** by adding an "Aliases" column to `02-services.md`:
   - `oauth2` (repo) / `OAuth2` (display) / `IdentityServer` (component)
   - `ms-search-api` (repo) / `Method.Search` (host) / `Search.Api` (project)
   - `Runtime.Core.Subscriber` (project) — drop "Subscriber.Agent" everywhere
8. **Annotate `ms-email-api`'s "(inactive)" status** in the matrix and in `08-interdeps`. If it's truly inactive, strike-through or move to a Legacy section. If it's active, fix `02-services.md:24`.

### Option C — Delete the matrix, refactor Phase 6
The matrix exists because Phase 6 of `stability-review-prompt.md` needs a tabular dependency lookup. If 08-interdeps is canonical, change Phase 6 to read 08-interdeps directly. Cleanest architecturally but requires a prompt rewrite and re-validation of the whole stability review. Defer unless Option B's maintenance becomes annoying.

---

## 7. Verification

Run from the routine root (`triage-bot/` clone). All commands are bash and assume `gh` CLI is authenticated via `GH_TOKEN`.

```bash
# §1 — confirm OnboardingDocs is empty (this is a maintainer-machine fact; cloud routine can skip)
# (no cloud-routine equivalent — this report's claim is informational)

# §2b — confirm pool sharing (six services in `microservices` pool)
gh api 'repos/methodcrm/DeveloperTools/contents/Method-CLI/iis.yaml' --jq '.content' \
  | base64 -d | grep -c 'app_pool: microservices'
# Expected: 6+

# §3 ms-gateway-api Elasticsearch
gh api 'repos/methodcrm/ms-gateway-api/contents/gateway/API/Util/LogHelper.cs' --jq '.content' \
  | base64 -d | grep -E 'Elasticsearch|esURL'

# §3 ms-email-api MongoDB + 2-cluster SQL
gh api 'repos/methodcrm/ms-email-api/contents/CLAUDE.md' --jq '.content' \
  | base64 -d | grep -E 'MongoDB|Sql_c'

# §3 runtime-core S3
gh api 'repos/methodcrm/runtime-core/contents/CLAUDE.md' --jq '.content' \
  | base64 -d | grep -E 'S3|file storage'

# §3 oauth2 Mongo + Redis
gh api 'repos/methodcrm/oauth2/contents/CLAUDE.md' --jq '.content' \
  | base64 -d | grep -E 'MongoDB|Redis|MySQL'

# §1 confirm 02-services.md is comprehensive — count service rows
gh api 'repos/methodcrm/DeveloperTools/contents/method-infrastructure/02-services.md' --jq '.content' \
  | base64 -d | grep -cE '^\| `?[a-z-]+\s*\|'
# Expected: 35-45 (matrix has 17)

# Drift-check — once §6.4 lands
python scripts/dep_drift_check.py --report
# Expected: zero drift after the §6.3 resync; surfaces drift on subsequent runs.
```

Maintainer-machine equivalents (Windows, when validating locally):

```powershell
mtd iis sites status
Select-String -Path 'C:\MethodDev\DeveloperTools\Method-CLI\iis.yaml' -Pattern 'app_pool: microservices'
Select-String -Path 'C:\MethodDev\ms-gateway-api\gateway\API\Util\LogHelper.cs' -Pattern 'Elasticsearch|esURL'
Select-String -Path 'C:\MethodDev\ms-email-api\CLAUDE.md' -Pattern 'MongoDB|Sql_c'
Select-String -Path 'C:\MethodDev\runtime-core\CLAUDE.md' -Pattern 'S3|file storage'
Select-String -Path 'C:\MethodDev\oauth2\CLAUDE.md' -Pattern 'MongoDB|Redis|MySQL'
```

---

## 8. Follow-ups (out of scope for this report)

- Tighten every "likely" cell in [08-interdeps:75–90](https://github.com/methodcrm/DeveloperTools/blob/bgrady/global-skills-export/method-infrastructure/08-interdependencies.md#L75-L90) against per-service config files. List of "likely" cells: ms-authentication-api Redis, ms-identity-api Redis, ms-tags-api Redis, ms-search-api Redis, ms-documents-api Redis, ms-preferences-api Redis, ms-account-api Redis + RabbitMQ, qbo-sync-api Redis, runtime-core ES.
- Decide on `ms-email-api`'s status — fix one of (matrix lists it active) vs (02-services.md says inactive).
- Decide whether `Method.Search` is hosted in runtime-core or is a separate `ms-search-api`. If separate, `runtime-core/CLAUDE.md:13` needs a correction. If both, document the relationship.
- Audit per-service `CLAUDE.md` files for lag — [ms-documents-api/CLAUDE.md:224](https://github.com/methodcrm/ms-documents-api/blob/master/CLAUDE.md#L224) already self-flags MemoryCache as tech debt; treat per-service docs as a verification layer, not authoritative.
- `ms-identity-api`, `ms-scheduler-api`, `legacy-bre-api`, `DeveloperTools` (top-level) have no `CLAUDE.md` per `CLAUDE.md:178` (this repo). Phase-6 reasoning about these services can only fall back to README + git log today.
