"""One-off builder: produce investigation reports + log lines + DM bodies for the
2026-05-17T12:08Z poll cycle. All 5 groups share the same blocked-tooling outcome.

Run from repo root. Writes to docs/investigations/, appends to kb/incident-log.jsonl.
Does NOT send DMs (caller does that with Slack MCP).
"""
import json, os
from datetime import datetime, timezone

WS = "methodme"
CYCLE_TS = "2026-05-17T12:08:00Z"
POLL_WINDOW = "2026-05-17T06:07:42Z->2026-05-17T12:08:00Z (6h backlog scan)"
DATE = "2026-05-17"


def plink(ch_id, ts):
    return f"https://{WS}.slack.com/archives/{ch_id}/p{ts.replace('.', '')}"


# (gid, channel_name, channel_id, (primary_ts, primary_hash, hhmm),
#                                  [(sat_ts, sat_hash, hhmm), ...])
GROUPS = [
    ("sys-B", "alert-system", "CPHHABKAA",
     ("1779003447.193349", "936a5769833e9a08", "07:37:27"),
     [("1779003508.485639", "9247f33df08acfc3", "07:38:28"),
      ("1779003748.818459", "3ed82e505d638c8d", "07:42:28"),
      ("1779003871.632739", "d636229f8f94900a", "07:44:31"),
      ("1779003995.294529", "cd0108b9923ec8a7", "07:46:35"),
      ("1779005127.789249", "c138bbb4b4e8c3df", "08:05:27"),
      ("1779005367.822179", "110f47a78be9a9cc", "08:09:27"),
      ("1779005609.109019", "aa3bb4b3f92a0cc3", "08:13:29"),
      ("1779006753.039219", "ed681032c2b5205a", "08:32:33"),
      ("1779006807.730819", "a42630bdae7edd48", "08:33:27"),
      ("1779007108.354869", "39e633a6ff94b21e", "08:38:28"),
      ("1779007347.149059", "8aca861e528f420b", "08:42:27"),
      ("1779007473.001859", "5313ddd3bf41249a", "08:44:33"),
      ("1779007528.050199", "d73161fadc7fdbc8", "08:45:28"),
      ("1779007894.634459", "345ffbe8b9fd6bce", "08:51:34"),
      ("1779008246.105359", "494081eb62ee983c", "08:57:26"),
      ("1779008307.757369", "7218dcf64af470c7", "08:58:27"),
      ("1779008366.095789", "5b04af4ae38f5243", "08:59:26"),
      ("1779008544.585059", "c1645c7300d06d5a", "09:02:24"),
      ("1779008786.682799", "8c029fb6d9f48b47", "09:06:26"),
      ("1779008846.332899", "4656ee0e75f2af24", "09:07:26"),
      ("1779009152.602869", "780736ce70e5822f", "09:12:32"),
      ("1779009687.836029", "105af6a00dd69fe8", "09:21:27"),
      ("1779009928.111419", "90ed77fdea7cd39f", "09:25:28")]),
    ("sys-A", "alert-system", "CPHHABKAA",
     ("1778999008.744809", "896dd9ae0ca7bfc9", "06:23:28"),
     [("1778999248.039589", "ef11dae8c67557b0", "06:27:28"),
      ("1779000514.588009", "552f3718f1e6c6c4", "06:48:34")]),
    ("sys-C", "alert-system", "CPHHABKAA",
     ("1779018511.384759", "8a76caa17121a107", "11:48:31"),
     [("1779018752.104219", "42bd91c53d7c0bf0", "11:52:32")]),
    ("fe-A", "alert-frontend-errors", "C03TYHGRS23",
     ("1779006013.178769", "347782a1ce862328", "08:20:13"),
     [("1779006073.233159", "ac4b8e74dc00f35d", "08:21:13"),
      ("1779006252.657219", "a4a13a250843ce4c", "08:24:12"),
      ("1779006312.244179", "b3ddf19484601284", "08:25:12")]),
    ("fe-B", "alert-frontend-errors", "C03TYHGRS23",
     ("1779016152.173759", "3cb73d675b1f46d5", "11:09:12"),
     []),
]

