# Runbook

What to do when the bot is misbehaving.

## Disable the bot in 30 seconds

Edit `kb/config.json` on `main`:

```json
{ "enabled": false }
```

Push. The next routine fire reads this at step 2 and exits silently. Existing in-flight runs may still finish, but new ones won't start.

To disable just PR creation but keep DM-only triage running, set `pr_mode: "off"` instead.

## Mute an alert storm

If a flapping monitor is firing dozens of times per minute, the Cloudflare Worker debounces by `alert_hash` for 60s — duplicate fires within that window are dropped. But a *new* hash every fire (e.g. timestamps in the alert text differing) defeats this.

To stop the flood:

1. **Hardest option:** disable the bot via `kb/config.json` as above.
2. **Targeted option:** add a `kb/false-alarms.json` entry that matches the storm (broad regex on the noisy keyword) with `silence_for: "1h"`. Push to `main`. The next runs will hit the entry immediately and thread-reply only — no DMs, no investigation.
3. **Source-of-truth option:** silence the upstream Datadog monitor in the Datadog UI. The bot will stop seeing alerts because Slack will stop posting them. This is correct when the monitor is genuinely misconfigured.

## "I never got a DM but I see alerts in the channel"

In order:

1. Check `#triage-bot-health` — the heartbeat (every 6h) flags Worker unreachability and daily-cap hits.
2. Check the Cloudflare Worker logs: `wrangler tail` from `slack-receiver/`. You'll see incoming requests + sig-verification results in real time.
3. Check the routine's run history at https://claude.ai/code/routines — look for failed runs.
4. Check `kb/incident-log.jsonl` last 50 lines on `main` — every run logs even if the DM failed.

Most common causes:
- `kb/config.json.enabled: false` (kill switch on)
- Daily run cap hit
- Routine secret expired (e.g. Slack token rotated)
- Worker URL changed but Slack app's Event Subscriptions URL still points at the old one

## "The bot DM'd me with garbage"

1. React ❌ on the DM — it's a record but no longer eligible for the 2-confirmation auto-promote.
2. If the bot is misclassifying an entire pattern of alerts, hand-edit `kb/known-issues.json` or `kb/false-alarms.json` with a corrective entry and push to `main`. Future alerts hit the new entry first.
3. If the bot is *systematically* wrong on a specific channel, edit `prompt.md` or `playbooks/channel-guidance.md`. Push. The next run uses the new prompt (the routine reads files from the cloned repo every fire).

## "The bot opened a PR I don't like"

(v2 only — should not happen in v1.)

1. Close the PR — the routine doesn't merge its own.
2. Delete the branch on the remote: `gh api -X DELETE repos/<org>/<repo>/git/refs/heads/claude/triage-<hash>-fix`.
3. Add the failing pattern to `kb/known-issues.json` with `fix_status: "manual-only"` so future matches don't auto-PR.

## Rotating credentials

| Credential | Where to update | Notes |
|---|---|---|
| `SLACK_BOT_TOKEN` | Routine secrets + `wrangler secret put` | Both must match |
| `SLACK_SIGNING_SECRET` | `wrangler secret put` only | Worker only |
| `DD_API_KEY` / `DD_APP_KEY` | Routine secrets | |
| `ELK_USER` / `ELK_PASS` | Routine secrets | |
| `SSH_PRIVATE_KEY` | Routine secrets | Authorize the new public key on the bastion's `~/.ssh/authorized_keys` first; keep the old key valid until the rotation completes |
| `SQL_PASS_RO` | Routine secrets | Coordinate with the platform team — rotate the DB role's password in the same maintenance window |
| `GH_TOKEN` | Routine secrets | Fine-grained PAT preferred; scope: `repo:write` on triage-bot, `repo:read` on Method services |

After any rotation, fire a manual test alert in `#triage-bot-debug` and confirm the next bot DM lands.

## Nuke and pave

If the bot is in an unrecoverable state:

```bash
# 1. Disable
echo '{"enabled":false,"max_runs_per_day":50,"max_spend_usd":20,"pr_mode":"off"}' > kb/config.json
git commit -am "emergency disable"
git push

# 2. Investigate via run history at https://claude.ai/code/routines
# 3. Fix root cause
# 4. Re-enable
echo '{"enabled":true,"max_runs_per_day":50,"max_spend_usd":20,"pr_mode":"off"}' > kb/config.json
git commit -am "re-enable after fix"
git push
```

## Pruning old branches

Routine pushes one `claude/triage-<hash>` branch per alert. Run monthly:

```bash
gh api "repos/<owner>/triage-bot/branches?per_page=100" --paginate \
  | jq -r '.[] | select(.name | startswith("claude/triage-")) | .name' \
  | while read branch; do
      # Get last commit date; delete if >30d
      last=$(gh api "repos/<owner>/triage-bot/branches/$branch" --jq '.commit.commit.committer.date')
      age_days=$(( ($(date +%s) - $(date -d "$last" +%s)) / 86400 ))
      if [ "$age_days" -gt 30 ]; then
        gh api -X DELETE "repos/<owner>/triage-bot/git/refs/heads/$branch"
      fi
    done
```

(Or schedule this as a fourth cron routine.)
