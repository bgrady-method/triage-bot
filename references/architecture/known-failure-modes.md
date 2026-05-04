# Known failure modes

Catalogue of recurring or high-impact failure modes the team has seen, with proposed SLO targets where none formally exist. Used by `stability-review-prompt.md` Phase 7 to compute error-budget burn against a defined target.

Format per entry:

```
### F<n>. <Title>
- **Symptom:** <user-visible failure>
- **Service(s):** <name>
- **Mechanism:** <why this happens>
- **Detection today:** <how it gets noticed (or doesn't)>
- **Proposed SLO target:** <if no formal SLO exists>
- **Course modules:** <level-N/<slug>.json paths to consult>
- **Source:** <where this is documented — CLAUDE.md, runtime-core/CLAUDE.md, prior investigation, etc.>
```

The list is **seed**. The routine should append entries as new patterns surface. Do not delete entries — mark them `Resolved: <YYYY-MM>` once the underlying recommendation has been implemented and verified by a subsequent month's report.

---

### F1. Cache staleness when Runtime.Core.Subscriber stops

- **Symptom:** Users see stale screen metadata, stale permissions, stale lookups for tens of minutes after a Designer change.
- **Service(s):** Runtime.Core.Subscriber. (Older docs / matrix predecessors called this `Subscriber.Agent`; the canonical name per [runtime-core/CLAUDE.md:11](https://github.com/methodcrm/runtime-core/blob/master/CLAUDE.md#L11) is `Runtime.Core.Subscriber`.)
- **Mechanism:** Subscriber consumes RabbitMQ events (`tables-fields.view.change`, `method.account-user.change`, others). On consume it invalidates Redis cache keys (prefix `runtime-core:2:`). When the consumer stops, events queue but are not consumed, so cache keys live to their TTL — minutes to hours.
- **Detection today:** None automatic. Discovered when users complain or when an engineer happens to notice queue depth.
- **Proposed SLO target:** Subscriber availability 99.9% over 30d (≤ 43 min unavailability). Heartbeat `No Data` alert + RabbitMQ consumer lag alert (depth > 100 messages for > 5 min).
- **Course modules:** `level-4/cache-invalidation.json`, `level-10/observability.json`, `level-10/disaster-recovery.json`, `level-1/availability-and-slas.json`.
- **Source:** [runtime-core/CLAUDE.md](https://github.com/methodcrm/runtime-core/blob/master/CLAUDE.md) lists Subscriber as a critical worker; `CLAUDE.md` (this repo) flags it as a critical-path failure.

### F2. RabbitMQ DLQ accumulation

- **Symptom:** Async events back up. AppRoutines stall. Cache invalidation halts (compounds F1).
- **Service(s):** RabbitMQ broker; MassTransit consumers across runtime-core, ms-* services.
- **Mechanism:** A consumer hangs (downstream timeout, deadlock, slow query) without bounded concurrency or fail-fast. Messages accumulate in the consumer's queue and eventually in the DLQ. No back-pressure to publishers.
- **Detection today:** Crash-detection only. A hung-but-alive consumer is invisible.
- **Proposed SLO target:** Per-queue depth p95 × 3 as alert threshold. DLQ depth > 0 for > 15 min as page.
- **Course modules:** `level-5/message-queues.json`, `level-5/communication-failure.json`, `level-10/circuit-breakers-and-bulkheads.json`, `level-10/back-pressure-and-flow-control.json`.
- **Source:** `runtime-core/CLAUDE.md` "RabbitMQ stuck — consumers hung" section.

### F3. Unbalanced SQL clusters (C1-C5)

- **Symptom:** Queries on heavy clusters slow; queries on light clusters fast. Per-tenant tail latency variable depending on placement.
- **Service(s):** SQL Server clusters C1-C5; per-tenant DBs.
- **Mechanism:** Sticky shard-key hash placement at account creation. No automatic rebalance as accounts grow. Eventually some clusters host many large tenants while others host many small ones.
- **Detection today:** Customer-side latency complaints; manual review.
- **Proposed SLO target:** Per-cluster utilization variance < 1.5× (max-cluster utilization ≤ 1.5 × min-cluster utilization). Monthly snapshot.
- **Course modules:** `level-3/partitioning-and-sharding.json`, `level-9/consistent-hashing.json`, `level-14/cloud-cost-estimation.json`, `level-14/architecture-review.json`.
- **Source:** `runtime-core/CLAUDE.md` "5 SQL clusters; uneven distribution causes slow queries".

### F4. MongoDB BSON discriminator brittleness

- **Symptom:** Inheritance changes to Control classes silently break runtime — some controls deserialize as base type and lose properties. Manifests as a screen with missing widgets.
- **Service(s):** runtime-core (Mongo serialization).
- **Mechanism:** `Startup.cs` (lines 198-213) registers `BsonClassMap` entries by hand. Adding a new Control subclass requires a manual addition. Forgotten registration → silent fallback to base type.
- **Detection today:** Manual code review on PRs touching `Controls/`. No CI enforcement.
- **Proposed SLO target:** Reflection-based PR-CI test asserting every `Control` subclass has a registered class map. Pass rate 100%.
- **Course modules:** `level-3/data-modeling-for-scale.json`, `level-7/clean-and-hexagonal.json`, `level-14/technology-decision-making.json`.
- **Source:** `runtime-core/CLAUDE.md` "MongoDB discriminators brittle" section.

### F5. Last-write-wins concurrency on Designer save

- **Symptom:** Two designers editing the same screen lose intermediate changes. The later save overwrites the earlier without warning.
- **Service(s):** Designer.Core.Api.
- **Mechanism:** No optimistic locking on screen updates. ETag-style versioning not implemented. Last write wins by definition.
- **Detection today:** Anecdotal user reports.
- **Proposed SLO target:** No SLO target — this is a correctness issue, not a reliability issue. Fix by adding ETag/version field to Screen; reject mismatched writes with 409.
- **Course modules:** `level-9/crdts-and-conflict-resolution.json`, `level-3/replication.json`, `level-1/consistency-models.json`.
- **Source:** `runtime-core/CLAUDE.md` "Concurrency: Last-write-wins" section.

### F6. IIS app-pool 503 on `runtime-core` stop

- **Symptom:** Runtime, Designer, RestApi, gateway-routed `/apps` endpoints all return 503. Whole runtime tier unreachable.
- **Service(s):** IIS app pool hosting runtime-core; cascades to ms-gateway-api responses.
- **Mechanism:** IIS app pool stopped (manual recycle, deploy, OOM kill). No auto-restart configured.
- **Detection today:** Health-endpoint monitor at the gateway level fires; on-call investigates.
- **Proposed SLO target:** runtime-core availability 99.95% (≤ 22 min/30d). Auto-restart on crash; deploy-time auto-recycle policy.
- **Course modules:** `level-10/disaster-recovery.json`, `level-7/deployment-patterns.json`, `level-10/observability.json`.
- **Source:** `runtime-core/CLAUDE.md` "IIS 503" section.

### F7. Dual BRE drift

- **Symptom:** A subset of accounts run `NewBRE` (event-driven), the rest run `LegacyBRE` (in-process). Behavior diverges on edge cases. Bug fixes ship to one but not the other.
- **Service(s):** runtime-core (BRE subsystem); legacy-bre-api.
- **Mechanism:** Per-account toggle via `NewBRE.BreEnabledAccounts`. Both engines maintained in parallel.
- **Detection today:** Inconsistent behavior reports.
- **Proposed SLO target:** Migration completeness: % of accounts on NewBRE. Target 100% by <date>.
- **Course modules:** `level-7/deployment-patterns.json` (strangler fig), `level-14/migration-strategies.json`, `level-6/feature-flags-and-ab-testing.json`.
- **Source:** `runtime-core/CLAUDE.md` "Dual BRE running" section.

### F8. ms-gateway-api Redis dependency for JWT cache

- **Symptom:** When Redis degrades, every gateway request misses cache and hits `ms-authentication-api`. Latency rises sharply across all authenticated paths. ms-authentication can be overwhelmed by the cache-miss storm.
- **Service(s):** ms-gateway-api; ms-authentication-api.
- **Mechanism:** JWT cache in Redis is the gateway's auth fast-path. Cache miss → synchronous validation call → ms-authentication is single-threaded relative to platform request rate.
- **Detection today:** Latency monitor on ms-gateway-api triggers; correlation with Redis health is manual.
- **Proposed SLO target:** ms-gateway-api availability 99.95% (≤ 22 min/30d) including degraded latency states. Redis cache hit rate > 95% steady-state alert.
- **Course modules:** `level-12/authentication-at-scale.json`, `level-4/distributed-caching.json`, `level-10/circuit-breakers-and-bulkheads.json`, `level-2/reverse-proxies-api-gateways.json`.
- **Source:** `triage-bot/CLAUDE.md` critical-path facts.

### F9. No formal SLOs for top critical flows

- **Symptom:** Performance targets exist in scattered CLAUDE.md files (e.g., "screen load < 200ms p95") but are not formal SLOs. There is no error-budget instrumentation; recommendations like F1-F8 have no shared denominator.
- **Service(s):** All.
- **Mechanism:** No designated owner for reliability cross-cuts. Conway's Law: teams own features, not reliability.
- **Detection today:** This monthly review IS the detection mechanism — the routine surfaces the gap each cycle until it's filled.
- **Proposed SLO target:** Define SLOs for top 3 critical flows in the next quarter:
  1. Screen runtime load — p95 latency < 200ms, success rate > 99.9% over 30d.
  2. App builder save — success rate > 99.9% over 30d.
  3. Action execution — end-to-end success rate > 99.9%, p95 latency < 5s.
- **Course modules:** `level-1/availability-and-slas.json`, `level-10/observability.json`, `level-14/conways-law-and-team-topology.json`, `level-14/architecture-review.json`.
- **Source:** Synthesised from absence of SLO documentation across all CLAUDE.md files.

---

## Maintenance

The stability-review routine reads this file at Phase 7 to compute error-budget burn. When a new failure mode appears in a monthly report's Findings, append a stub entry here in the same commit. When a recommendation closes (e.g., F1's monitor lands), mark the entry `Resolved: YYYY-MM` and keep the entry — it remains useful as historical context.

This file is **seed** until the routine has been running long enough (≥3 monthly reports) to validate the proposed SLO targets against real burn data. After that, edit the targets to reflect what the data shows is achievable.
