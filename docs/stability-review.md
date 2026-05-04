# Stability-review runbook

Operational controls for the `stability-review` routine. Mirrors the structure of `docs/runbook.md` (which covers the `triage` routine).

## What it does

Runs monthly (first Tuesday at 09:23 local). Reads the trailing 30 days of triage-bot output, applies postmortem 5-whys analysis to recurring patterns, computes availability / MTTR / error-budget burn against proposed SLO targets, cross-references Jira read-only, and commits a markdown report to `stability-reviews/YYYY-MM/report.md`. Posts a one-liner to `#triage-bot-health` and DMs Ben the Executive Summary.

The routine is **read-only** on Jira, monitors, and KB (other than appending one cost-tracking line to `kb/incident-log.jsonl`).

## Disable in 30 seconds

Same as the other routines. Edit `kb/config.json` on `main`:

```json
{ "enabled": false }
```

Push. The next routine fire (any routine) reads this at Phase 0 and exits silently.

## Per-routine spend cap

`stability-review` honors a separate cap from the global daily cap:

```json
// kb/config.json
{
  "stability_review": { "max_spend_usd": 5 }
}
```

Default is $5 per run. The routine tracks spend through the run and stops early if exceeded, posting `🟡 stability-review: spend cap reached — partial report committed` to `#triage-bot-health`. Increase the cap if you find genuine value being cut off; lower it if the routine is over-spending without proportional value.

## Manual trigger

In the Anthropic routine UI at https://claude.ai/code/routines:

1. Find the `stability-review` routine.
2. Click "Trigger now".

Same prompt, same code path. Useful for:
- Post-incident retrospectives (run mid-month after a P0).
- Verifying a fix has resolved a pattern (re-run after the fix lands; confirm the pattern doesn't reappear).
- Testing changes to `playbooks/stability-review.md` or `references/`.

## Idempotence — re-running in the same month

If `stability-reviews/YYYY-MM/report.md` already exists, the routine **overwrites** it. The new report prepends a header:

```
> _Updated <ISO-8601 ts> — superseding earlier run_
```

The latest run is canonical. Earlier runs are preserved in git history (one commit per run).

If you want both runs to coexist without overwrite, edit the prompt to use `report-${run_count}.md`. Default is overwrite because the report is a synthesis — the freshest synthesis wins.

## Atlassian MCP setup (one-time)

The `stability-review` routine is the only routine that uses Atlassian MCP. First-time setup:

1. In the routine UI, edit `stability-review` and add the Atlassian MCP connector.
2. OAuth as Ben — same identity as the Slack MCP.
3. The routine will now have read-only Jira access.

Without Atlassian MCP, Phase 4 (Jira cross-reference) silently degrades to "no Jira data found" — the routine still produces a report, just without the cross-reference column.

To verify Atlassian access during a manual run, the report's Methodology section prints the JQL query count. If it's 0 with non-empty findings, Atlassian MCP is misconfigured.

## "I never got the monthly DM but I see the report on `main`"

In order:

1. Slack MCP OAuth may have expired between the post-to-channel step and the DM step. Re-authorize the connector.
2. The DM was posted but Slack collapsed it as a "self-DM with too many recent messages" (rare). Search Slack for `stability-review YYYY-MM`.
3. The routine posted to a different channel because `kb/config.json.channels."triage-bot-health"` is wrong. Verify the channel ID.

## "The report cited a course module path that doesn't exist"

The mirror is out of date. Refresh:

```bash
python scripts/sync_course_content.py
git add references/system-design
git diff --cached --stat        # confirm what changed
git commit -m "references: refresh system-design course mirror"
git push
```

Re-run the routine.

## "The report scored a recommendation with ICE = 100"

ICE max is 10×10/1 = 100, achieved only when Impact and Confidence are perfect (10) and Effort is 1 (single-line config change). If you see this, verify the Effort score — the rubric in `references/methodology/recommendation-rubric.md` is calibrated to make Effort < 3 unusual outside of pure config changes. If the routine is scoring Effort too low, edit the rubric file with a tighter Effort calibration.

## "The report says `(undetermined)` for MTTR on a finding that has obvious recovery times"

The routine couldn't recover the close timestamps from `kb/incident-log.jsonl`. Either:
- The investigation reports have the close ts in their body but the routine isn't extracting it. Adjust the prompt's Phase 7 extraction logic.
- The cluster's incidents are still open at window end. Mark explicit; consider extending the window for the next run.

## Course mirror — when to refresh

The mirror is committed to `references/system-design/`. Re-run `scripts/sync_course_content.py` whenever:
- The upstream course at https://github.com/benjgrad/learn updates (check the last-modified date of the most recent commit on that repo).
- A monthly report cites a `level-N/<slug>.json` path that doesn't exist on disk (the slug changed upstream).

Default: refresh quarterly, or when a finding requires a module the current mirror doesn't have.

## Adjusting the cron

The default cron `23 9 1-7 * 2` fires the first Tuesday of every month at 09:23 local. Change in `routines/stability-review.yaml`:

| Goal | Cron |
|------|------|
| First Monday at 09:00      | `0 9 1-7 * 1`     |
| Mid-month (15th, any day)  | `0 9 15 * *`      |
| Quarterly (Jan, Apr, Jul, Oct, 1st) | `0 9 1 1,4,7,10 *` |
| Weekly (every Tuesday)     | `23 9 * * 2`      |

Push the YAML change and re-save in the routine UI.

## Schema for `kb/incident-log.jsonl` line appended by this routine

```json
{
  "ts": <epoch>,
  "classification": "stability-review",
  "ym": "YYYY-MM",
  "patterns_found": <N>,
  "report_path": "stability-reviews/YYYY-MM/report.md",
  "runtime_cost_usd": <est>,
  "status": "ok" | "spend-capped" | "no-data" | "push-failed"
}
```

The `heartbeat` routine doesn't currently consume this line, but it could in future to enforce the per-routine cap globally.

## Nuke and pave

```bash
# 1. Disable the bot globally
echo '{"enabled":false,"max_runs_per_day":100,"max_spend_usd":20,"pr_mode":"off"}' > kb/config.json
git commit -am "emergency disable"
git push

# 2. Inspect the most recent report
cat stability-reviews/$(ls stability-reviews/ | tail -1)/report.md

# 3. Inspect the run log via the routine UI
# 4. Fix the underlying issue
# 5. Re-enable
git checkout HEAD~1 -- kb/config.json
git commit -am "re-enable"
git push
```

## Pruning old reports

Stability reports are append-only month-by-month. They are small markdown files; pruning is unnecessary at month-scale. If the directory grows beyond ~5 years' reports and becomes unwieldy, archive everything older than 24 months into `stability-reviews/archive/YYYY/` rather than deleting — the trend analysis benefits from long-window history.

## When to retire this routine

Retire when:
- Method has a dedicated SRE / observability function with its own postmortem cadence — at which point this routine duplicates that work.
- The triage routine's KB has matured to the point where the bot is auto-classifying ≥95% of alerts and no patterns are escaping into "needs-human" — at which point recurring pattern detection becomes uninteresting.

Until then, the routine is the only synthesis layer between hour-scale incidents and quarterly architecture reviews.
