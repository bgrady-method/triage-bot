---
name: dd-metrics
description: Query Datadog metric timeseries (latency, error rate, throughput, system metrics) and list dashboards. TRIGGER when the user asks about metric values, golden signals, dashboard URLs, or wants to verify a monitor's underlying query against current data.
user_invocable: true
---

# dd-metrics — Datadog metric queries

## When to use

- "What's `tables-fields`'s p95 latency right now?"
- "Show me request rate for the last 4 hours."
- "Does this monitor's query actually return what we think it does?"
- "Find the `tables-fields` SRE dashboard."

Pre-req: `dd-setup` complete.

## Tools

| Script | Purpose |
|---|---|
| `scripts/query_timeseries.py` | Run any Datadog metric query and get back the timeseries. Default output is summary stats per series (min/max/avg/last) + sample of head/tail points. Use `--raw` for the full point arrays. |
| `scripts/list_dashboards.py` | List dashboards, optionally filtered by title substring. Returns id, title, description, URL. |

## Metric query language — quick reference

```
<aggregator>:<metric>{<scope>}[<rollup>] [by {<group_by>}]
```

| Part | Examples |
|---|---|
| Aggregator | `avg`, `sum`, `min`, `max`, `count`, `p50`, `p75`, `p90`, `p95`, `p99` |
| Metric | `system.cpu.user`, `trace.web.request.duration`, `trace.web.request.errors`, `trace.web.request.hits` |
| Scope | `{*}`, `{service:tables-fields}`, `{service:foo,env:prod}`, `{!status:ok}` |
| Rollup | `.rollup(60)` (60s buckets), `.as_rate()` (per-second rate), `.as_count()`, `.fill(zero)` |
| Group by | `by {host}`, `by {service,resource_name}` |

Common patterns:

| Goal | Query |
|---|---|
| CPU per host | `avg:system.cpu.user{*} by {host}` |
| Request rate | `sum:trace.web.request.hits{service:tables-fields}.as_rate()` |
| p95 latency by endpoint | `p95:trace.web.request.duration{service:tables-fields} by {resource_name}` |
| Error rate | `sum:trace.web.request.errors{service:tables-fields}.as_rate()` |
| Error % | `(sum:trace.web.request.errors{service:tables-fields} / sum:trace.web.request.hits{service:tables-fields}) * 100` |
| Memory | `avg:system.mem.used{host:web-prod-1}` |

## Standard flow

1. **Verify a monitor's query** — copy the `query` field from `dd-monitors get_monitor.py --summary` and run it through `query_timeseries.py` to see the live values.
2. **Pull golden signals during an incident** — for each affected service, run three queries: rate, error rate, p95 latency. Compare to the same window from the previous day for context.
3. **Find a dashboard** — `list_dashboards.py --filter <service>` returns clickable URLs.

## Conventions

- **Time defaults**: `--from now-1h --to now`. Widen for trend, narrow for "what's happening right now."
- **Output**: stats (count/min/max/avg/last) + 5-point head and tail samples. Pass `--raw` if you need every point (e.g. for charting).
- **Series count**: a `by {host}` query can return hundreds of series. The trimmed output keeps it readable; for the full set use `--raw` and pipe to `jq`.

## Gotchas

- **Rate vs raw count** — `trace.web.request.hits` without `.as_rate()` is a counter; the value depends on the rollup window. For "requests per second", always `.as_rate()`.
- **No data ≠ zero** — by default, missing buckets render as `null`. Add `.fill(zero)` for math (otherwise an `error_rate / hits` query returns null when one side is missing).
- **`status:` is a metric tag, not the log facet** — confusing because `dd-logs` also has `status`. They're different namespaces.
- **`resource_name`** in trace metrics is the endpoint path / SQL statement / cache key, depending on the integration. Useful for "which endpoint is slow" but cardinality varies.
- **`status` field on response** — the v1 query API returns `"status": "ok"` even on errors with empty `series`. Always check `series_count` and `error`.
- **Time window cost** — `now-7d` is fine for one-metric queries but slow for `by` clauses. If a query times out, narrow the window or remove the `by`.

## What this skill does NOT do

- No metric submission — read-only.
- No dashboard creation/editing — `list_dashboards.py` is read-only. To edit a dashboard, use the UI.
- No metric metadata lookup (units, tags) — add a separate script if needed (`/api/v1/metrics/{metric_name}`).
- No formula-based queries via the v2 `/query/scalar` API yet — `query_timeseries.py` uses v1, which handles all the common cases. Add a v2 script if/when a complex multi-metric formula is needed.