# Per-group confidence and bug-type guess (all needs-human; tooling blocked)
CONFIDENCE = {
    "sys-B": 0.55, "sys-A": 0.45, "sys-C": 0.40,
    "fe-A": 0.55, "fe-B": 0.40,
}

# Per-group narrative
NARRATIVE = {
  "sys-B": {
    "headline": "24-alert alert-system cascade over 108 minutes",
    "summary": [
      "Largest alert-system burst this routine has seen in its memory; bot B011R3D650X fired 24 times in a 108-minute window (07:37:27Z -> 09:25:28Z) with sustained density (mean inter-alert gap 4.7 min).",
      "Burst is bracketed by a 49-minute silence before (sys-A 06:48 -> sys-B 07:37) and a 2h23m silence after (09:25 -> sys-C 11:48).",
      "fe-A burst (4 alerts 08:20-08:25Z) lands INSIDE this window — strong cascading-failure signature (back-end-leads-front-end).",
    ],
    "cause": "Unknown without DD/ES. Density and 108-min duration are consistent with sustained backend incident (e.g. IIS pool flap, DB cluster contention, RabbitMQ queue backup). The fe-errors co-fire suggests user-facing impact.",
    "action": "page DB on-call / pull DD monitors manually",
    "bug_type": "unknown",
  },
  "sys-A": {
    "headline": "3-alert alert-system precursor 06:23-06:48Z",
    "summary": [
      "3 alerts in 25 min on alert-system, terminating 49 minutes before the sys-B cascade started (07:37:27Z).",
      "Likely precursor to sys-B — same channel, same bot, no other signal differentiator.",
    ],
    "cause": "Unknown without DD/ES. Bursts of 2-3 alerts have appeared in routine history (alert-system-variable-burst-mode candidate, currently unlocked). Possible same root cause as sys-B given proximity.",
    "action": "monitor (group with sys-B in human review)",
    "bug_type": "unknown",
  },
  "sys-C": {
    "headline": "2-alert alert-system trailing burst 11:48-11:52Z",
    "summary": [
      "2 alerts in 4 min on alert-system, 2h23m after the sys-B cascade ended.",
      "Lands 36 min after the fe-errors pair (11:04 + 11:09Z). May indicate the underlying incident is still flapping.",
    ],
    "cause": "Unknown without DD/ES. Pattern matches the alert-system-variable-burst-mode candidate (n=2 size bursts seen before). Could be sys-B remnant or fresh issue.",
    "action": "monitor; if next cycle has more alert-system fires, treat as ongoing incident",
    "bug_type": "unknown",
  },
  "fe-A": {
    "headline": "4-alert alert-frontend-errors micro-burst 08:20-08:25Z",
    "summary": [
      "4 alerts in 5 minutes on alert-frontend-errors (08:20:13Z -> 08:25:12Z); matches the (still-falsified) ki-fe-errors-2-alert-micro-burst-recurring candidate but with size 4 (not 2).",
      "Burst lands INSIDE sys-B's 108-min window (07:37 -> 09:25) — co-fire suggests cascading failure with the backend.",
      "Breaks 7h45m+ fe-errors silence (last fe-errors before this was 2026-05-16T12:17:12Z cluster-28).",
    ],
    "cause": "Strongly correlated with sys-B backend cascade. Without DD RUM / ES, can't pinpoint which frontend service or what error class. method-platform-ui last commit 2026-05-15 (>36h before alert, not a deploy correlation).",
    "action": "investigate jointly with sys-B; pull DD RUM manually",
    "bug_type": "code",
  },
  "fe-B": {
    "headline": "Singleton alert-frontend-errors 11:09:12Z (likely satellite of d205866aa861305f)",
    "summary": [
      "5 min after the prior cycle's primary 11:04:13Z (d205866aa861305f, logged at 11:11:06Z), bot B011R3D650X fired again at 11:09:12Z.",
      "Should likely have been grouped with d205866aa861305f, but that hash dedup'd out of this cycle's pending list before grouping (step 0c, age <24h).",
      "Stands alone in this cycle. Block-only body; no service tag without DD.",
    ],
    "cause": "Almost certainly the same root cause as d205866aa861305f (the prior-cycle primary 5 min earlier). Without DD, can't confirm. method-platform-ui clean.",
    "action": "treat as satellite of prior cycle's investigation; if pattern continues into next cycle, mark as recurring",
    "bug_type": "code",
  },
}


