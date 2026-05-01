# KB curation guide

How the bot's knowledge base grows, and how Ben keeps it useful.

## How entries get into the KB

There are three paths:

### 1. Bot proposes, Ben approves (the common path)

After a `false-alarm` or `new-with-clear-fix` classification, the bot's DM contains a fenced JSON block tagged `proposed_kb_entry`:

````
🤖 proposed kb entry — react ✅ to add to kb/false-alarms.json:
```proposed_kb_entry
{
  "target": "false-alarms",
  "id": "fa-2026-04-30-tables-fields-1am-warmup",
  "title": "tables-fields p95 spike during 1am cache prewarm",
  "match": {
    "channels": ["alert-runtime-monitoring"],
    "any_of": [{ "regex": "tables-fields.*p95.*4[0-9][0-9]ms" }]
  },
  "reason": "Cron-driven cache prewarm always nudges p95 between 1:00-1:05 ET.",
  "silence_for": "24h"
}
```
````

Ben reacts ✅ on that DM. Within 30 minutes, the `kb-approver` cron routine picks it up and commits the entry to `kb/false-alarms.json` on `main`.

Ben reacts ❌ if the entry is wrong — nothing gets added.

No reaction = no action. Old un-reacted DMs are ignored after 24h.

### 2. Auto-promotion (false alarms only, low-stakes)

If two alerts within 24h are classified `false-alarm` with no matched KB entry, the `kb-approver` cron synthesizes a minimal entry from their shared signature and adds it without Ben's approval. Rationale: false-alarm misclassifications are cheap (worst case the bot stays silent on a real alert *that looked exactly like a false alarm twice in a row*, which is acceptable risk).

Auto-promotion **never** applies to `kb/known-issues.json` — those entries gate the bot's playbook output and need a human in the loop.

### 3. Hand-editing

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
