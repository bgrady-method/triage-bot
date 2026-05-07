# Datadog trace-metric tag presence

Which `by {X}` queries return useful series and which return `X:N/A` for the entire payload. Consulting this before issuing a `by {X}` query saves at least one wasted turn per N/A facet (each one costs the same as the original query plus the time to interpret the empty result).

> **Use:** before running `dd_search.py metric --query "<...>{...} by {X}"`, find the metric prefix in the table below. If `X` is in the **Always N/A** column, fall back to the next dimension in the **Fallback chain**.

## Tag presence by metric prefix

| Metric prefix | Reliably present | Often present | Always N/A | Fallback chain |
|---|---|---|---|---|
| `trace.aspnet_core.request` (.NET Core services) | `service`, `env`, `resource_name` | `host` (sometimes) | — | `host` → `service` → `env` |
| `trace.aspnet.request` (Tier 3 .NET Framework) | `service`, `env`, `resource_name` | `host` (sometimes) | — | `host` → `service` → `env` |
| `trace.redis.command` | `service`, `env` | — | `host`, `redis.command`, `error.type` | `host`/`redis.command` → `service` |
| `trace.redis.command.errors` | `service`, `env` | — | `host`, `error.type` | `error.type` → `service` |
| `trace.sql_server.query` | `service`, `env` | — | unknown — record on next incident | `host` → `service` |
| `trace.mongodb.query` | `service`, `env` | — | unknown — record on next incident | `host` → `service` |
| `trace.http.request` | `service`, `env` | — | unknown — record on next incident | `host` → `service` |

## Why this matters

The dd-trace-dotnet integration in Method's services doesn't promote certain tags to metric facets. The trace span itself carries `error.type`, `redis.command`, and `host` — but those don't roll up to the `trace.*.command.errors` metric. A `by {error.type}` query against `trace.redis.command.errors` returned `error.type:N/A` for the entire 2026-05-07 series, costing one round-trip to discover.

To read the actual exception class for a failed Redis span, the bot must:
1. Fetch one trace via the DD UI (or `get_trace.py` if it's working — see `kb/dd-skill-tooling-status.md`).
2. Read the span's `error.type` / `error.stack` directly from the trace tree.

Long-term fix is at the dd-trace agent config level (instrument with the missing tags); out of scope for the bot.

## How to grow this file

When an investigation discovers a metric where `by {X}` returns `X:N/A`:
1. Add a row to the table above, or update an existing row's "Always N/A" column.
2. The `kb-approver` routine reviews proposed rows before merging.

Cross-references:
- `kb/metric-baselines.md` — baseline values for these metrics
- `kb/dd-skill-tooling-status.md` — which DD skill scripts work
