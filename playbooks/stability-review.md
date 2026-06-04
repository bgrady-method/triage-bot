# Stability-review playbook

The methodology behind the monthly `stability-review` routine. Used by `stability-review-prompt.md`. Mirrors the structure of `playbooks/dd-investigate.md` and `playbooks/es-investigate.md` — Steps, Conventions, Gotchas, Out of scope.

## Mandatory framing (every report this playbook produces)

Every report this playbook produces — monthly stability-review, ad-hoc availability snapshot, post-incident retrospective, anything — **must include an "Industry comparison" / "Framing" section** with:

1. A **benchmark tier table** (99.99% hyper-scale, 99.95% well-run mid-market, 99.9% industry-standard SaaS SLA — Salesforce / HubSpot / QBO / Zoho, 99.5% below-industry). Annualized + monthly downtime per tier.
2. **Method against those tiers** — every availability metric in the report gets an industry-context comparison ("X notches below/at/above 99.9%"), not bare percentages.
3. An **annualization caveat** when the window contains an incident cluster — explicitly name the P0-count-per-window so readers don't naively annualize.
4. A **concentration-vs-distribution call** — is the shortfall dominated by a small set of named root causes (closable), or distributed across many unrelated incidents (systemic)?

Headline numbers in the Executive Summary always carry industry context inline. A raw "99.34%" without "≈ 1 notch below the 99.9% peer SLA standard, concentrated in 4 named incidents" is misleading.

## Mandatory input freshness (every report this playbook produces)

Two upstream sources must be current at the moment of writing the report. Stale inputs produce confident-but-wrong findings — a failure mode we've seen first-hand.

1. **PIRs are current.** Every stability-review run (and any ad-hoc report this playbook covers) MUST fetch the canonical PIR Confluence blog live via `mcp__claude_ai_Atlassian__getConfluencePage` and merge any new entries into `kb/known-issues.json` before starting analysis. The weekly `pir-ingest` snapshot is the floor, not the ceiling. New entries between Monday's pir-ingest and the report run must show up in the report. The Executive Summary always includes a `PIR sync: +N entries` line so the reader knows the analysis ran against a fresh snapshot. See `stability-review-prompt.md` Phase 0a.5 for the exact procedure.

2. **Service-repo code is current.** Any `git log` / `git grep` / `git show` against a cloned service repo MUST be preceded by `git fetch origin <default-branch> --quiet` for that repo, per `CLAUDE.md`'s "Hard rule." Read via `git show origin/<default-branch>:<path>` — never the local working tree. Stable repos are stale: assume that without a fresh fetch, the version you're reading is days or weeks behind production.

Failing either freshness gate fails the report's quality bar — same severity as missing a five-whys or undecidable substitution.

## When to use

- The `stability-review` routine fires on its monthly cron (`23 9 1-7 * 2` — first Tuesday of the month, 09:23 local).
- Manual trigger via the Anthropic routine UI for an ad-hoc review (e.g., post-incident retrospective).

This is a **synthesis** activity — applied to a 30-day window of triage-bot output. It is not for live incident response (use `playbooks/dd-investigate.md` or `playbooks/es-investigate.md` for that).

## Step 0 — Scope confirmation

Before any analysis:

1. **Window:** trailing 30 days, expressed as Unix epoch seconds. `WINDOW_END = $(date -u +%s)`, `WINDOW_START = WINDOW_END - 2592000`. Translate to ISO-8601 for human-readable copy in the report.
2. **Year-month for output path:** `YYYY-MM = date -u +%Y-%m`. Output file: `stability-reviews/<YYYY-MM>/report.md`.
3. **Data adequacy check.** Count lines in `kb/incident-log.jsonl` whose `ts` falls in the window:
   ```bash
   awk -v from="$WINDOW_START" -v to="$WINDOW_END" \
     '/"ts"/ { match($0, /"ts":[ ]?([0-9]+)/, a); if (a[1] >= from && a[1] <= to) c++ } END { print c+0 }' \
     kb/incident-log.jsonl
   ```
   - **< 10 lines:** the bot has not been running long enough or has been disabled. Post `🟡 stability-review: only N incident-log lines in window — skipping (need ≥10)` to `#triage-bot-health` and exit cleanly. Do not commit a report.
   - **10-49 lines:** proceed but include a "Limited data" disclaimer in the Executive Summary. The report exists; trend analysis is unreliable.
   - **≥ 50 lines:** full run.
