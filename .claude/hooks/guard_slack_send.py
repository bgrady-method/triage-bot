#!/usr/bin/env python3
"""
guard_slack_send.py — PreToolUse guard that enforces the triage bot's two send-path
Hard rules at the harness layer, across EVERY send path (not just slack_send.py):

  * Hard rule (#swat/IR): NEVER post into #swat or #team-incident-response.
  * Hard rule #13 (@-mentions): NEVER emit <@U…>, <!subteam^…>, <!channel|here|everyone>,
    or raw @channel/@here/@everyone.

slack_send.py already refuses these for itself (exit 3 / exit 4). This hook extends the
SAME guards to the paths that bypass the script: the Slack MCP send tools and raw
`curl .../chat.postMessage`. Forbidden channel IDs are resolved from kb/config.json — the
one source slack_send.py also uses — so they never drift.

Contract: reads the PreToolUse event JSON on stdin. To block, prints a deny decision on
stdout and exits 0. Fails OPEN (allow) when it cannot positively identify a Slack send —
it must never block unrelated Bash commands.
"""
import json
import os
import re
import sys

# Same mention pattern slack_send.py uses (kept in sync deliberately).
MENTION_RE = re.compile(
    r"<@[UW][A-Z0-9]+>|<!subteam\^|<!channel>|<!here>|<!everyone>"
    r"|(?<![\w/])@(channel|here|everyone)\b", re.I)

SLACK_SEND_TOOLS = {
    "mcp__claude_ai_Slack__slack_send_message",
    "mcp__claude_ai_Slack__slack_send_message_draft",
    "mcp__claude_ai_Slack__slack_schedule_message",
}

# Bash is only inspected when the command clearly targets a Slack send.
BASH_SLACK_MARKERS = ("slack_send.py", "chat.postMessage", "chat.scheduleMessage",
                      "slack.com/api")

FORBIDDEN_NAMES = ("swat", "team-incident-response")


def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def forbidden_channels():
    """Return (set of forbidden channel IDs, id->name) from kb/config.json."""
    path = os.path.join(project_dir(), "kb", "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            chans = json.load(f).get("channels", {})
    except Exception:  # noqa: BLE001  — fall back to the hard-coded IDs below
        chans = {}
    ids = {chans[n] for n in FORBIDDEN_NAMES if n in chans}
    # Defense in depth: keep the known IDs even if config is unreadable.
    ids |= {"C01L5K42GQ6", "C0B6233UN4S"}
    id_to_name = {v: k for k, v in chans.items()}
    return ids, id_to_name


def deny(reason):
    """Emit a PreToolUse deny decision and exit (0 = decision delivered cleanly)."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.stderr.write(f"[guard_slack_send] BLOCKED: {reason}\n")
    sys.exit(0)


def allow():
    sys.exit(0)  # silent — implicit allow, does not short-circuit other hooks


def _first(d, *keys):
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return None


def check(channel, text, forbidden, id_to_name):
    """Deny if channel is forbidden or text carries a mention. Otherwise return."""
    if channel:
        chan = str(channel).lstrip("#").strip()
        if chan in forbidden or chan in FORBIDDEN_NAMES:
            name = id_to_name.get(chan, chan)
            deny(f"refusing to send into #{name} — incident-response channel is never "
                 f"written to (swat/team-incident-response). Route findings to "
                 f"#triage-results instead.")
    if text:
        m = MENTION_RE.search(str(text))
        if m:
            deny(f"refusing to send: @-mention not allowed (matched {m.group(0)!r}). "
                 f"Hard rule #13 — render handles as inert text.")


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:  # noqa: BLE001  — malformed event: fail open
        allow()

    tool = event.get("tool_name", "")
    ti = event.get("tool_input", {}) or {}
    forbidden, id_to_name = forbidden_channels()

    if tool in SLACK_SEND_TOOLS:
        channel = _first(ti, "channel", "channel_id", "channelId", "channelName", "conversation_id")
        text = _first(ti, "text", "message", "content", "markdown_text", "markdownText", "blocks")
        check(channel, text, forbidden, id_to_name)
        allow()

    if tool == "Bash":
        cmd = ti.get("command", "") or ""
        if not any(marker in cmd for marker in BASH_SLACK_MARKERS):
            allow()  # not a Slack send — never block unrelated commands
        # Best-effort channel extraction from --channel / JSON / -d payloads.
        chan = None
        m = re.search(r"--channel[= ]+['\"]?([#A-Za-z0-9_-]+)", cmd)
        if m:
            chan = m.group(1)
        if not chan:
            m = re.search(r"[\"']?channel[\"']?\s*[:=]\s*[\"']?([#A-Za-z0-9_-]+)", cmd)
            if m:
                chan = m.group(1)
        # Mention check runs against the whole slack-send command string.
        check(chan, cmd, forbidden, id_to_name)
        allow()

    allow()  # any other tool: not our concern


if __name__ == "__main__":
    main()
