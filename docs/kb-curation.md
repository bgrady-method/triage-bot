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

**Recurrence DM suppression (`last_notified_at` field, added 2026-05-21):**

Each KB entry tracks the last time the bot DM'd Ben about a recurrence. On subsequent matches, the recurrence DM is suppressed unless one of:
- The match is on `#swat` (always DM).
- More than `kb/config.json.suppression_window_hours` (default 24h) have passed since `last_notified_at`.
- `occurrences % 10 == 0` (every 10th hit re-surfaces so long-running issues don't go invisible).
- The entry's `fix_status` changed since the last DM.

Suppressed recurrences are appended to **`docs/actionable/<UTC-date>.md`** (a per-day markdown file committed to the repo — Ben reviews when convenient, no end-of-day Slack DM). The KB entry's `occurrences` and `last_seen` are always updated even when the DM is withheld.

## Scoring rubric for `needs-human` (Granularity v2)

When triage classifies an alert as `needs-human`, an impact-scored gate decides whether it earns a Slack DM, lands in `docs/actionable/<date>.md`, or just gets counted. Inputs are all observable from existing data (no model self-confidence). See `prompt.md` step 7 for the authoritative signal list and weights.

Key adjustable knobs in `kb/config.json`:
- `escalation_score_threshold` (default 4) — DM if score ≥ this
- `actionable_score_threshold` (default 2) — full `actionable.md` entry if score ≥ this; below = terse one-liner
- `daily_escalation_cap` (default 5) — hard ceiling on non-swat DMs per UTC day; excess go to `actionable.md`
- `critical_path_services` — service names that count as sign-in/core path (+3 to score)

Self-tuning signals (no manual upkeep): monitor history (a monitor's historical DM-rate adjusts its score by ±2), recency decay (same monitor firing repeatedly today loses score), metric-breach magnitude (parses observed-vs-threshold ratio from alert text).

## Ben-curated lookups

The bot reads but never writes:

- **`kb/account-tiers.json`** — map of `account_name` → tier (`enterprise` / `paid` / `free` / `unknown`). Only special-cased accounts go in this file; **everything else inherits the `_default.tier`** (currently `unknown`, contributing 0 to the escalation score). The bot's `score_breakdown` records `tier_source: "account-tiers.json"` vs `"default"` so you can audit which signal came from a real curated entry. Change `_default.tier` if you want a different fleet-wide default.

## Account-impact lookup (active users + multi-tenancy)

**`scripts/account_impact.py`** is the bot's reproducible "given a list of affected account names, count active users per account" tool. The triage routine runs it in step 4.3 of `prompt.md` after extracting `@account_name` values from Datadog logs. Output is JSONL — one line per input account.

Per-account result includes the per-`TenantId` breakdown from `spiderSecurity` (Method is multi-tenant *within* an account DB too — multiple `TenantId` values are common), totals across tenants, the account's `tier` (resolved through `account-tiers.json` with `_default` fallback), and a `status` field for edge cases:

| Status | Meaning |
|---|---|
| `ok` | Found and counted. |
| `not_found` | Not in any AlocetSystem cluster the bot tried. Bot retries with subdomain / friendly-name variant. |
| `ambiguous` | Multiple registry rows matched. Bot picks the most-active + highest-user-count candidate. |
| `inactive_account` | Registry shows `IsActive=0`; user count 0. |
| `tenant_unreachable` | Registry found the DB but connect failed (cluster down, name drift). |
| `schema_unknown` | Tenant DB reachable but `spiderSecurity` missing (old schema). |
| `error` | Uncategorised; includes `error_message`. |

The triage routine **always commits the raw JSONL** alongside the investigation report (`docs/investigations/<date>-<hash>.accounts.jsonl`), so a later stability-review can re-aggregate user-impact across the window without re-querying.

### Extrapolation

A single account mentioned in DD logs is rarely the *only* affected account. After running `account_impact.py`, step 4.4 in `prompt.md` asks the bot to decide whether the impact extends beyond the named set:

- **Infrastructure-shaped** (DNS, gateway, Redis, Mongo, SQL cluster keywords in the diagnosis) — the bot scopes the impact to *all accounts on the affected cluster*; the user-count signal is a lower bound.
- **Shared-endpoint generic error** (e.g., the well-known noisy monitor 77419271) — the bot broadens the DD log query to drop the `@account_name` filter and re-aggregate over the wider time window, then re-runs `account_impact.py` with the expanded set.
- **Account-specific bug** — the bot explicitly notes that extrapolation was considered and rejected.

The `score_breakdown` records `user_count_source`: `named_only` / `extrapolated_dd_broaden` / `cluster_lower_bound` / `fallback`, so the next stability-review can tell which alerts were under-estimated due to lack of extrapolation data.

## `docs/actionable/<YYYY-MM-DD>.md`

One file per UTC date, append-only during the day. Three categories inside:
- **high-borderline** — score between `actionable_score_threshold` and `escalation_score_threshold`. Full score_breakdown + suggested action.
- **known-issue-recurrence** — suppressed by the 24h window (Layer 1). One section per occurrence, grouped under the matched ki-id.
- **low-impact** — score below `actionable_score_threshold`. Terse one-line per entry.

Committed in the same commit as the triage cycle's other outputs. No standalone end-of-day routine.

### 2. PIR ingestion (weekly)

The `pir-ingest` routine (`routines/pir-ingest.yaml`) runs every Monday at 09:15 local. It fetches the canonical Post-Incident Report Confluence blog (`method.atlassian.net/wiki/spaces/SD/blog/.../Post-Incident+Report`, pageId `133496969`) via the Atlassian MCP, parses each engineer-authored incident block, dedupes against existing `kb/known-issues.json` entries, and writes any new ones with **confidence = 0.95** (PIRs are engineer-confirmed ground truth, not bot inference). It only writes known-issues, never false-alarms.

Today's KB was seeded by hand from this PIR (commit `3c779fb`); the routine keeps the KB current going forward with no manual effort.

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
