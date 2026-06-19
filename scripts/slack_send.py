#!/usr/bin/env python3
"""
slack_send.py — the triage bot's SEND path, through the `triage-bot` Slack app.

Posts via the Slack Web API using the app's bot token (SLACK_BOT_TOKEN, xoxb-...),
so outbound messages come from the `triage-bot` bot — NOT from Ben. (Reading Slack
stays on the Slack MCP as Ben; only sending moves here.)

Subcommands:
  dm        --user <Uxxxx> --text <msg>            open an IM with a user and post (DM Ben: kb-update / health / operational)
  post      --channel <Cxxxx> --text <msg> [--thread-ts <ts>]   triage findings → #triage-results; false-alarm thread reply → source channel

Hard guards (defense in depth — these also live in prompt.md):
  * NEVER posts to #swat or #team-incident-response (resolved from kb/config.json). Refuses with exit 3.
  * NO @-mentions: rejects <@U…>, <!subteam^…>, <!channel>/<!here>, and raw @channel/@here/@everyone. Exit 4.
  * Appends the JSONL audit line the prompt requires: docs/messages/<YYYY-MM-DD>/<slug>.jsonl

Never prints the token. Use --dry-run to validate guards + payload without sending (no token needed).
"""
import argparse, datetime, json, os, re, sys, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "kb", "config.json")
SLACK_API = "https://slack.com/api"

# Slack-encoded mentions + common raw forms. Any match is refused.
MENTION_RE = re.compile(r"<@[UW][A-Z0-9]+>|<!subteam\^|<!channel>|<!here>|<!everyone>|(?<![\w/])@(channel|here|everyone)\b", re.I)


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def channel_maps(cfg):
    """Return (id->name, name->id) and the set of forbidden incident-response channel IDs."""
    chans = cfg.get("channels", {})
    name_to_id = dict(chans)
    id_to_name = {v: k for k, v in chans.items()}
    forbidden = {chans[n] for n in ("swat", "team-incident-response") if n in chans}
    return id_to_name, name_to_id, forbidden


def guard_text(text):
    m = MENTION_RE.search(text or "")
    if m:
        sys.stderr.write(f"refusing to send: @-mention not allowed (matched {m.group(0)!r}). "
                         f"Render handles as inert text.\n")
        sys.exit(4)


def guard_channel(channel_id, id_to_name, forbidden):
    if channel_id in forbidden:
        name = id_to_name.get(channel_id, channel_id)
        sys.stderr.write(f"refusing to post to #{name} ({channel_id}) — incident-response channel is "
                         f"never written to (gate_reason=swat-bypass). Output goes to Ben's DM.\n")
        sys.exit(3)


def api(method, payload, token):
    req = urllib.request.Request(f"{SLACK_API}/{method}",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json; charset=utf-8",
                                          "Authorization": f"Bearer {token}"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"{method} HTTP {e.code}: {e.read().decode()[:200]}\n"); sys.exit(5)
    if not data.get("ok"):
        sys.stderr.write(f"{method} error: {data.get('error')}\n"); sys.exit(5)
    return data


def log_jsonl(channel_id, channel_name, recipient, msg_type, thread_ts, body):
    date_dir = os.path.join(ROOT, "docs", "messages", datetime.datetime.utcnow().strftime("%Y-%m-%d"))
    os.makedirs(date_dir, exist_ok=True)
    slug = {"self-dm": "self-dm"}.get(recipient, recipient.lstrip("#"))
    line = {"ts": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "channel_id": channel_id, "channel_name": channel_name, "recipient": recipient,
            "message_type": msg_type, "alert_hash": None, "thread_ts": thread_ts, "body": body}
    with open(os.path.join(date_dir, f"{slug}.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def token_or_die():
    t = os.environ.get("SLACK_BOT_TOKEN")
    if not t:
        sys.stderr.write("SLACK_BOT_TOKEN not set (xoxb-... from the triage-bot Slack app).\n"); sys.exit(2)
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pd = sub.add_parser("dm"); pd.add_argument("--user", required=True); pd.add_argument("--text", required=True)
    pp = sub.add_parser("post"); pp.add_argument("--channel", required=True); pp.add_argument("--text", required=True); pp.add_argument("--thread-ts", dest="thread_ts")
    for p in (pd, pp):
        p.add_argument("--type", default="other", help="message_type for the audit log")
        p.add_argument("--dry-run", action="store_true", help="validate guards + payload; do not send")
    a = ap.parse_args()

    cfg = load_config()
    id_to_name, name_to_id, forbidden = channel_maps(cfg)
    guard_text(a.text)  # @-mention guard runs for every path, before any network

    if a.cmd == "post":
        guard_channel(a.channel, id_to_name, forbidden)
        name = id_to_name.get(a.channel, a.channel)
        if a.dry_run:
            print(f"[dry-run] post -> #{name} ({a.channel}) thread={a.thread_ts}: {a.text!r}"); return
        payload = {"channel": a.channel, "text": a.text, "mrkdwn": True}
        if a.thread_ts:
            payload["thread_ts"] = a.thread_ts
        api("chat.postMessage", payload, token_or_die())
        log_jsonl(a.channel, f"#{name}", name, a.type or "thread-reply", a.thread_ts, a.text)
        print(f"sent: post -> #{name}")

    elif a.cmd == "dm":
        if a.dry_run:
            print(f"[dry-run] dm -> user {a.user}: {a.text!r}"); return
        tok = token_or_die()
        opened = api("conversations.open", {"users": a.user}, tok)
        dm_id = opened["channel"]["id"]
        api("chat.postMessage", {"channel": dm_id, "text": a.text, "mrkdwn": True}, tok)
        log_jsonl(dm_id, "self-dm", "self-dm", a.type or "needs-human", None, a.text)
        print(f"sent: dm -> {a.user}")


if __name__ == "__main__":
    main()
