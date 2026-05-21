# Datadog log search query syntax — cheat sheet

The full DSL is at https://docs.datadoghq.com/logs/explorer/search_syntax/. This file covers the patterns that come up daily during incident triage.

## Boolean / grouping

| Operator | Example | Notes |
|---|---|---|
| Implicit AND | `service:foo status:error` | Space = AND |
| Explicit AND | `service:foo AND env:prod` | Operators are case-sensitive (must be ALL CAPS) |
| OR | `status:error OR status:warn` | |
| NOT | `service:foo NOT status:info` | Or `-status:info` |
| Grouping | `service:foo (status:error OR status:warn)` | |

## Tag (reserved attribute) facets

These are first-class — no `@` prefix.

| Facet | Example |
|---|---|
| `service` | `service:tables-fields` |
| `host` | `host:web-prod-1` |
| `env` | `env:prod` |
| `status` | `status:error` (values: `emergency`/`alert`/`critical`/`error`/`warning`/`notice`/`info`/`debug`) |
| `source` | `source:dotnet` |
| `version` | `version:1.2.3` |
| `trace_id` | `trace_id:abc123def456` |

## Custom attributes

Anything from your structured logs. Prefix with `@`.

| Pattern | Example |
|---|---|
| Field equals | `@http.status_code:500` |
| Field exists | `@user.id:*` |
| Field absent | `-@user.id:*` |
| Numeric range | `@duration:>1000000000` (nanoseconds) |
| Numeric range | `@http.status_code:[500 TO 599]` |
| Substring | `@http.url_details.path:*\/v1\/field\/*` (escape slashes) |

## Wildcards & phrases

- `*foo*` — substring search on the message body. Slow; prefer attribute filters.
- `"connection refused"` — exact phrase in the message.
- `foo*` — prefix on a single token.

## Common queries

| Goal | Query |
|---|---|
| All errors for a service | `service:tables-fields status:error` |
| 5xx responses | `service:tables-fields @http.status_code:[500 TO 599]` |
| Slow requests (> 2s, duration in ns) | `service:tables-fields @duration:>2000000000` |
| Logs for one trace | `trace_id:abc123` |
| Logs touching a specific endpoint | `service:tables-fields @http.url_details.path:*FieldList*` |
| Logs from one host | `host:i-0abc123` |
| Excluding a noisy logger | `service:tables-fields -@logger.name:HealthCheck` |

## Tips

- **`@field` vs `field`** — bare names hit reserved facets only. Anything from your JSON payload needs `@`.
- **Status is normalized** — Datadog maps `WARN` -> `warn`, `ERR` -> `error`, etc. Always lowercase.
- **Time windows are server-side** — passing `--from now-15m` is much cheaper than fetching 1h and filtering locally.
- **Indexes** — if the org has multiple log indexes (e.g. `main` vs `archive`), `--indexes main` cuts cost and latency.
- **Trace pivot** — once you have a `trace_id` from a log, hand it to `dd-apm get_trace.py --trace-id <id>` for the full request path.
