# KB curation guide

How the bot's knowledge base grows, and how Ben keeps it useful.

## How entries get into the KB

There are two paths:

### 1. The bot writes directly (the common path)

When the triage routine classifies an alert as `false-alarm` or `new-with-clear-fix` with confidence ≥ 0.85, it writes the entry directly to `kb/false-alarms.json` or `kb/known-issues.json` and commits in the same cycle. No proposal, no ✅ reaction, no approver routine — the agent owns the write.

Example commit message: `kb: add fa-2026-04-30-tables-fields-1am-warmup from triage cycle <hash>`.

The bot still DMs you a `kb-update` notification so the change shows up in your self-DM history alongside the alert it came from. The DM contains the full entry JSON for auditability.

**If you disagree with an entry** the bot wrote, edit (or remove) it directly on `main` — see path 2 below. The bot reads the latest version on the next fire.

**Guardrails the bot enforces before writing:**
- Confidence ≥ 0.85 (lower confidence → falls through to `needs-human` instead).
- For `kb/false-alarms.json`: ≥2 source alerts OR a clear-cut single-alert pattern documented in the investigation report.
- For `kb/known-issues.json`: investigation pinpoints a reproducible root cause with a fix sketch (diff or playbook).
- Idempotence: if an entry with the same `id` already exists, the bot increments `occurrences` and updates `last_seen` rather than duplicating.

### 2. Hand-editing

For one-off corrections, edit `kb/known-issues.json` or `kb/false-alarms.json` directly on `main` and push. The bot reads the latest version on every fire (it's a fresh clone each run).

Useful when:
- An entry's `match` regex is too greedy and capturing real alerts as false alarms.
- You want to add a `playbook` field to an existing entry after writing one.
- You're seeding the KB with patterns you already know about (recommended on day 1).

## Schema reference

### `kb/known-issues.json`

```json
[
  {
    "id": "ki-2026-04-12-tables-fields-deadlock",
    "title": "tables-fields SQL deadlock on bulk field add",
    "first_seen": "2026-04-12T14:22:00Z",
    "last_seen": "2026-04-28T09:11:00Z",
    "occurrences": 7,
    "match": {
      "channels": ["alert-runtime-monitoring"],
      "any_of": [
        { "contains": "Deadlock found when trying to get lock" },
        { "regex": "tables-fields.*Timeout expired" }
      ]
    },
    "diagnosis": "Concurrent BulkAddField calls on the same DB...",
    "playbook": "Restart tables-fields pool; if recurring within 1h, page DB on-call.",
    "fix_status": "in-progress",
    "fix_jira": "PL-12345",
    "fix_template": null,
    "confidence": 0.9
  }
]
```

| Field | Required | Purpose |
|---|---|---|
| `id` | yes | Unique. Convention: `ki-YYYY-MM-DD-<slug>` |
| `title` | yes | One-line human description |
| `first_seen` / `last_seen` | yes | ISO-8601 UTC, updated by the bot |
| `occurrences` | yes | Count, incremented on every match |
| `match.channels` | no | Channel allowlist. Omit to match any channel |
| `match.any_of` | yes | Array of `{contains: ...}` or `{regex: ...}` clauses; OR'd together |
| `diagnosis` | yes | What's actually broken |
| `playbook` | yes | What a human should do — the bot quotes this verbatim in the DM |
| `fix_status` | yes | `unknown` / `in-progress` / `fixed` / `manual-only` |
| `fix_jira` | no | Jira key, if a ticket exists |
| `fix_template` | no | (v2) If present, the bot can auto-apply this diff template — leave null in v1 |
| `confidence` | yes | 0..1; how sure we are this match is the right one |

### `kb/false-alarms.json`

Same shape minus `playbook` and `fix_*`. Adds:

| Field | Purpose |
|---|---|
| `reason` | Why this alert is noise (e.g. "cron-driven cache prewarm") |
| `silence_for` | Duration string (`"24h"`, `"7d"`); after this, the next match re-asks for confirmation. Set to `"forever"` for entries you're certain about. |

### `kb/incident-log.jsonl`

One line per run, never edited by hand. The bot appends; the heartbeat reads. Schema is in `prompt.md` § "Output contract".

## Curation rhythm

- **Daily (5 min):** triage your overnight DMs. ✅ obvious matches; hand-fix anything wrong.
- **Weekly (15 min):** review `kb/incident-log.jsonl` for the last 7 days. Look for hashes that recur >5 times without a matched KB entry — those are missing entries waiting to be written. `git log -- kb/known-issues.json` shows what's been added recently.
- **Monthly:** prune low-value entries (`occurrences < 3` and `last_seen` >30d ago). They're either misfires or transient issues.

## When to write a `playbook` vs a `reason`

- **`playbook` (known-issues):** "what should the on-call do." Imperative voice. Specific commands or links. Examples: "Restart the X pool", "Page the DB on-call via XMatters".
- **`reason` (false-alarms):** "why this is noise." Causal voice. Explain the upstream so future-you remembers why we silenced this. Example: "Datadog's `as_rate()` introduces ~30s lag; this monitor's threshold doesn't account for it".

## What NOT to put in the KB

- One-off incidents that aren't going to recur. Just let them age out.
- Vague matches like `{contains: "error"}` — the regex catalog should encode specific signatures.
- Jira ticket descriptions. The KB is for matching alerts → playbooks. Diagnosis prose belongs in Jira.
