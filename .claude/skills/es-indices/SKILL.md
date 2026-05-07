---
name: es-indices
description: List Elasticsearch indices and inspect their field mappings. TRIGGER when a log search returns unexpectedly empty, when you don't know what fields are queryable, or when you need to know which daily logstash index is live.
user_invocable: true
---

# es-indices — inspect indices and field mappings

Supporting skill for the `es-*` family. Use it when `es-logs` returns weird results — usually because you're querying the wrong index or the wrong field name.

## When to use

- "Which `logstash-*` indices exist and which are fresh?"
- "What fields are on this index? Is `fields.ServiceName` really what I should filter on?"
- "Is `level` a keyword or text field? (Matters for aggregation.)"
- "What's the mapping of `fields.Exception` — is it a nested object or just text?"

Pre-req: `es-setup` complete.

## Tools

| Script | Purpose |
|---|---|
| `scripts/list_indices.py` | `GET /_cat/indices/{pattern}`. Lists matching indices with health, doc count, size, creation date. Sort by name (default), doc count, size, or creation date. |
| `scripts/describe_mapping.py` | `GET /{index}/_mapping`. Flattens the properties tree into a sorted field list with type, aggregatability, and sub-fields (`.keyword`, etc.). Supports `--filter` (path substring) and `--type` (keyword/text/date/long/...). |

## Standard flow

1. **Confirm the live index pattern.**
   ```bash
   python .claude/skills/es-indices/scripts/list_indices.py --sort index --top 10
   ```
   Shows the most recent matching indices. If the newest one has no docs, either the pipeline is broken upstream or the pattern is wrong.

2. **Inspect the field mapping of the newest index.**
   ```bash
   python .claude/skills/es-indices/scripts/describe_mapping.py \
     --index logstash-2026.04.15 --filter fields. --top 50
   ```
   Scan the output to see the actual dotted paths your log emitter is using. This is the source of truth for writing queries.

3. **Find aggregatable fields.**
   ```bash
   python .claude/skills/es-indices/scripts/describe_mapping.py \
     --index logstash-* --type keyword
   ```
   Keyword fields can be aggregated on directly. Text fields need a `.keyword` sub-field — the output flags which of those exist.

## Conventions

- **Patterns can match many indices.** `describe_mapping.py` merges mappings across matched indices. In practice they're consistent (because they're generated from a shared template), but if you hit weird results narrow to a single index.
- **Sort default is `index` descending** — newest-named first, which is what you want for logstash-YYYY.MM.DD indices.
- **`--filter` is a case-insensitive substring match** on the full dotted path, e.g. `--filter service` matches `fields.ServiceName`, `host.service.name`, etc.

## Gotchas

- **404 on `_mapping`** — the pattern didn't match any index. Run `list_indices.py` first to see what's there.
- **Empty `properties` on a new cluster** — if the template hasn't been applied yet (new index just rolled over, no docs yet), the mapping will be sparse. Wait a few minutes or inspect yesterday's index.
- **`text` fields don't show `aggregatable: true`** unless they have a `.keyword` sub-field. If you want to aggregate on a text field and it has no `.keyword`, you can't — either change the mapping (infra change, careful) or pick a different field.
- **Mapping conflicts across patterns.** If two daily indices disagree on a field's type (rare but happens after a log format change), merging them in `describe_mapping.py` will show the last-seen type. Kibana handles this with "conflict" warnings; we just quietly report one.

## What this skill does NOT do

- No mapping edits. Read-only.
- No template / ILM policy inspection — add a script if needed (`GET /_index_template`, `GET /_ilm/policy`).
- No alias management. If your team uses aliases (e.g. `logstash-write`), list_indices will show them with `index.hidden` status and `alias` won't be obvious — check `GET /_alias/*` manually via curl for now.
