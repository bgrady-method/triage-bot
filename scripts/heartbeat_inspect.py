"""Quick inspection of incident-log.jsonl: classifications + recent rows."""
import json, time
from collections import Counter

cls_counts = Counter()
recent = []
with open('kb/incident-log.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        cls_counts[r.get('classification', '<missing>')] += 1
        ts = r.get('ts', 0)
        try:
            ts_f = float(ts)
        except Exception:
            ts_f = 0.0
        recent.append((ts_f, r.get('classification', '<missing>'), r.get('runtime_cost_usd', 0)))

recent.sort(key=lambda x: x[0])
last_5 = recent[-5:]
now = time.time()
print('classifications:', dict(cls_counts))
print('total rows:', sum(cls_counts.values()))
print('last 5 rows (ts | classification | cost | hours_ago):')
for ts, cls, cost in last_5:
    try: ts_f = float(ts)
    except: ts_f = 0
    ago = (now - ts_f) / 3600 if ts_f else None
    print(f'  {ts} | {cls} | {cost} | {ago:.2f}h ago' if ago is not None else f'  {ts} | {cls} | {cost} | ?')
