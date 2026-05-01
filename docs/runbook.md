# Runbook

What to do when the bot is misbehaving.

## Disable the bot in 30 seconds

Edit `kb/config.json` on `main`:

```json
{ "enabled": false }
```

Push. The next routine fire reads this at step 0a and exits silently. Existing in-flight runs may still finish, but new ones won't start.

To disable just PR creation but keep DM-only triage running, set `pr_mode: "off"` instead.

## Mute an alert storm

If a single misconfigured monitor is firing dozens of times per hour, the routine will pull all of them in a single poll cycle and process each (subject to `max_runs_per_day`). To stop the flood:

1. **Hardest option:** disable the bot via `kb/config.json` as above.
2. **Targeted option:** add a `kb/false-alarms.json` entry that matches the storm (broad regex on the noisy keyword) with `silence_for: "1h"`. Push to `main`. The next poll cycle will hit the entry immediately and thread-reply only — no DMs, no investigation.
3. **Source-of-truth option:** silence the upstream Datadog monitor in the Datadog UI. The bot will stop seeing alerts because Slack will stop posting them. This is correct when the monitor is genuinely misconfigured.

## "I never got a DM but I see alerts in the channel"

In order:

1. Check `#triage-bot-health` — the heartbeat (every 6h) flags daily-cap hits and a missing-poll-cycle warning if no cron run has fired in 90 minutes.
2. Check the routine's run history at https://claude.ai/code/routines — look for failed runs.
3. Check `kb/incident-log.jsonl` last 50 lines on `main`. Every poll cycle appends one `classification: "poll-cycle"` summary line, even if zero new alerts. If the most recent line is more than ~70 minutes old, the cron isn't firing.
4. Check that the Slack MCP connection in the routine still has a valid OAuth — connectors sometimes need re-authorization after a long idle period.

Most common causes:
- `kb/config.json.enabled: false` (kill switch on)
- Daily run cap hit (`#triage-bot-health` will say so)
- Slack MCP OAuth expired
- Channel IDs in `kb/config.json` are wrong (the bot polls but can't find the channels)
- The alert author user matches `BEN_USER_ID` and is being filtered by step 0b's "skip self" rule (only happens if Ben hand-posted a test message)

## "The bot DM'd me with garbage"

1. React ❌ on the DM — it's a record but no longer eligible for the 2-confirmation auto-promote.
2. If the bot is misclassifying an entire pattern of alerts, hand-edit `kb/known-issues.json` or `kb/false-alarms.json` with a corrective entry and push to `main`. Future polls hit the new entry first.
3. If the bot is *systematically* wrong on a specific channel, edit `prompt.md` or `playbooks/channel-guidance.md`. Push. The next poll uses the new prompt (the routine reads files from the cloned repo every fire).

## "The bot opened a PR I don't like"

(v2 only — should not happen in v0.5/v1.)

1. Close the PR — the routine doesn't merge its own.
2. Delete the branch on the remote: `gh api -X DELETE repos/<org>/<repo>/git/refs/heads/claude/triage-<hash>-fix`.
3. Add the failing pattern to `kb/known-issues.json` with `fix_status: "manual-only"` so future matches don't auto-PR.

## Rotating credentials

| Credential | Where to update | Notes |
|---|---|---|
| Slack MCP OAuth | Re-authorize the connector in the routine UI | Identity (Ben) doesn't change |
| `DD_API_KEY` / `DD_APP_KEY` | Routine secrets | |
| `ELK_USER` / `ELK_PASS` | Routine secrets | |
| `SSH_PRIVATE_KEY` | Routine secrets | Authorize the new public key on the bastion's `~/.ssh/authorized_keys` first; keep the old key valid until the rotation completes |
| `SQL_PASS_RO` | Routine secrets | Coordinate with the platform team — rotate the DB role's password in the same maintenance window |
| `GH_TOKEN` | Routine secrets | Fine-grained PAT preferred; scope: `repo:write` on triage-bot, `repo:read` on Method services |

After any rotation, manually trigger the triage routine and watch `kb/incident-log.jsonl` for a successful poll-cycle line.

## Nuke and pave

```bash
# 1. Disable
echo '{"enabled":false,"max_runs_per_day":100,"max_spend_usd":20,"pr_mode":"off"}' > kb/config.json
git commit -am "emergency disable"
git push

# 2. Investigate via run history at https://claude.ai/code/routines
# 3. Fix root cause
# 4. Re-enable (restore the full config — see git log for last good version)
git checkout HEAD~1 -- kb/config.json
git commit -am "re-enable after fix"
git push
```

## Pruning old branches

Routine pushes one `claude/triage-<hash>` branch per alert. Run monthly:

```bash
gh api "repos/bgrady-method/triage-bot/branches?per_page=100" --paginate \
  | jq -r '.[] | select(.name | startswith("claude/triage-")) | .name' \
  | while read branch; do
      last=$(gh api "repos/bgrady-method/triage-bot/branches/$branch" --jq '.commit.commit.committer.date')
      age_days=$(( ($(date +%s) - $(date -d "$last" +%s)) / 86400 ))
      if [ "$age_days" -gt 30 ]; then
        gh api -X DELETE "repos/bgrady-method/triage-bot/git/refs/heads/$branch"
      fi
    done
```

(Or schedule this as a fourth cron routine.)

## When to revive `slack-receiver/`

`slack-receiver/` is parked. Revive it only if:

- `#swat` 60-min latency starts costing real time during P0s, OR
- Daily alert volume is high enough that hourly polling misses messages because of `max_runs_per_day` truncation.

To revive: deploy the Worker, set up the Slack app, change the triage routine's trigger from `cron` to `api`, and update `prompt.md` to consume a single payload instead of polling. The push and pull modes can coexist — push for `#swat`, pull for the rest.
