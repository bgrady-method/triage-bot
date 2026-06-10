# PIR placeholders

Files in this directory are **stub records for incidents that occurred in production but do not yet have a published Confluence PIR** at the time the triage bot last synced the PIR cache (`.claude/pir-parsed.json`).

## Why these exist

The stability-review process reads PIRs from Confluence (Phase 0a.5 of `stability-review-prompt.md`) to ground-truth its availability calculation. If an incident occurred but no Confluence PIR was ever published, the next stability-review will undercount downtime — silently. The honest availability number depends on the PIR set being complete.

Placeholders close that gap: each one is a self-contained Markdown record with `status: placeholder` in the frontmatter, so the next stability-review reads it alongside Confluence PIRs and counts it toward downtime.

## What to do when a real Confluence PIR is published

When an engineer publishes the real PIR in Confluence, replace the placeholder with a stub that just links to the Confluence page:

```markdown
---
status: superseded
superseded_by: https://method.atlassian.net/wiki/spaces/...
superseded_on: 2026-MM-DD
---

Real PIR published; see Confluence link above.
```

Or delete the file. The frontmatter `status: superseded` is preferred for audit trail.

## What NOT to put here

- Reports of incidents that have a Confluence PIR. Those are pulled live via Atlassian MCP.
- Reports of incidents that aren't platform downtime (third-party AV flagging, support cases on individual accounts, etc.). Those don't belong in availability calculations.
- Triage-bot investigation reports. Those live in `docs/investigations/`.

## Current placeholders

See sibling `.md` files dated `YYYY-MM-DD-<slug>.md`.
