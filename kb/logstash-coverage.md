# Logstash coverage — which services ship to ES

Not every Method service ships its application logs to the Method Logstash cluster. Searching ES for a service that doesn't ship there returns 0 hits and is indistinguishable from "the bug doesn't exist in logs," which is exactly the trap that cost the 2026-05-07 investigation 3+ wasted turns on `runtime-core-api`.

> **Use:** before any `es_search.py search --query 'fields.ServiceName:"<svc>"'` invocation, look up `<svc>` here. If `indexed: no`, route to the **fallback** column instead.

## Critical facts

- The canonical service-name facet is **`fields.ServiceName`** (NOT `service.name`, NOT `kubernetes.labels.app`).
- Index pattern: `logstash-*`. Current month's index: `logstash-<YYYY>.<MM>` (e.g. `logstash-2026.05`).
- For services with `indexed: no`, the application's local log files at `D:/logs/<service>/...` (per memory `reference_log_location.md`) are the source of truth. EC2/host access required.
- Datadog APM **always** sees span-level errors even when ILogger.LogError is never called. APM trace tree is the canonical source of an exception class for `indexed: no` services.

## Coverage table

| Service | Indexed in ES | Fallback if not indexed | Last verified |
|---|---|---|---|
| `runtime-core-api` | **no** | DD APM trace tree (open the slow request's trace in DD UI); on-host `D:/logs/runtime-core/*.log` | 2026-05-07 |
| `sync` | yes | — | 2026-05-07 |

(Initial seed — bot extends this as future investigations clarify other services.)

## Symptom: how you know a service isn't indexed

A service should show up in a sanity-check query during an incident's window. If you see this pattern:

```
es_search.py search --query 'fields.ServiceName:"<svc>"' --from "<window>" --to "<window>"
=> { "total": 0 }
es_search.py search --query '<svc>' --from "<window>" --to "<window>"
=> { "total": 6 }   # all hits are from a DIFFERENT service mentioning <svc> in a payload
```

…then `<svc>` is almost certainly not shipping to Logstash. Add a row above and route to the fallback.

## How to grow this file

When an investigation confirms a service's indexing state:
1. Add a row keyed by service name with `yes` / `no` / `unknown`.
2. If `no`, document the fallback (host log path, DD APM trace tree, or both).
3. The `kb-approver` routine reviews proposed rows before merging.

Cross-references:
- `kb/metric-baselines.md` — what to look at when log search fails
- `playbooks/es-investigate.md` — primary ES playbook (consult this catalog at step 1)
- `playbooks/dd-investigate.md` — DD APM is the fallback for non-indexed services
