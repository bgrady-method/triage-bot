# System-design course — navigation index

This directory mirrors https://github.com/benjgrad/learn/tree/main/ai-fluency-platform/content/system-design verbatim. The course is the routine's reference library — every recommendation in `stability-reviews/YYYY-MM/report.md` must cite at least one module by path.

The mirror is refreshed by `scripts/sync_course_content.py`. Re-run that any time the upstream course updates.

## Required navigation steps (in order)

For every cluster the routine analyses:

1. **CLASSIFY** the cluster against the Symptom Taxonomy below. Pick exactly one primary class. (A cluster can secondarily fit another class; record that in the report's "secondary symptom" field.)
2. **LOOK UP** the matched modules in the Symptom-to-Module Map.
3. **READ** those module JSONs from `level-N/<slug>.json` with the Read tool. Read primary modules in full. Read secondary modules only if primary doesn't fully explain the cluster.
4. **APPLY** at least one principle from each consulted module to the recommendation. The principle must be quoted or paraphrased in the report — not just cited.
5. **CITE** the module path(s) in the report's "Course module references" field, formatted as `level-N/<slug>.json`.

If a recommendation does not cite at least one course module path, the report fails the playbook's checklist. Tighten the symptom classification or expand to secondaries before bypassing.

## Symptom Taxonomy (8 classes)

| Class | Definition | Typical signal |
|-------|------------|----------------|
| **AVAILABILITY_LOSS** | Service unreachable, returns errors, or `No Data` for golden signals. | DD monitor in Alert/No-Data state; 5xx surge; consumer crash. |
| **LATENCY_REGRESSION** | p95/p99 climbing beyond baseline, timeouts increasing. | DD `trace.web.request.duration` shifted up vs 24h-prior. |
| **CAPACITY_LIMIT** | Resource exhaustion: CPU, memory, connection pool, queue, disk. | OOM, ThreadPool starvation, connection-pool drained, queue depth growing. |
| **DATA_INCONSISTENCY** | Stale, conflicting, or missing data perceived by the user. | Cache stale; replication lag; missing audit row; lost write. |
| **SECURITY_INCIDENT** | Auth failure, unauthorized access, exposure, suspected attack. | Spike in 401/403; failed-login pattern; secret leakage. |
| **DEPLOYMENT_RISK** | Failure correlated with a recent deploy or schema change. | Step change in error rate or latency at deploy timestamp. |
| **DEPENDENCY_FAILURE** | Upstream / downstream service or third-party API failing. | QuickBooks 5xx; SQL connection refused; RabbitMQ broker down. |
| **COST_OUTLIER** | Unexpected resource spend or scaling event. | DD billing alert; uncached requests slamming a paid API. |

## Symptom-to-Module Map

Module identifiers are `<level>.<order>` — e.g. `1.3` is `level-1/availability-and-slas.json` (the third graded module in level 1). Resolve to file paths via `curriculum.json` if needed.

| Symptom | Primary modules | Secondary modules |
|---------|-----------------|-------------------|
| AVAILABILITY_LOSS    | 1.3, 10.4, 10.6              | 1.2, 5.6, 9.1, 10.2     |
| LATENCY_REGRESSION   | 1.2, 4.1, 4.2, 4.3, 10.4     | 2.3, 3.5, 5.4           |
| CAPACITY_LIMIT       | 1.5, 10.1, 10.3              | 4.3, 6.4, 11.2          |
| DATA_INCONSISTENCY   | 1.4, 3.3, 4.2, 9.5           | 7.1, 9.1, 11.4, 5.5     |
| SECURITY_INCIDENT    | 12.1, 12.2, 12.3, 12.4, 12.5 | 2.4, 14.4               |
| DEPLOYMENT_RISK      | 7.5, 14.2                    | 3.3, 14.4, 14.5         |
| DEPENDENCY_FAILURE   | 5.6, 10.2                    | 5.4, 9.7, 10.3, 7.7     |
| COST_OUTLIER         | 14.1                         | 4.1, 4.5, 6.1, 6.2      |

## Cross-walks

- If a cluster fits two primary classes equally well, classify by the **most actionable** class (the one whose recommendation requires the smallest behavior change for the team).
- If primary modules don't explain the cluster, expand to secondaries.
- If still unmatched, append to the **Gaps** section below — the next routine run reads this to decide whether the taxonomy needs a 9th class.

## Level guide (for orientation)

| Level | Title | Stability relevance |
|-------|-------|---------------------|
| 1 | The Fundamentals | Always relevant. SLOs, latency, throughput, estimation, consistency basics. |
| 2 | The Network | DNS / CDN / load balancers / protocols. Read for AVAILABILITY_LOSS at the edge. |
| 3 | The Data Layer | Read for DATA_INCONSISTENCY, CAPACITY_LIMIT on storage. |
| 4 | The Speed Layer | Caching — read for LATENCY_REGRESSION and stale-cache DATA_INCONSISTENCY. |
| 5 | The Communication Layer | APIs, message queues, async patterns. Read for DEPENDENCY_FAILURE, AVAILABILITY_LOSS in async paths. |
| 6 | The Component Catalog | Containers, search, queues, monitoring, payment, feature flags. Cross-reference. |
| 7 | The Pattern Library | Event-driven, CQRS, DDD, deployment patterns, distributed transactions. |
| 8 | The Architecture | Monolith vs micro, BFF, service mesh, serverless, cross-cutting concerns. |
| 9 | The Distributed Systems | CAP, consensus, clocks, CRDTs, consistent hashing — read for the hard DATA_INCONSISTENCY cases. |
| 10 | **The Resilience Layer** | **Most direct stability content.** Rate limiting, circuit breakers, observability, chaos, DR. |
| 11 | The Data Pipeline | Batch + stream processing, event sourcing, CDC. |
| 12 | The Security Layer | Auth, encryption, zero-trust, secrets — read for SECURITY_INCIDENT. |
| 13 | The Design Interview | Worked end-to-end designs. Useful as analogy when proposing a new subsystem. |
| 14 | The Architect's Intuition | Cost, migration, Conway's Law, ADRs, architecture review. Read when recommending org / process changes. |

## How to refresh the mirror

```bash
python scripts/sync_course_content.py
```

The script is idempotent. Re-run any time the upstream course updates. Commit the diff alongside the next stability review run so the cloud routine's clone has the latest content.

## Gaps

(Empty. Append unmatched cluster patterns here as they appear during runs. Format: `YYYY-MM <symptom not in taxonomy> — <one-line description>`.)