4. **Idempotence:** if `stability-reviews/<YYYY-MM>/report.md` already exists, prepare to overwrite. The new report prepends `> _Updated <ISO-8601 ts> — superseding earlier run_` so the latest is canonical.

## Step 1 — Pattern discovery

A "pattern" is one of:

- **Recurring alert_hash:** the same `alert_hash` appears ≥2 times in the window (group by exact hash).
- **Recurring root cause:** distinct `alert_hash`es whose `Likely cause` (from `docs/investigations/<hash>.md`) match the same noun phrase (e.g., "RabbitMQ consumer lag", "SQL deadlock on accInvoice"). Cluster these into a single pattern.
- **High-impact singleton:** one alert classified `needs-human` with a `confidence < 0.7` score AND no matching KB entry, IF it touched a critical-path service from `references/architecture/platform-overview.md` (gateway, auth, runtime-core, SQL cluster, RabbitMQ, Redis).
- **Unaddressed prior recommendation:** a recommendation from a prior `stability-reviews/.../report.md` that is still firing alerts in the current window. These are surfaced under "Open Follow-ups", not as new findings.

Discard from clustering:
- One-off transient alerts (single occurrence in window, classification `false-alarm` or `new-with-clear-fix` with confidence ≥ 0.8). They are noise at month-scale.
- Alerts with `bot_id` set to a known noisy bot whose `kb/false-alarms.json` entry is still valid.

Cap: report no more than **10 findings**. If the window has more, take the top-10 by frequency × severity (severity = 1 for false-alarm, 2 for known-issue, 3 for needs-human/new-with-clear-fix). Drop the rest into a "Long tail" appendix line: `Additional <N> patterns below threshold; see kb/incident-log.jsonl for full data`.

## Step 2 — Five-whys protocol

For each pattern:

- Apply `references/methodology/five-whys-template.md`.
- Each "why" cites at least one piece of evidence:
  - Specific `kb/incident-log.jsonl` line numbers
  - Specific `docs/investigations/<hash>.md` files
  - DD log lines (preserve URLs)
  - DD monitor IDs
  - DD trace IDs
  - Jira ticket keys (read-only)
  - Deploy hashes from `git log` of the affected service repo
- The 5th why must be **structural** — a process gap, an architecture constraint, a missing instrumentation contract. Never "the engineer should have…".
- If you reach a structural cause at why 3 or 4, stop. Don't pad to 5.
- If you can't reach a structural cause by why 5 because the data isn't there, stop and mark `(structural cause unverified — needs investigation)` rather than fabricating.

## Step 3 — Course consultation (REQUIRED)

For each pattern's recommendation:

1. **CLASSIFY** against the Symptom Taxonomy in `references/system-design/INDEX.md`. Pick exactly one primary class.
2. **READ** the primary modules listed in the Symptom-to-Module Map. Use the Read tool on `references/system-design/level-N/<slug>.json` directly.
3. **APPLY** at least one principle per consulted module to the recommendation. Quote or paraphrase the principle in the recommendation text.
4. **CITE** the module path(s) in the report's "Course module references" field.

If a recommendation does not cite at least one course module path, the report fails the playbook's quality gate. Either tighten the symptom classification, expand to secondaries, or append the gap to `references/system-design/INDEX.md` § "Gaps".

## Step 4 — Calculations

Use `references/methodology/metrics-formulas.md`. For each pattern compute:

