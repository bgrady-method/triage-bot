# Investigation: <group_hash> — <YYYY-MM-DD HH:MM UTC>

## Alert summary
- **Channel:** <channel_name>
- **Source bot / system:** <bot name and bot_id>
- **Alert time:** <HH:MM UTC> (<HH:MM local>)
- **Alert text:** <full text, or "(empty — content in Slack blocks only)">
- **Alerts in group:** <M> (<list satellite hashes if any>)
- **Permalinks:**
  - <permalink-1>
  - <permalink-2>

## Classification
- **Result:** <false-alarm | known-issue-recurrence | new-with-clear-fix | needs-human>
- **Confidence:** <0.NN>
- **Action taken:** <dm-self | thread-reply | deduplicated | ...>
- **Matched KB entry:** <id or none>

## Investigation

### Time window
<start> → <end> UTC (extended to now if < 15 min wide)

### Services identified
| Service | Source | Repo checked | Recent deploy? |
|---|---|---|---|
| <name> | alert text / DD monitor / ES result | <repo> | yes — `<hash> <message>` / no |

### Tools run
| Tool | Query / args | Result summary |
|---|---|---|
| DD monitors | `--state Alert --state "No Data"` | <N firing; list names> |
| DD logs | `<query> --from <window>` | <N results; top finding> |
| DD metrics | `<metric query>` | <value vs 24h baseline> |
| ES | `<query>` | <result, or "unavailable (403)"> |
| sql_query.py | `--template <name>` | <result> |

### Key findings
- <bullet — what the data showed>
- <bullet — 24h baseline comparison>
- <bullet — deploy correlation if any>

### Likely cause
<hypothesis, 1–3 sentences>

### Evidence links
- DD monitors: https://app.datadoghq.com/monitors/<id>
- DD logs: https://app.datadoghq.com/logs?query=<encoded>&from_ts=<ms>&to_ts=<ms>&live=false
- DD metrics: https://app.datadoghq.com/metric/explorer?live=false&exp_metric=<metric>&exp_scope=<scope>&start=<epoch_s>&end=<epoch_s>
- Kibana: <url, or "unavailable — 403">

## What we couldn't determine
<anything blocked by ES being down, missing data, empty alert text, etc.>

## Suggested KB entry (if applicable)
```json
{
  "target": "false-alarms | known-issues",
  "id": "fa-YYYY-MM-DD-<slug>",
  "channel": "<channel_name>",
  "match": { "text_contains": "<keyword>" },
  "reason": "<why this fires and why it's safe to silence>",
  "silence_for": "24h"
}
```
_or "none"_

## Lessons / follow-up
- <anything the team should do differently: mute a monitor, fix a Centreon threshold, add a KB entry, improve the bot's investigation logic for this signal type>
