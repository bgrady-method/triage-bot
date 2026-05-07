---
name: dd-apm
description: Search Datadog APM spans, fetch and visualize traces, list active services. TRIGGER when the user asks about traces, spans, slow endpoints, request latency breakdown, or wants to follow a request through services.
user_invocable: true
---

# dd-apm — Datadog APM trace and span inspection

## When to use

- "What's the slowest span in trace `abc123`?"
- "Show me all errored spans for `tables-fields` in the last 15 min."
- "Which endpoints are over 2 seconds right now?"
- "List the services reporting traffic in prod."
- "I have a `trace_id` from a log — pull the trace tree."

Pre-req: `dd-setup` complete.

## Tools

| Script | Purpose |
|---|---|
| `scripts/search_spans.py` | Search APM spans by query/window. Returns trimmed JSON (timestamp, service, resource, duration_ms, error, trace_id, span_id, parent_id). |
| `scripts/get_trace.py` | Fetch all spans for one `trace_id` and print as a tree (default) or raw JSON. Includes total duration and error count. |
| `scripts/list_services.py` | Discover active services via `trace.web.request.hits by {service}`. Returns hits, errors, error % per service. No service-catalog scope needed. |

## Standard flow

1. **Pivot from a log** — copy `trace_id` from `dd-logs search_logs.py` output, then:
   ```bash
   python .claude/skills/dd-apm/scripts/get_trace.py --trace-id <id>
   ```
2. **Find slow / errored spans** — `search_spans.py` with `@duration:>1000000000` (>1s) or `status:error`.
3. **Map traffic across services** — `list_services.py --env prod` to see who's busy and where errors are concentrated.

## Span query syntax

Same DSL as logs (see `.claude/skills/dd-logs/references/query-syntax.md`), with APM-specific facets:

| Facet | Example |
|---|---|
| `service` | `service:tables-fields` |
| `env` | `env:prod` |
| `resource_name` | `resource_name:GET\\ /v1/field/Get` |
| `operation_name` / `name` | `operation_name:aspnet_core.request` |
| `@duration` (nanoseconds) | `@duration:>2000000000` (>2s), `@duration:[500000000 TO 2000000000]` (500ms-2s) |
| `status` | `status:error` |
| `trace_id` | `trace_id:abc123def456` |
| `span_id` | `span_id:9876543210` |
| `parent_id` | `parent_id:1234567890` |
| `host` | `host:web-prod-1` |
| `@http.status_code` | `@http.status_code:[500 TO 599]` |

## Conventions

- **Durations are ns on the wire** — the trimmed output converts to ms for sanity. When writing queries, multiply ms by 1,000,000.
- **Time defaults**: `search_spans.py` uses `now-15m`, `get_trace.py` uses `now-1h` (traces are usually fresh-ish, but widen to `now-24h` if not found).
- **Trace search index retention** — the searchable index defaults to 15 days. Older traces exist in raw form but aren't queryable here. Use the UI for archive lookups.

## Gotchas

- **`trace_id` is a string** even though it looks numeric — pass it raw, no quotes (the script handles escaping).
- **Tree may have multiple roots** if the trace is incomplete (early spans dropped, or trace fragmented across regions). The renderer shows them sequentially.
- **Span sort** — `search_spans.py` defaults to `-timestamp` (newest first). For a chronological scan use `--sort timestamp`.
- **`list_services.py` queries request-style integrations only** — it unions across `trace.http.request`, `trace.web.request`, `trace.aspnet[_core].request`, `trace.servlet.request`, `trace.django/express/rack/rails/gin/echo/fastapi/flask/node.request`. Background workers, batch jobs, and async consumers don't show up. For those, hand the integration name to `dd-metrics` directly (e.g. `trace.rabbitmq.consume.hits by {service}`). Pass `--metric-prefix` to narrow or override.
- **`apm_read` scope alone** is enough for span search and metric-based service discovery. The Service Catalog API (`/api/v2/services`) needs `apm_service_catalog_read`, which we deliberately skip — `list_services.py` works around it.

## What this skill does NOT do

- No span/trace mutations — read-only.
- No service-catalog metadata edits.
- No live profile or continuous profiling data — that's a different API.
- No span-link or distributed-trace cross-account stitching.
