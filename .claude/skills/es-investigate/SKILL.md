---
name: es-investigate
description: Troubleshooting playbook for production issues using Method's Logstash/Elasticsearch — composes es-logs / es-indices to narrow from "something's wrong" to a specific request ID, exception, or pattern. TRIGGER when the user says "investigate this in logstash", "what's wrong in prod", "pattern in the logs", "why is this failing", or describes a symptom without knowing which service/host is the culprit.
user_invocable: true
---

# es-investigate — production log triage

This is a playbook, not a script. It walks through the order that narrows a vague symptom to a concrete artifact (request id, exception, log line) fastest using `es-logs` and `es-indices`. Use it when you can't jump straight to a specific query because you don't yet know what you're looking for.

## When to use

- "Customer reports that field edits are failing intermittently — find the pattern."
- "We just deployed `tables-fields`; is anything new in the logs?"
- "There's a spike of 5xx somewhere; find the source."
- "I know this exception is somewhere in the logs but I don't remember the right filter."

If the user already has a known field/value to query (trace id, exact exception type), skip this skill and go straight to `es-logs search_logs.py`.

Pre-req: `es-setup` complete. If anything below returns a cred error, run `es-setup/scripts/smoke_test.py` first.

## Step 0 — Confirm scope

Ask (or infer):

1. **Symptom** — error, slow response, no data, customer complaint, alert fired, post-deploy anomaly.
2. **Time window** — when did it start? Default to `now-30m` unless it's longer-running. Convert anything relative the user says into an ES date math expression.
3. **Service / endpoint / user hint** — anything that narrows. Often the user only has a vague "it's slow" — that's fine, we'll discover.

## Step 1 — Confirm logs are flowing

Cheap sanity check. If this returns 0 docs, stop investigating and go check the log pipeline.

```bash
python .claude/skills/es-logs/scripts/search_logs.py --query "*" --from now-5m --limit 3
```

If that's empty but the user is sure logs should exist, run:

```bash
python .claude/skills/es-indices/scripts/list_indices.py --sort index --top 5
```

and confirm the newest `logstash-*` index has a non-zero doc count.

## Step 2 — Aggregate to find concentration

You want to know which dimension the signal lives in (service? host? endpoint? exception type?). Start broad:

```bash
python .claude/skills/es-logs/scripts/aggregate_logs.py \
  --query "level:(ERROR OR FATAL)" --from <window> \
  --by fields.ServiceName --top 10
```

If no obvious service stands out, try breaking down by a different dimension:

```bash
# By host
--by host.name

# By exception type
--by fields.Exception

# Two dimensions at once (heatmap style)
--by fields.ServiceName --by fields.Exception --top 5
```

For a time shape (is this a spike, a steady baseline, a slow creep?):

```bash
python .claude/skills/es-logs/scripts/aggregate_logs.py \
  --query "level:ERROR AND fields.ServiceName:<svc>" \
  --from now-6h --histogram --interval 10m
```

## Step 3 — Measure the field you just picked

Once you have a candidate field, `field_stats.py` tells you cardinality + top values in one shot. Useful before writing a precise filter:

```bash
python .claude/skills/es-logs/scripts/field_stats.py \
  --query "level:ERROR AND fields.ServiceName:<svc>" \
  --from <window> --field fields.Exception --top 20
```

If the top exception type covers most of the volume, drill into it. If it's a long tail, you may be chasing a distributed problem — back out and check infrastructure signals (dd-* skills) instead.

## Step 4 — Drill into one representative event

Pick the noisiest bucket from step 2 (service+exception, say) and pull individual hits:

```bash
python .claude/skills/es-logs/scripts/search_logs.py \
  --query 'level:ERROR AND fields.ServiceName:"<svc>" AND fields.Exception:"<type>"' \
  --from <window> --limit 10
```

Each hit's `trace` field is the request/correlation id (if your logger populates it). Grab one.

## Step 5 — Expand to the full request

```bash
python .claude/skills/es-logs/scripts/search_logs.py \
  --query 'fields.RequestId:"<id>"' --from <wider window> \
  --limit 200 --sort asc
```

`--sort asc` gives chronological order so you can read the request as it happened — log levels will walk from INFO debug context to the ERROR that ended it. If the request spans services, you'll see each service's contribution interleaved.

## Step 6 — Validate you're querying the right fields

If any step above returned zero when you expected results, the field names are probably wrong. Run:

```bash
python .claude/skills/es-indices/scripts/describe_mapping.py \
  --index logstash-* --filter <partial-field-name>
```

The actual dotted paths in the mapping override any guess you made. Update `references/query-syntax.md` in the `es-logs` skill if you find a field naming convention worth preserving.

## Step 7 — Summarize

Produce a summary like:

```
Symptom:   <one-line description>
Service:   <name>
Window:    <start> -> <end>
Pattern:   <e.g. "NullReferenceException in POST /v1/field from customer 12345, 80 occurrences">
Top bucket: <service>:<exception> — N docs, first seen <ts>, last seen <ts>
Representative request: <trace/request id>
Kibana link: <url from search_logs.py stderr>
Likely cause: <hypothesis with confidence>
Suggested next action:
  - <file defect via log-defect>
  - <check recent deploy>
  - <cross-reference dd-* for infra signals>
```

Hand off to `log-defect` if a ticket is warranted, or to `dd-investigate` if the root cause looks infrastructural (latency, capacity, external dependency).

## Cross-skill pivots

- **Infra signals** — if errors correlate with a latency spike, switch to `dd-investigate` / `dd-metrics`. ES/Logstash tells you *what* logged the error; Datadog tells you *whether the system is healthy*.
- **Database angle** — if the exception points at SQL or MongoDB, hand the context to `db-query` / `method-mongo-query` for a parallel check on data state.
- **Filing a bug** — when you have a reproducible signature, `log-defect` creates a well-formed Jira ticket with the Kibana pivot link and top log line included.

## Gotchas

- **Unknown field names** are the #1 reason for empty results. Don't assume `service.name` or `app.name` — check the mapping.
- **Analyzed text fields don't aggregate.** If `aggregate_logs.py --by <field>` returns no buckets and you're sure events exist, the field needs `.keyword`. Pass `<field>.keyword` explicitly.
- **Time windows bigger than a few hours** on a verbose query will be slow and may time out. Narrow before you widen — aggregate first, drill second.
- **Noisy signals.** If `level:ERROR` catches 10,000+ hits in a 5-minute window, you're looking at a broken log pipeline or a pathological service — filter out the noisiest service first with `NOT fields.ServiceName:"<offender>"` to see what's underneath.

## What this skill does NOT do

- Does not write to ES. Read-only.
- Does not file tickets or page anyone (`log-defect` does that).
- Does not replace Kibana Discover for visual pattern spotting — the scripts output Kibana URLs; share them when prose isn't enough.