def write_report(gid, ch_name, ch_id, primary, sats):
    pri_ts, pri_hash, pri_hhmm = primary
    total = 1 + len(sats)
    sat_list = "  - (none — singleton)" if not sats else "\n".join(
        f"  - {h} ({hh}Z) — `{plink(ch_id, ts)}`" for ts, h, hh in sats
    )
    pri_link = plink(ch_id, pri_ts)
    span = f"{pri_hhmm}Z -> {sats[-1][2]}Z" if sats else f"{pri_hhmm}Z (singleton)"
    n = NARRATIVE[gid]
    md = f"""# Investigation: {pri_hash} — {DATE} {pri_hhmm} UTC  ({gid})

## Alert summary
- **Channel:** {ch_name}
- **Source bot / system:** Slack bot `B011R3D650X` (same bot fires on both alert-system and alert-frontend-errors)
- **Alert time:** {pri_hhmm} UTC (primary; group span {span})
- **Alert text:** (empty — content in Slack blocks only; bot does not expose readable text to MCP)
- **Alerts in group:** {total} ({len(sats)} satellite{'s' if len(sats)!=1 else ''})
- **Group label (cycle-local):** {gid}
- **Permalinks:**
  - {pri_hash} ({pri_hhmm}Z, **primary**) — `{pri_link}`
{sat_list}

## Classification
- **Result:** needs-human
- **Confidence:** {CONFIDENCE[gid]:.2f}
- **Action taken:** dm-self
- **Matched KB entry:** none (`kb/known-issues.json` and `kb/false-alarms.json` both still empty after 31+ cycles; no lock candidates have crossed the 0.95 conservative-mode threshold)

## Investigation

### Time window
{span} ({len(sats)} satellite{'s' if len(sats)!=1 else ''}; investigation window extended to {CYCLE_TS} cycle wall-clock for DD/ES/SQL queries — N/A this cycle, all blocked)

### Services identified
| Service | Source | Repo checked | Recent deploy? |
|---|---|---|---|
| (unknown) | bot body block-only; DD monitors blocked (no DD_API_KEY) | default-4 (runtime-core, method-platform-ui, ms-gateway-api, ms-tables-fields-api) | no — last commits 2026-05-13 / 14 / 15 (>2 days before alert) |

Without a `service:` tag from DD monitors or readable alert text, the routine cannot pinpoint a service. The bot `B011R3D650X` posts to both alert-system (backend) and alert-frontend-errors (frontend) channels with block-only payloads — historically these alerts have included service tags inside the Slack blocks that the MCP `conversations.history` payload omits.

### Tools run
| Tool | Query / args | Result summary |
|---|---|---|
| `slack_read_channel` | `oldest=1778998062 limit=100` ({ch_name}) | OK — pulled 6h window, found {total} message(s) for this group |
| `dd_search.py monitors` | (would be `--state Alert --state "No Data" --summary`) | **skipped** — DD_API_KEY not set (32nd consecutive cycle blocked) |
| `es_search.py` | (would query Logstash for window) | **skipped** — ELK_BASE_URL not set |
| `sql_query.py` | (would query AlocetSystem / prod1) | **skipped** — SQL_HOST_PROD1 not set |
| `mongo_query.py` | (would query per-account DB) | **skipped** — no MONGO_URI_* set |
| `gh api repos/methodcrm/<repo>/commits` | 2026-05-17T03:00Z -> 12:30Z, default-4 | 0 commits in 4h pre-alert window across all four repos |

### Key findings
{chr(10).join('- ' + s for s in n['summary'])}
- 32nd consecutive cycle with DD/ES/SQL/Mongo blocked (all routine secrets missing in this env). Root-cause work remains fully stalled at the tooling layer.
- Default-4 repos are quiet: runtime-core last commit `10208af` 2026-05-15T18:18Z (PL-62342, docs/tests for .NET upgrade); method-platform-ui last commit `46646d1` 2026-05-15T18:40Z (PL-62305 Method Pay UI fix); ms-gateway-api last commit `fd9ea65` 2026-05-14T18:49Z (PL-61884 v1 documents cleanup); ms-tables-fields-api last commit `2a89c92` 2026-05-13T19:35Z. No deploy correlation.

### Likely cause
{n['cause']}

### Evidence links
- DD monitors: https://app.datadoghq.com/monitors  (would filter to Alert+No Data; unavailable — DD_API_KEY not set)
- DD logs: https://app.datadoghq.com/logs  (unavailable — DD_API_KEY not set)
- Kibana: ${{ELK_BASE_URL}}/app/discover  (unavailable — ELK_BASE_URL not set)

## What we couldn't determine
- **Which service is firing.** Block-only body + DD blocked = no service tag.
- **Error class / top exception.** ES blocked.
- **24h baseline comparison.** ES + DD blocked.
- **Whether this is a known monitor or a new one.** DD monitors blocked.

## Suggested KB entry (if applicable)
None this cycle. Locking any candidate would require ≥0.95 confidence per conservative-mode rule (line count {{wc -l incident-log.jsonl}} < 50 still), and no candidate has crossed that bar with tools blocked. The `alert-system-variable-burst-mode` candidate has another data point this cycle (sys-A=3, sys-B=24, sys-C=2 — burst sizes still erratic) but still needs DD evidence to lock.

## Lessons / follow-up
- Suggested next action: **{n['action']}**
- **Resolve the cron-stuck issue** (silent ~14h since 2026-05-16T22:11Z) — without auto-fires every hour, large bursts like sys-B (24 alerts, 108 min span) accumulate as unprocessed backlog that manual local polls have to drain.
- **Provide DD/ES credentials in the routine env.** 32 consecutive cycles blocked means every needs-human investigation bottoms out at "service unknown, can't pinpoint."
- Cross-group: sys-A, sys-B, sys-C, fe-A all likely share a root cause (cascading backend incident with frontend impact). Human review should treat them as one event, not four.
"""
    path = f"docs/investigations/{DATE}-{pri_hash}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path