- **Frequency** (incidents per month).
- **MTTR** (mean recovery time across the window's incidents).
- **Availability impact** (% of window in unhealthy state, expressed in nines lost).
- **Error budget burn** vs the proposed SLO target in `references/architecture/known-failure-modes.md` (or in the matching CLAUDE.md if the pattern targets a service with a defined SLO).
- **Blast radius** (estimated affected users / tenants from log volumes).
- **ICE score** per `references/methodology/recommendation-rubric.md`.

Show the substitution in the report so the reader can verify. If a number cannot be computed because the data isn't there, mark `(undetermined — <reason>)` and proceed.

## Step 5 — Jira read-only cross-reference

For each pattern, search Jira for similar tickets to avoid recommending what's already being tracked.

JQL templates (use `mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql`):

```
# Recent open work in NCNG/PL matching service + signature
project in (NCNG, PL) AND
  (text ~ "<service-name>" OR text ~ "<exception-signature>") AND
  resolution = Unresolved AND
  updated >= -90d
ORDER BY updated DESC

# Recent closed work — to know what was fixed and verify it stayed fixed
project in (NCNG, PL) AND
  text ~ "<exception-signature>" AND
  resolution = Done AND
  resolved >= -90d
ORDER BY resolved DESC

# Tickets already linked to a kb/known-issues.json entry (which has fix_jira)
project in (NCNG, PL) AND
  key in (<comma-separated keys from known-issues.json>)
```

For each match found:
- Note the ticket key, summary, status, assignee.
- If the recommendation overlaps with an open ticket, note it in the recommendation text: "Tracked in <KEY-NNNN>; this report adds <new context>".
- If the recommendation overlaps with a closed ticket but the alert is still firing, note that the closed fix may not be effective: "<KEY-NNNN> closed YYYY-MM-DD but symptom recurring — verify fix landed and is sufficient".

**Never write to Jira.** No `createJiraIssue`, no `editJiraIssue`, no `transitionJiraIssue`, no `addCommentToJiraIssue`. The routine is read-only on Jira.

## Step 6 — Report assembly

Use `references/methodology/postmortem-template.md` as the structure. Required sections in order:

1. Executive Summary
2. Methodology (data sources used, course modules consulted)
3. Findings (one per pattern, ordered by ICE descending)
4. Trend Analysis (skip if no prior report)
5. Open Follow-ups
6. Appendix: raw queries

Quality gate before commit:
- [ ] Every recommendation cites at least one `level-N/<slug>.json` path.
- [ ] Every five-whys reaches a structural 5th why OR explicitly stops with `(unverified)` reason.
- [ ] Every calculation shows the substitution (e.g., `MTTR = 120/4 = 30 min`).
- [ ] Every Jira reference uses ticket keys, not free text.
- [ ] No PII in evidence quotes (sanitize account names/IDs to `account-<hash>` if needed).

## Conventions

- **Always read CLAUDE.md first** — same as `prompt.md`. Service catalog and critical-path facts are the prior for impact reasoning.
- **Always read `references/system-design/INDEX.md` second** — locks in the navigation protocol before any classification.
- **Compare to baseline** — every metric in the report compares to either the prior report's value or to a 30-day baseline pulled from DD. A bare number is never the right answer.
- **Preserve URLs verbatim** — DD permalinks, Kibana URLs, Jira keys. The reader can't re-derive these.
- **Blameless framing** — refer to gaps in instrumentation, process, or architecture. Never to specific people.
- **Conservative on novelty** — if a pattern is genuinely new (not previously seen), confidence should never exceed 0.7 in this report. Mark as "new — verify on next month's review".

## Gotchas

- **Time arithmetic on `kb/incident-log.jsonl`** — `ts` is Unix seconds in the existing schema. Convert to ISO-8601 only for display, never for computation.
- **`docs/investigations/<hash>.md` may be missing** for some incidents — the routine writes them but older runs may pre-date that schema. Use `kb/incident-log.jsonl` as the canonical ledger; investigation reports are bonus context.
- **`alert_hash` collisions across channels** — possible but rare. When grouping, also include `channel` to disambiguate.
- **Jira MCP rate limits** — limit JQL queries to 1 per pattern + 2-3 broad sweeps. If you need more, batch with `OR` clauses rather than running many small queries.
- **Course modules are JSON.** Read them as JSON (not markdown). The interesting content is in fields like `intro`, `sections[*].body`, `key_takeaways`. Don't quote the full module — quote the principle.
- **Don't recommend for the sake of recommending.** If a window genuinely has no patterns worth surfacing (rare, but possible after the team has fixed everything), say so:
  ```
  ## Findings
  No patterns met the threshold this window. Continue monitoring; baseline 30d availability across listed services is N.NN%.
  ```
  And produce a 1-page report rather than padding.

## Out of scope

- This playbook does not file Jira tickets.
- It does not page anyone.
- It does not change KB entries (the triage routine writes those directly during normal cycles).
- It does not silence monitors.
- It does not deploy or roll back.
