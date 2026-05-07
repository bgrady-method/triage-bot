---
name: dd-investigate
description: Top-level Datadog incident triage playbook — composes dd-monitors / dd-logs / dd-metrics / dd-apm to answer "what's broken and why". TRIGGER when the user says "what's wrong in datadog", "investigate this incident", "the service is broken", "something's on fire", "page just fired", or wants a guided multi-signal triage.
user_invocable: true
---

# dd-investigate — Datadog incident triage orchestrator

This skill is a playbook, not a script. It chains the four `dd-*` data skills in the order that gets to a useful answer fastest. Use it when you don't yet know which surface (monitors, logs, metrics, traces) holds the smoking gun.

## When to use

- "Page just fired for `tables-fields` — what's going on?"
- "User reports the API is slow. Investigate."
- "Errors in prod. Where?"
- "Something is wrong but I don't know where to look."

If the user already knows the surface ("show me the trace for X", "is monitor 123 firing"), skip this skill and go straight to `dd-logs` / `dd-apm` / `dd-monitors` / `dd-metrics`.

Pre-req: `dd-setup` complete.

## Step 0 — Confirm scope

Before running any scripts, get three things from the user (or infer from context):

1. **Affected service / component** — e.g. `tables-fields`. If unknown, run `list_services.py --env prod` to enumerate candidates.
2. **Time window** — when did this start? Default to `now-30m` if unstated, but ask if it's a longer-running issue.
3. **Symptom** — one of: alert fired, latency, errors, no-data, customer report, deploy-related, *unknown*.

Do not skip this step. Investigating the wrong service for the wrong window is the most common waste of time.

## Step 1 — What's already firing?

```bash
python .claude/skills/dd-monitors/scripts/list_monitors.py \
  --tags "service:<svc>,env:prod" \
  --state Alert --state "No Data"
```

Note any monitor IDs that are firing. For each, get the details:

```bash
python .claude/skills/dd-monitors/scripts/get_monitor.py --id <id> --summary
```

The `query` field tells you what dimension the monitor is tracking (latency, errors, request rate, etc.). The `failing_groups` and `last_triggered_ts` tell you when and where.

**If a monitor is firing**: skip to step 3 (correlate with metrics) and step 4 (find the matching logs / traces) for that dimension.

**If nothing is firing but the user reports a problem**: go to step 2 — telemetry may be lagging, or the issue may be below thresholds.

## Step 2 — Where are the errors concentrated?

```bash
python .claude/skills/dd-logs/scripts/aggregate_logs.py \
  --query "service:<svc> status:error env:prod" \
  --from now-30m --by service --by host --top 10
```

If one host or one path dominates, focus there. If errors are evenly distributed, the cause is probably global (config, dependency, deploy).

For 5xx specifically:

```bash
python .claude/skills/dd-logs/scripts/aggregate_logs.py \
  --query "service:<svc> @http.status_code:[500 TO 599]" \
  --from now-30m --by "@http.url_details.path" --top 10
```

## Step 3 — What do the golden signals say?

Run all three for the affected service and compare to the same window 24h ago:

```bash
# Request rate
python .claude/skills/dd-metrics/scripts/query_timeseries.py \
  --query "sum:trace.web.request.hits{service:<svc>,env:prod}.as_rate()" \
  --from now-1h

# Error rate
python .claude/skills/dd-metrics/scripts/query_timeseries.py \
  --query "sum:trace.web.request.errors{service:<svc>,env:prod}.as_rate()" \
  --from now-1h

# p95 latency by endpoint
python .claude/skills/dd-metrics/scripts/query_timeseries.py \
  --query "p95:trace.web.request.duration{service:<svc>,env:prod} by {resource_name}" \
  --from now-1h
```

Look for:
- Sudden cliffs (rate dropped to zero -> service down or upstream broken)
- Step changes (latency doubled at 14:32 -> deploy or config change)
- Drift (errors creeping up -> resource exhaustion, leak)

## Step 4 — Pull a representative trace

Take a recent error log and grab its `trace_id`:

```bash
python .claude/skills/dd-logs/scripts/search_logs.py \
  --query "service:<svc> status:error" --from now-15m --limit 5
```

Then expand it:

```bash
python .claude/skills/dd-apm/scripts/get_trace.py --trace-id <id>
```

The tree shows where time is spent and where the error originated. If the failing span is in a downstream service, repeat steps 1-4 for that service.

## Step 5 — Summarize

Produce a triage summary in this shape:

```
Incident: <one-line symptom>
Service:  <name>
Window:   <start> -> <end>
Firing monitors:
  - <id> <name> (since <ts>)
  - ...
Symptoms:
  - <golden signal observation, e.g. "p95 latency 4x baseline">
  - <log finding, e.g. "200 errors/min on POST /v1/field, all from host web-prod-3">
  - <trace finding, e.g. "75% of latency is in SQL span on customer DB">
Likely cause: <hypothesis with confidence>
Suggested next action:
  - <e.g. "log defect via log-defect skill", "check recent deploys", "page DB on-call">
```

If the cause is clear and a defect should be filed, hand off to the `log-defect` skill with the summary as context.

## Conventions

- **Always run step 1 first.** Even if the user says "the logs are spammy", the monitors tell you what *Datadog* thinks is broken — a useful prior.
- **Compare to baseline.** A single number is meaningless. Either re-run the metric query for `now-25h to now-24h` or eyeball whether the timeseries shape is normal.
- **Preserve trace IDs** in your summary — they're the cheapest way for a future investigator to reconstruct what you saw.
- **Don't pivot blindly.** If aggregation shows errors are uniform across hosts, don't waste time pulling a per-host log search.

## Gotchas

- **The `<svc>` placeholder** in this playbook needs to match the actual `service:` tag value. If the metrics show no data, the service might be tagged differently (e.g. `tables-fields-api` vs `tables_fields_api`). Run `list_services.py` to enumerate.
- **Monitor naming is inconsistent.** Don't trust monitor names to imply they cover what they sound like — read the `query` field.
- **Telemetry lag** — Datadog ingestion is usually <30s but can spike to minutes during incidents that affect their own infra. If `now-2m` shows nothing and `now-15m` does, that's a hint.
- **Background workers** don't show up in `trace.web.*` metrics. For RabbitMQ consumers, sidekick jobs, etc., use `trace.<integration>.*` metrics or query logs directly.

## What this skill does NOT do

- Does not file tickets or page anyone — that's `log-defect` and the on-call rotation.
- Does not mutate Datadog state (mute monitors, post events) — read-only family.
- Does not replace the Datadog UI for visual exploration. The skills hand back URLs (`web_url(...)`) for everything they fetch — share those with the user when prose isn't enough.
