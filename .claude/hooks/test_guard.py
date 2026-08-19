"""Regression tests for guard_slack_send.py (the PreToolUse Slack guard).

Feeds PreToolUse-shaped events to the hook as a subprocess and asserts the
permissionDecision. Kept payloads inside this file (not on a shell command line)
so the live Bash hook doesn't match the test runner itself.

Run:  python .claude/hooks/test_guard.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "guard_slack_send.py")
ROOT = os.path.dirname(os.path.dirname(HERE))

SWAT = "C01L5K42GQ6"
IR = "C0B6233UN4S"
RESULTS = "C0B0Q3KHC07"

CASES = [
    # (name, event, expected_decision)
    ("allow mcp -> triage-results", {
        "tool_name": "mcp__claude_ai_Slack__slack_send_message",
        "tool_input": {"channel": RESULTS, "text": "ki-28 recurrence, 213 hits"}}, "allow"),
    ("deny mcp -> swat by id", {
        "tool_name": "mcp__claude_ai_Slack__slack_send_message",
        "tool_input": {"channel": SWAT, "text": "investigating"}}, "deny"),
    ("deny mcp -> IR by name", {
        "tool_name": "mcp__claude_ai_Slack__slack_send_message",
        "tool_input": {"channel": "#team-incident-response", "text": "hi"}}, "deny"),
    ("deny mcp mention <@U>", {
        "tool_name": "mcp__claude_ai_Slack__slack_send_message",
        "tool_input": {"channel": RESULTS, "text": "paging <@U063EFBAY95> pls"}}, "deny"),
    ("deny mcp subteam mention", {
        "tool_name": "mcp__claude_ai_Slack__slack_send_message",
        "tool_input": {"channel": RESULTS, "text": "cc <!subteam^ABC123|team>"}}, "deny"),
    ("deny scheduleMessage -> swat", {
        "tool_name": "mcp__claude_ai_Slack__slack_schedule_message",
        "tool_input": {"channel": SWAT, "text": "later"}}, "deny"),
    ("deny bash curl -> IR", {
        "tool_name": "Bash",
        "tool_input": {"command": "curl -s https://slack.com/api/chat.postMessage "
                                  "-d channel=" + IR + " -d text=hi"}}, "deny"),
    ("deny bash send-script -> swat", {
        "tool_name": "Bash",
        "tool_input": {"command": "python scripts/slack_" + "send.py post "
                                  "--channel " + SWAT + " --text hi"}}, "deny"),
    ("allow bash send-script -> results", {
        "tool_name": "Bash",
        "tool_input": {"command": "python scripts/slack_" + "send.py post "
                                  "--channel " + RESULTS + " --text ok"}}, "allow"),
    ("allow unrelated bash", {
        "tool_name": "Bash",
        "tool_input": {"command": "git status; python scripts/dd_search.py monitors"}}, "allow"),
    ("allow raw @everyone non-slack bash", {
        "tool_name": "Bash",
        "tool_input": {"command": "echo hi @everyone in the standup notes"}}, "allow"),
    ("allow other tool", {
        "tool_name": "Read", "tool_input": {"file_path": "x"}}, "allow"),
]


def decision_for(event):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": ROOT}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                       capture_output=True, text=True, env=env)
    out = p.stdout.strip()
    if not out:
        return "allow"
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except Exception:  # noqa: BLE001
        return f"?({out[:60]})"


def main():
    failures = 0
    for name, event, expected in CASES:
        got = decision_for(event)
        ok = got == expected
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'} [{name}] expected={expected} got={got}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
