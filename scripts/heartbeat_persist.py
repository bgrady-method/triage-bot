"""Write the heartbeat outbound message to docs/messages/<date>/triage-bot-health.jsonl
and append the heartbeat row to kb/incident-log.jsonl.

Inputs are passed via argv as a single JSON blob to keep escaping sane:
  python heartbeat_persist.py '<json>'

Required keys in the JSON:
  send_ts_epoch   (number)  — epoch seconds returned by Slack chat.postMessage
  body            (string)  — full message text exactly as sent
  status          (string)  — "ok" | "degraded" | "disabled"
  fail_count      (int)
  runtime_cost_usd(number)
  tool_health     (object)  — { tool: status, ... }
  notes           (string, optional)
"""
import json, os, sys
from datetime import datetime, timezone

if len(sys.argv) != 2:
    print("usage: heartbeat_persist.py <json-blob>", file=sys.stderr)
    sys.exit(2)

payload = json.loads(sys.argv[1])
send_ts = float(payload['send_ts_epoch'])
iso = datetime.fromtimestamp(send_ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
date_dir = datetime.fromtimestamp(send_ts, tz=timezone.utc).strftime('%Y-%m-%d')

# 1) docs/messages/<date>/triage-bot-health.jsonl
out_dir = os.path.join('docs', 'messages', date_dir)
os.makedirs(out_dir, exist_ok=True)
msg_path = os.path.join(out_dir, 'triage-bot-health.jsonl')

msg_row = {
    "ts": iso,
    "channel_id": "C0B0Q3KHC07",
    "channel_name": "#triage-bot-health",
    "recipient": "#triage-bot-health",
    "message_type": "health-status",
    "alert_hash": None,
    "thread_ts": None,
    "body": payload['body'],
}
with open(msg_path, 'a', encoding='utf-8') as f:
    f.write(json.dumps(msg_row) + '\n')

# 2) kb/incident-log.jsonl
log_row = {
    "ts": iso,
    "classification": "heartbeat",
    "tool_health": payload['tool_health'],
    "fail_count": int(payload['fail_count']),
    "runtime_cost_usd": float(payload['runtime_cost_usd']),
    "status": payload['status'],
}
if payload.get('notes'):
    log_row['notes'] = payload['notes']
with open(os.path.join('kb', 'incident-log.jsonl'), 'a', encoding='utf-8') as f:
    f.write(json.dumps(log_row) + '\n')

print(json.dumps({"msg_path": msg_path, "iso": iso, "appended_log": True}))
