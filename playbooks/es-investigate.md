# Elasticsearch / Logstash investigation playbook

Ported from `~/.claude/skills/es-investigate/SKILL.md`. Local Python helper calls replaced with `scripts/es_search.py` (REST under the hood).

## When to use

When the alert is about a logged exception, a vague pattern ("requests failing intermittently"), or a post-deploy anomaly. If you already have a known field/value (trace id, exact exception type), skip to Step 4.

## Step 0 — Confirm scope

1. **Symptom** — error / slow response / no data / customer complaint / alert fired / post-deploy anomaly.
2. **Time window** — when did it start? Default `now-30m`. Use ES date math (`now-30m`, `now/d`, etc).
3. **Service / endpoint / user hint** — anything that narrows.

## Step 1 — Confirm logs are flowing

```bash
python scripts/es_search.py search --query "*" --from now-5m --limit 3
```

If 0 docs returned and the user is sure logs should exist, the log pipeline is broken — stop investigating, escalate. Or check that the index glob matches:

```bash
python scripts/es_search.py mapping --filter "<a-field-you-know-exists>"
```

## Step 2 — Aggregate to find concentration

You want to know which dimension the signal lives in. Start broad:

```bash
python scripts/es_search.py aggregate \
  --query "level:(ERROR OR FATAL)" --from now-30m \
  --field fields.ServiceName --top 10
```

If no obvious service stands out, try a different dimension:

```bash
# By host
--field host.name

# By exception type
--field fields.Exception
```

For a time shape (spike vs steady creep), there's no equivalent flag in `es_search.py` — fall back to running aggregations over multiple narrower windows or open Kibana for the visual.

## Step 3 — Drill into one bucket

Pick the noisiest bucket from Step 2 and pull individual hits:

```bash
python scripts/es_search.py search \
  --query 'level:ERROR AND fields.ServiceName:"<svc>" AND fields.Exception:"<type>"' \
  --from now-30m --limit 10
```

Each hit's `_source.fields.RequestId` (or `_source.trace`) is the correlation id. Grab one.

## Step 4 — Expand to the full request

```bash
python scripts/es_search.py search \
  --query 'fields.RequestId:"<id>"' --from now-1h \
  --limit 200 --sort asc
```

`--sort asc` walks the request chronologically: INFO context → the ERROR that ended it. If the request spans services, you'll see each service's contribution interleaved.

## Step 5 — Validate field names if zero results

If a step returned zero unexpectedly, the field names are wrong. Check the mapping:

```bash
python scripts/es_search.py mapping --filter <partial-field-name>
```

The actual dotted paths in the mapping override any guess.

## Step 6 — Summarize (output for the routine prompt)

```
Symptom:   <one-line description>
Service:   <name>
Window:    <start> -> <end>
Pattern:   <e.g. "NullReferenceException in POST /v1/field from customer 12345, 80 occurrences">
Top bucket: <service>:<exception> — N docs
Representative request: <trace/request id>
Kibana link: <if known>
Likely cause: <hypothesis>
Suggested next action:
  - <e.g. "file defect via log-defect" / "cross-reference Datadog metrics" / "no action — known recurrence">
```

## Cross-pivots

- **Infra signals correlate with errors** → switch to `dd-investigate` (latency, capacity, dependency health).
- **Exception points at SQL or Mongo** → run a vetted SQL template via `scripts/sql_query.py` for parallel data-state check.
- **Bug looks reproducible** → routine's classification path may produce a "new-with-clear-fix" — but only with confidence ≥ 0.85 in v1.

## Gotchas

- **Unknown field names** are the #1 reason for empty results. Don't assume `service.name` or `app.name`. Check mapping.
- **Analyzed text fields don't aggregate.** If `aggregate` returns no buckets, append `.keyword` to the field. (`scripts/es_search.py aggregate` does this automatically when there's no `.` in the field name.)
- **Time windows >1h on verbose queries** can time out. Narrow before widening.
- **Noisy signals** — if `level:ERROR` catches 10k+ hits in 5 min, filter the noisiest service first with `NOT fields.ServiceName:"<offender>"` to see what's underneath.

## Out of scope

- Read-only — never PUTs, POSTs that mutate state.
- Does not file tickets or page anyone.
