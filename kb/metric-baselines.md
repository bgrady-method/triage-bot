# Metric baselines (env:prod)

Reference values for "normal" so a deviation is one-glance obvious. Seeded from the 2026-05-07 RTC Screen Load investigation; grown by the `kb-approver` routine as future incidents capture new baselines.

> **Use:** before reporting "elevated vs baseline" in an investigation summary, look up the concrete number here. If the metric isn't listed, capture a baseline value at investigation time and propose a new row to `kb-approver`.

## Per-metric baselines

| Metric | Scope | Baseline | Last anomaly seen | Monitor + threshold |
|---|---|---|---|---|
| `p95:trace.aspnet_core.request` | `service:runtime-core-api, resource_name:post_/api/v1/runtime/load/_screenid*` | 0.7–1.5s | 10.7s max, 12.3s peak (2026-05-07) | 115456700 — `p95 last_5m > 3s` |
| `p95:trace.aspnet_core.request` | `service:runtime-core-api, resource_name:post_/api/v1/runtime/_actionid_*` | unknown — record on next incident | — | 117279738 — `p95 last_10m > 3s` |
| `p90:trace.aspnet_core.request` | `service:runtime-core-api` | unknown | — | 17872725 — `p90 last_10m > 2s` |
| `sum:trace.aspnet_core.request.hits.as_rate()` | `service:runtime-core-api, resource_name:post_/api/v1/runtime/load/_screenid*` | 3.65–11.85/s, avg ~9 | unchanged 2026-05-07 | — |
| `sum:trace.aspnet_core.request.errors.as_rate()` | `service:runtime-core-api, resource_name:post_/api/v1/runtime/load/_screenid*` | 0 (no series) | 0 (still no errors during latency spike) | — |
| Service hourly hits | `service:runtime-core-api, env:prod` | ~302k/hr, ~1.74% errors | unchanged 2026-05-07 | — |
| Service hourly hits | `service:gateway, env:prod` | ~555k/hr, ~0.96% errors | unchanged 2026-05-07 | — |
| Service hourly hits | `service:classic/syncservices, env:prod` | ~317k/hr, ~0.03% errors | unchanged 2026-05-07 | — |
| `p95:trace.redis.command` | `service:runtime-core-api*, env:prod` | ~3ms | 1.36s on 2026-05-07 (~400×) | none |
| `max:trace.redis.command` | `service:runtime-core-api*, env:prod` | <100ms | 4.0s on 2026-05-07 | none |
| `sum:trace.redis.command.errors.as_count()` | `service:runtime-core-api*, env:prod` | 0 | 61 in single 20s bucket on 2026-05-07 | none |
| `sum:trace.redis.command.hits.as_rate()` | `service:runtime-core-api*, env:prod` | 285–735/s, avg ~571 | unchanged 2026-05-07 | — |

## Known monitors — runtime-team (env:prod)

| ID | Name | Query | Window | Threshold | Last triggered |
|---|---|---|---|---|---|
| 115456700 | RTC Screen Load high p95 | `percentile(last_5m):p95:trace.aspnet_core.request{env:prod,service:runtime-core-api,resource_name:post_/api/v1/runtime/load/_screenid*}` | last_5m | > 3 | 2026-05-07T13:39Z |
| 117279738 | RTC Action Execution high p95 | `percentile(last_10m):p95:trace.aspnet_core.request{env:prod,service:runtime-core-api,resource_name:post_/api/v1/runtime/_actionid_*}` | last_10m | > 3 | — |
| 117424880 | runtime-core-api throughput anomaly | `anomalies(sum:trace.aspnet_core.request.hits{...}.as_count(), 'agile', 3, ...)` | last_4h | anomaly | — |
| 17872725 | runtime-core-api high p90 latency | `avg(last_10m):p90:trace.aspnet_core.request{env:prod,service:runtime-core-api}` | last_10m | > 2 | — |
| 17420774 | runtime-core-api high error rate | `sum(last_10m):errors/hits` | last_10m | > 0.05 | — |

## Coverage gaps

- **No infra-layer Redis monitor** for runtime-core-api or for the shared Redis cluster as a whole. A cluster-wide Redis blip will only surface as a downstream symptom monitor on the busiest consumer (this is what 115456700 caught on 2026-05-07). Adding `p95:trace.redis.command{env:prod} > 0.5s` as an infra-layer monitor would alert on the cause, not the symptom.
- The other Redis monitors (65577145/65577146) are bound to `service:ms-account-api-redis` only.

## How to grow this file

When an investigation discovers a new metric/scope or refutes a baseline:
1. Capture the metric query and the observed normal range.
2. Append a row in the appropriate table, keyed by `(metric, scope)`.
3. The `kb-approver` routine reviews proposed rows before merging.

Cross-references:
- `kb/dd-trace-metric-tags.md` — which `by {X}` queries return `X:N/A`
- `kb/logstash-coverage.md` — which services are NOT searchable in ES
- `kb/dd-skill-tooling-status.md` — which DD skill scripts are working / broken