def build_log_lines(gid, ch_name, ch_id, primary, sats):
    pri_ts, pri_hash, pri_hhmm = primary
    grouped = [pri_hash] + [h for _, h, _ in sats]
    lines = []
    # Satellites first (per spec step 2, written before investigation but we batch here)
    for sat_ts, sat_hash, sat_hhmm in sats:
        sat_obj = {
            "ts": f"{DATE}T{sat_hhmm}Z",
            "alert_hash": sat_hash,
            "channel": ch_name,
            "classification": "grouped",
            "matched_kb": None,
            "confidence": None,
            "action": f"grouped-with:{pri_hash}",
            "grouped_with": pri_hash,
            "duration_s": 0,
            "runtime_cost_usd": 0,
        }
        lines.append(json.dumps(sat_obj))
    # Primary log entry
    pri_obj = {
        "ts": CYCLE_TS,
        "alert_hash": pri_hash,
        "channel": ch_name,
        "classification": "needs-human",
        "matched_kb": None,
        "confidence": CONFIDENCE[gid],
        "action": "dm-self",
        "grouped_alerts": grouped,
        "investigation_doc": f"docs/investigations/{DATE}-{pri_hash}.md",
        "duration_s": 0,
        "runtime_cost_usd": 0,
        "note": f"{gid}: {NARRATIVE[gid]['headline']}. 32nd consecutive DD/ES/SQL/Mongo-blocked cycle.",
    }
    lines.append(json.dumps(pri_obj))
    return lines


