# Elasticsearch query_string syntax — cheat sheet

The `es-logs` scripts use Lucene `query_string` (the same language as Kibana's Discover in "Lucene" mode). Full reference: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html.

## Boolean / grouping

| Operator | Example | Notes |
|---|---|---|
| AND (default) | `Level:Error host.name:PROD-UTILITY-03` | Space = AND. Use `AND` to be explicit. |
| OR | `Level:(Error OR Fatal)` | Operators must be UPPERCASE. |
| NOT | `Level:Error NOT Context:HealthCheck` | Or `-Context:HealthCheck`. |
| Grouping | `Level:Error AND (host.name:PROD-* OR host.name:WEB-*)` | |

## Field filters

| Pattern | Example |
|---|---|
| Equals | `Level:Error` |
| Exists | `_exists_:Exception` or `Exception:*` |
| Missing | `NOT _exists_:Exception` |
| Phrase | `message:"There is an error in XML document"` |
| Wildcard (value) | `host.name:PROD-*` (analyze_wildcard=true is enabled in these scripts) |
| Range (time) | `@timestamp:[now-1h TO now]` (but `--from` / `--to` are easier) |

## Method's field shape (verified against live logstash-* index, 2026-04-15)

Method's logs are **flat top-level fields**, NOT nested under `fields.*` the way typical Serilog configs do. Use these:

| Field | Type | Purpose | Example values |
|---|---|---|---|
| `@timestamp` | date | Event time (primary time field) | `2026-04-15T20:42:35.190Z` |
| `Level` | text + `.keyword` | Log level (capitalized) | `Error`, `Warn`, `Info`, `Fatal`, `Debug` |
| `message` | text | Full rendered log line (raw, includes pipes from the emitter) | `2026-04-15 15:42:35.1903|PROD-UTILITY-03|Error|…` |
| `Context` | text + `.keyword` | Logger name, FQN of the class | `Com.Method.SyncEngine.DefalutConverter` |
| `Action` | text + `.keyword` | Method / operation name | `Deserialize`, `ProcessTask` |
| `Account` | text + `.keyword` | Tenant / customer identifier | `m11mobilitycityautomation` |
| `Exception` | text | Full exception string with stack trace | `System.InvalidOperationException: …\r\n   at …` |
| `Error` | text | Short error message (without stack) | `There is an error in XML document (0, 0).` |
| `type` | text + `.keyword` | Log source / consumer label | `SyncHourlyConsumers` |
| `host.name` | text + `.keyword` | Emitting host | `ip-172-31-121-218` |
| `hostname` | text | Hostname as reported by the emitter (often different case) | `PROD-UTILITY-03` |
| `thread` | text + `.keyword` | Thread name | `Thread-72` |
| `event.original` | text | The raw unparsed log line (duplicate of message) | — |
| `log.file.path` | text | Source log file on the emitting host | `/opt/logs/prod-utility-03/logs/qbo-sync-consumers/2026-04-15_error.log` |
| `tags` | keyword array | Logstash pipeline tags | `["multiline"]` |

**Not present** (despite common docs suggesting otherwise):
- `fields.ServiceName`, `fields.Application`, `fields.RequestId`, `fields.Exception`, `fields.SourceContext` — none exist in this deployment
- `service`, `service.name`, `app`, `application` — none exist
- `trace.id`, `trace_id`, `correlation_id` — Method's logs don't carry a request correlation id today
- `log.level` — the level lives at `Level` (capitalized), not `log.level`

## Indices

- **Monthly** rollups, not daily: `logstash-2026.01`, `logstash-2026.02`, `logstash-2026.03`, `logstash-2026.04`. Pattern `logstash-*` covers all of them.
- No data streams, no aliases (as of the verification — `list_indices.py` prints what exists).

## Time range

Passed via `--from` / `--to`, not inside `--query`. Accepts ES date math:

- Relative: `now`, `now-15m`, `now-1h`, `now-1d`, `now-1M`
- Rounded: `now-1d/d` (start of yesterday), `now/h` (start of current hour)
- Absolute ISO: `2026-04-15T19:30:00Z`
- Epoch millis: `1713213045000`

## Common query recipes (verified against Method's shape)

| Goal | Query |
|---|---|
| All errors | `Level:Error` |
| Errors and fatals | `Level:(Error OR Fatal)` |
| Errors from one logger | `Level:Error AND Context:"Com.Method.SyncEngine.DefalutConverter"` |
| Errors for one tenant | `Level:Error AND Account:"m11mobilitycityautomation"` |
| Particular exception type | `Exception:"System.NullReferenceException"` |
| Errors from one host | `Level:Error AND host.name:PROD-UTILITY-03` |
| One consumer / log source | `type:"SyncHourlyConsumers"` |
| Exclude a noisy logger | `Level:Error NOT Context:"Com.Method.SyncEngine.HealthCheck"` |
| Message phrase | `message:"Root element is missing"` |
| Specific action | `Action:"Deserialize" AND Level:Error` |

## Aggregation field tips

- Most text fields have a `.keyword` sub-field. `aggregate_logs.py` and `field_stats.py` add `.keyword` automatically for single-word field names. For dotted names, they pass through as-is.
- Useful group-by dimensions for Method: `Context` (the logger, ≈ service), `Action` (operation), `Account` (tenant), `type` (consumer label), `host.name` (emitting host), `Level` (severity breakdown).
- Counter-intuitive: there's no "ServiceName" field. If you want "which service is this from", use `Context` (FQN of the class) or `type` (pipeline label, coarser).

## Special characters

These need escaping with `\` in queries: `+ - = && || > < ! ( ) { } [ ] ^ " ~ * ? : \ /`. In the shell, wrap the whole query in single quotes: `--query 'Context:"Com.Method.Foo" AND Account:"xyz"'`.
