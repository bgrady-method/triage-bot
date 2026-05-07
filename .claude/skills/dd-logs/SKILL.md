---
name: dd-logs
description: Search and aggregate Datadog logs by service/host/trace, filter errors, find error concentrations, pivot to traces. TRIGGER when the user asks about Datadog logs, application errors, exceptions, request failures, or wants to investigate what a service was doing at a specific time.
user_invocable: true
---

# dd-logs — search and aggregate Datadog logs

## When to use

- "What errors is `tables-fields` throwing right now?"
- "Find me the log for trace `abc123`"
- "Where are the 5xx coming from?"
- "Did anything weird happen on `web-prod-3` between 14:00 and 14:15?"

Pre-req: `dd-setup` complete (`.env` populated, smoke test passes). If a script fails with a credential error, run the dd-setup smoke test first.

## Tools

| Script | Purpose |
|---|---|
| `scripts/search_logs.py` | Pull individual log events for a query + window. Returns trimmed JSON (timestamp, service, host, status, trace_id, message). Use `--raw` for the full Datadog payload. |
| `scripts/aggregate_logs.py` | Group log counts by facet (service, host, endpoint, etc.) — answers *"where is the noise concentrated"* in one call. Use this BEFORE search when scope is unclear. |

Reference: `references/query-syntax.md` — the Datadog log search DSL cheat sheet (read it the first time you write a non-trivial query).

## Standard triage flow

1. **Aggregate first.** Don't blindly fetch 1000 events. Run `aggregate_logs.py` to find the top services/hosts/endpoints producing the symptom:
   ```bash
   python .claude/skills/dd-logs/scripts/aggregate_logs.py \
     --query "status:error env:prod" --from now-1h --by service --top 5
   ```
2. **Drill into one bucket.** Take the noisiest service from step 1 and search:
   ```bash
   python .claude/skills/dd-logs/scripts/search_logs.py \
     --query "service:tables-fields status:error" --from now-15m --limit 20
   ```
3. **Pivot to traces.** Each event in the trimmed output has a `trace_id`. Hand it to `dd-apm`:
   ```bash
   python .claude/skills/dd-apm/scripts/get_trace.py --trace-id <id>
   ```

## Conventions

- **Time defaults**: `search_logs.py` uses `now-15m`, `aggregate_logs.py` uses `now-1h`. Aggregations need a wider window to be meaningful; searches narrow.
- **Limits**: `search_logs.py` defaults to 50 events. The hard server cap is 1000. Don't ask for more than 200 unless you're paginating deliberately.
- **Sort**: default `-timestamp` (newest first). Pass `--sort timestamp` for chronological.
- **Output**: stdout = JSON for further processing. Stderr gets a UI pivot link so you can hand the user a clickable URL.

## Gotchas

- **`@field` vs bare facets** — `service:foo` works; `app.name:foo` doesn't. Custom attributes need the `@` prefix (`@app.name:foo`). See `references/query-syntax.md`.
- **Status normalization** — Datadog lowercases `status`. Always query `status:error`, never `status:ERROR`.
- **No data ≠ no problem** — empty result sets often mean wrong service name, wrong env, or out-of-window. Sanity-check by widening to `--query "*" --from now-5m --limit 5` to confirm logs are flowing at all.
- **Cost of broad queries** — `--query "*" --from now-7d` is slow and expensive. Stay narrow.

## What this skill does NOT do

- No log writes (Datadog ingestion is push-only from agents anyway).
- No log archive / rehydration. Queries hit the live indexes only — for old data, use the Datadog UI.
- No live tailing. The Logs API is poll-based; for live tail use `datadog-ci logs tail` or the UI.