def build_dm(gid, ch_name, ch_id, primary, sats):
    pri_ts, pri_hash, pri_hhmm = primary
    total = 1 + len(sats)
    n = NARRATIVE[gid]
    sat_perm_lines = "\n".join(
        f"  • {plink(ch_id, ts)}  (#{ch_name}, {hh} UTC)"
        for ts, _, hh in sats
    )
    if sats:
        permalinks_block = f"  • {plink(ch_id, pri_ts)}  (#{ch_name}, {pri_hhmm} UTC, **primary**)\n{sat_perm_lines}"
    else:
        permalinks_block = f"  • {plink(ch_id, pri_ts)}  (#{ch_name}, {pri_hhmm} UTC)"

    body = f"""🚨 *new alert — needs human*  ({gid})
Channel: #{ch_name}  •  confidence: {CONFIDENCE[gid]:.2f}  •  bug-type guess: {n['bug_type']}  •  alerts in group: {total}

Symptoms:
""" + "\n".join("  - " + s for s in n['summary']) + f"""

Trace IDs: (unknown — block-only alert bodies + DD/ES blocked)
Likely cause: {n['cause']}
Suggested next action: {n['action']}

Source alerts ({total} total):
{permalinks_block}

Evidence:
  • DD monitors: unavailable — DD_API_KEY not set (32nd consecutive cycle blocked)
  • DD logs: unavailable — DD_API_KEY not set
  • Kibana: unavailable — ELK_BASE_URL not set
  • gh: default-4 repos clean — last commits 2026-05-13 / 14 / 15 (>2 days before alert window)
  • Investigation report: `docs/investigations/{DATE}-{pri_hash}.md`

Cross-group context this cycle:
  • sys-A (3 alerts 06:23-06:48Z) + sys-B (24 alerts 07:37-09:25Z) + sys-C (2 alerts 11:48-11:52Z) + fe-A (4 alerts 08:20-08:25Z, INSIDE sys-B window) + fe-B (singleton 11:09Z) — likely one cascading backend incident with frontend impact, not 5 independent issues."""
    return body


# Make output directories
os.makedirs("docs/investigations", exist_ok=True)
os.makedirs(f"docs/messages/{DATE}", exist_ok=True)

results = []
for gid, ch_name, ch_id, primary, sats in GROUPS:
    path = write_report(gid, ch_name, ch_id, primary, sats)
    log_lines = build_log_lines(gid, ch_name, ch_id, primary, sats)
    dm_body = build_dm(gid, ch_name, ch_id, primary, sats)
    results.append((gid, path, log_lines, dm_body, primary[1]))
    print(f"BUILT {gid} -> {path}  ({len(log_lines)} log lines, {len(dm_body)} char DM)")

# Append log lines to incident-log.jsonl (satellites + primary in chronological order)
with open("kb/incident-log.jsonl", "a", encoding="utf-8") as f:
    for gid, path, log_lines, dm_body, pri_hash in results:
        for line in log_lines:
            f.write(line + "\n")

# Write DM bodies to a temp file so the calling shell can pull them
with open(".claude/dm_bodies.json", "w", encoding="utf-8") as f:
    json.dump([{"gid": gid, "primary_hash": pri_hash, "body": body}
               for gid, _, _, body, pri_hash in results], f, indent=2)

print(f"\nWROTE {len(results)} investigation reports + {sum(len(l) for _,_,l,_,_ in results)} log lines.")
