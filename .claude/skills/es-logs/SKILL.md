---
name: es-logs
description: Search and aggregate Method's production logs in Elasticsearch / Logstash. Find errors, count patterns, drill into individual requests. TRIGGER when the user asks about production logs, Kibana, Logstash, "what's happening in prod", error patterns, request IDs, or wants to investigate a service's recent behavior.
user_invocable: true
---

# es-logs — search and aggregate Method's production Logstash

## When to use

- "What errors is `tables-fields` throwing in prod right now?"
- "Find the log line for request id `abc-123`."
- "How many 5xx did we serve in the last hour, and on which endpoints?"
- "Is that exception actually happening or is it a one-off?"

Kibana UI: https://logstash.method.me. These scripts talk to the ES REST API directly so results come back as JSON for further processing — use the Kibana URL for visual exploration.

Pre-req: `es-setup` complete (`.env` populated, smoke test passes).

## Tools

| Script | Purpose |
|---|---|
| `scripts/search_logs.py` | Pull individual log hits for a query + window. Default: trimmed JSON per hit (timestamp, host, service, level, message, trace id, \_index, \_id). `--raw` for untrimmed ES response, `--no-trim` to keep full _source, `--fields` to project. |
| `scripts/aggregate_logs.py` | Terms or date-histogram aggregations. Answers "where is this concentrated". Supports multi-level nesting (`--by service --by host`). |
| `scripts/field_stats.py` | Cardinality + top-N values for one field. Fast way to ask "how many distinct X are there, and what's the distribution". |

Reference: `references/query-syntax.md` — Lucene `query_string` cheat sheet with Method-specific fields (`fields.ServiceName`, `fields.RequestId`, etc.). Read once when you write a non-trivial query.

## Standard triage flow

1. **Sanity check the pipeline.** If you're unsure logs are flowing, start wide:
   ```bash
   python .claude/skills/es-logs/scripts/search_logs.py --query "*" --from now-5m --limit 3
   ```
2. **Aggregate to find concentration.** Don't fetch thousands of hits blind:
   ```bash
   python .claude/skills/es-logs/scripts/aggregate_logs.py \
     --query "level:(ERROR OR FATAL)" --from now-1h --by fields.ServiceName --top 10
   ```
3. **Drill into one bucket.** Take the noisy service and search its errors:
   ```bash
   python .claude/skills/es-logs/scripts/search_logs.py \
     --query 'level:ERROR AND fields.ServiceName:"tables-fields"' \
     --from now-15m --limit 20
   ```
4. **Pivot to a specific request.** The trimmed output exposes `trace` (whatever trace/request id the log has). Widen to the full request:
   ```bash
   python .claude/skills/es-logs/scripts/search_logs.py \
     --query 'fields.RequestId:"<id-from-step-3>"' --from now-30m --limit 100 --sort asc
   ```

## Conventions

- **Query syntax:** Lucene `query_string` (same as Kibana in "Lucene" mode). See `references/query-syntax.md`.
- **Time defaults:** `search_logs.py` → `now-15m`. `aggregate_logs.py` → `now-1h`. Aggregations need a wider window to be meaningful; searches narrow.
- **Time format:** any ES date math (`now-15m`, `now-1d/d`, ISO 8601, unix ms). Pass straight through — no client-side parsing.
- **Time field:** defaults to `@timestamp`. Override with `--time-field` if your index uses something else.
- **Limits:** search defaults to 50 hits, server cap 10,000. Don't request more than ~200 unless you're scrolling a specific correlation.
- **`.keyword` for aggregations:** text fields are tokenized. The aggregation scripts add `.keyword` automatically for single-word names. If your field is already dotted, it passes through — if aggregation errors with "illegal_argument_exception", inspect the mapping with `es-indices describe_mapping.py`.
- **Output:** stdout = JSON. Stderr = a Kibana Discover pivot link so you can hand the user a clickable URL.

## Gotchas

- **Empty results ≠ no problem.** Could be wrong service name, wrong index, or out-of-window. Sanity-check with `search_logs.py --query "*" --from now-5m --limit 3` before concluding "no errors".
- **Case matters on values inside `.keyword`.** `fields.ServiceName.keyword:tables-fields` won't match `Tables-Fields`. For analyzed text fields, case is folded; for `.keyword`, it's not.
- **Quotes in shell.** Wrap the whole `--query` in single quotes so the shell doesn't eat the double quotes inside: `--query 'level:ERROR AND fields.ServiceName:"tables-fields"'`.
- **Field paths vary by logger.** Serilog emits `fields.<Name>`; Filebeat emits `<name>` or dotted paths. If a field doesn't match, check the mapping or peek at a raw hit (`search_logs.py --limit 1 --no-trim --raw`).
- **Index rollover.** `logstash-*` matches many daily indices. If `ES_DEFAULT_INDEX` is too narrow (e.g. `logstash-2026.04.14`), widen it.
- **Cost.** `--query "*" --from now-30d` is slow and expensive on a shared cluster. Stay narrow; widen deliberately.
- **Message truncation.** The trimmed view clips message text at ~800 chars (with a "+N chars" marker). Use `--no-trim --raw` if you need the full payload.

## What this skill does NOT do

- No writes. Read-only by design.
- No Kibana saved objects (searches, dashboards, visualizations). Use the Kibana UI.
- No live tail. Each invocation is a point-in-time query.
- No cross-cluster search. Queries hit the cluster in `ES_SEARCH_ENDPOINT` only.
