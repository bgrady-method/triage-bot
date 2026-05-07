You are the triage-bot heartbeat. Run this exact procedure:

## Step 1 — Spend + activity stats

Read kb/incident-log.jsonl. Compute:
  - Per-message lines today (UTC midnight to now), excluding `classification=poll-cycle` summaries
  - Poll-cycle lines today (the cron heartbeat — should be ≥1 every 6h)
  - Lines this week
  - Sum of runtime_cost_usd today (across all line types)
  - Time since last poll-cycle line (this is the most direct "is the cron alive" signal)
  - Last KB update: `git log -1 --format=%ct -- kb/known-issues.json kb/false-alarms.json`

Read kb/config.json's max_spend_usd.

## Step 2 — Tool availability checks

Run the REST-reachable checks via the helper script:

```bash
python scripts/tool_health.py --pretty > /tmp/tool_health.json
cat /tmp/tool_health.json
```

Parse the resulting JSON. The script covers:
  - `gh`        — GitHub API auth (`gh api user`)
  - `dd`        — Datadog `/api/v1/validate`
  - `es`        — Elasticsearch `_cluster/health`
  - `vpn`       — TCP connect to `$SSH_HOST:$SSH_PORT` (proxy for VPN reachability)
  - `sql`       — reported `skipped` (script can't run a real SQL query without a driver; rely on `vpn`)
  - `mongo`     — reported `skipped` (same reason)

Then run the MCP-tool checks inline (Python can't make MCP calls):

  a. **Slack MCP** — call `mcp__slack__users.info` for `BEN_USER_ID` (resolve via `mcp__slack__auth.test` first if needed). If it returns the profile, slack=ok. If it errors, slack=fail with the error message.

  b. **Atlassian MCP** — call `mcp__claude_ai_Atlassian__atlassianUserInfo` (no args). If it returns a user object, jira=ok. If it errors with auth, jira=fail with the error message. If the connector isn't configured for this routine, jira=skipped with "Atlassian MCP not enabled for heartbeat".

  c. **GitHub MCP** — only checked indirectly through `gh` CLI above; the heartbeat doesn't use the GitHub MCP for anything else.

Build a combined results table:

| tool      | status |
|-----------|--------|
| gh        | ok / fail / skipped |
| dd        | ok / fail / skipped |
| es        | ok / fail / skipped |
| vpn       | ok / fail / skipped |
| sql       | (skipped — see vpn) |
| mongo     | (skipped — see vpn) |
| slack     | ok / fail |
| jira      | ok / fail / skipped |

## Step 3 — Decide the post emoji

Priority (top wins):

1. If `sum_cost_today > max_spend_usd`:
    - Edit kb/config.json: set "enabled": false
    - git commit kb/config.json with message "heartbeat: daily spend cap reached, disabling"
    - git push origin main
    - Post: `🔴 triage-bot DISABLED: today's spend $X.XX > cap $Y.YY`
    - (Do not run further checks; the bot is off until manually re-enabled.)

2. If any tool check returned `fail`:
    - Post: `🟡 triage-bot alive but tools degraded · today: N alerts ($X.XX) · last poll <ago>`
    - Add a second line: `tools: gh ✓ dd ✓ es ✗(timeout) vpn ✓ slack ✓ jira ✗(401)` (use ✓ for ok, ✗(reason) for fail, omit skipped tools or render as `~` if you want to call them out).
    - Mention the failing tools by name in line 2 so the reader can act without opening the script output.

3. If `time_since_last_poll_cycle > 90 minutes`:
    - Post: `🟡 triage-bot: no poll cycle in <Nm> — cron may be stuck · tools: <one-line>`

4. Else (all green):
    - Post: `🟢 triage-bot alive · today: N alerts processed ($X.XX) · last poll <ago> · last KB update <ago> · tools all ok`

Always keep the post under 4 lines.

## Step 3.5 — Log the outbound message to disk

Immediately after the `chat.postMessage` call returns success, append the
message to `docs/messages/<YYYY-MM-DD-of-send>/triage-bot-health.jsonl` so
the stability-review routine can synthesise across heartbeat output. Schema
(one line, mirrors the format used by triage and stability-review):

```json
{"ts": "<iso-8601-utc>", "channel_id": "C0B0Q3KHC07", "channel_name": "#triage-bot-health", "recipient": "#triage-bot-health", "message_type": "health-status", "alert_hash": null, "thread_ts": null, "body": "<full message text exactly as sent>"}
```

Pseudocode:

```bash
DATE_DIR="docs/messages/$(date -u +%Y-%m-%d)"
mkdir -p "$DATE_DIR"
echo "$LINE" >> "$DATE_DIR/triage-bot-health.jsonl"
```

If the send failed, do NOT log — only log on success. Commit picks this
up alongside the incident-log line in Step 5.

## Step 4 — Sanity-check recent alerts

Sanity-check that recent alerts have incident-log entries.
  - For each alert channel, slack conversations.history last 6h
  - For each non-bot, non-self message: compute alert_hash, grep kb/incident-log.jsonl
  - If any are missing, list them in the heartbeat post (max 3, "...and N more")

## Step 5 — Append to incident log

Append one line to kb/incident-log.jsonl summarising the heartbeat result so
later cost-tracking can see it:

```json
{"ts": <epoch>, "classification": "heartbeat", "tool_health": {"gh":"ok","dd":"ok",...}, "fail_count": <N>, "runtime_cost_usd": <est>, "status": "ok"|"degraded"|"disabled"}
```

Commit + push as a follow-up commit so the kb stays clean.

---

## Unattended-execution rules

This routine runs unattended on a disposable Windows VM via Windows Task Scheduler. There is no operator at the keyboard. Every uncertainty resolves to a deterministic action.

1. **No interactive prompts.** Never ask the operator a question mid-run. Tool checks classify into `ok | fail | skipped` deterministically; the post composition follows the Step-3 priority table without judgment.

2. **Per-tool timeout: 90 seconds.** Wrap every external call (the `tool_health.py` invocation, every MCP call) with `timeout 90 ...`. If the script itself doesn't return within 90s, treat it as `fail` with reason `script-timeout` and proceed to compose the post. The point of the heartbeat is to land *some* status post even if half the tools are wedged — never let a single hang suppress the canary.

3. **Per-fire deadline awareness.** The routine's overall deadline is 8 minutes (Task Scheduler `timeout_minutes`). At 7 minutes elapsed, stop starting new tool checks; compose the post with whatever results are in hand and mark missing tools `skipped (deadline)`. The post still goes out.

4. **Fail-soft.** If composing the post itself fails (Slack MCP wedged, network down), write the intended post body to `logs/heartbeat-failed-${YYYY_MM_DD-HH-mm}.txt` and exit non-zero. The kill-switch logic in Step 3 priority 1 still runs to completion before the post attempt — flipping `kb/config.json.enabled = false` is the most important side-effect this routine has and must not be blocked by Slack failures.

5. **No interactive auth.** All credentials come from environment variables. If `GH_TOKEN` or any tool credential is missing, the affected tool reports `fail` (not `skipped`) and the post line names it. Don't prompt to recover.

6. **Push retry is bounded.** Two pushes happen here (the kill-switch flip if triggered, and the incident-log append). On either: try once, on failure pull-rebase-retry once, on second failure write the intended commit to `logs/heartbeat-uncommitted-${YYYY_MM_DD-HH-mm}.diff` and post `🟡 heartbeat: git push failed — see logs` to `#triage-bot-health`. The next heartbeat fire will catch up.
