import json, time
from datetime import datetime, timezone


def parse_ts(ts):
    """Parse a heartbeat-log ts which may be epoch seconds or ISO-8601 string."""
    if ts is None:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    s = str(ts).strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        pass
    # Try ISO-8601 (handle trailing Z)
    try:
        if s.endswith('Z'):
            s2 = s[:-1] + '+00:00'
        else:
            s2 = s
        return datetime.fromisoformat(s2).timestamp()
    except Exception:
        return 0.0


now = time.time()
day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
week_start = now - 7*86400

per_msg_today = 0
poll_today = 0
all_today = 0
lines_week = 0
cost_today = 0.0
last_poll_ts = 0
last_any_ts = 0

with open('kb/incident-log.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        ts = parse_ts(r.get('ts', 0))
        if ts == 0.0:
            continue
        cls = r.get('classification', '')
        if ts >= day_start:
            all_today += 1
            cost_today += float(r.get('runtime_cost_usd', 0) or 0)
            if cls == 'poll-cycle':
                poll_today += 1
            elif cls != 'heartbeat':
                per_msg_today += 1
        if ts >= week_start:
            lines_week += 1
        if cls == 'poll-cycle' and ts > last_poll_ts:
            last_poll_ts = ts
        if ts > last_any_ts:
            last_any_ts = ts

print(json.dumps({
    'now': now,
    'day_start': day_start,
    'per_msg_today': per_msg_today,
    'poll_today': poll_today,
    'all_today': all_today,
    'lines_week': lines_week,
    'cost_today': round(cost_today, 4),
    'last_poll_ts': last_poll_ts,
    'sec_since_last_poll': round(now - last_poll_ts, 0) if last_poll_ts else None,
    'last_any_ts': last_any_ts,
}, indent=2))
