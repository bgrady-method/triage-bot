---
name: es-setup
description: One-time bootstrap for the es-* Elasticsearch/Logstash skill family — place credentials and verify the cluster responds. TRIGGER when any es-logs/es-indices/es-investigate script fails with a credential or connection error, or when wiring up production log access for the first time.
user_invocable: true
---

# es-setup — bootstrap the Elasticsearch skill family

Configures access to Method's Elastic Cloud cluster (the one that backs the Logstash Kibana at https://logstash.method.me). Read-only — no cluster mutations.

## Required state

1. **Python deps** (shared with dd-* family — likely already present):
   ```bash
   pip install requests python-dotenv
   ```

2. **`.env` file** at `~/.claude/skills/es-setup/.env` (gitignored). Copy `.env.example` and fill in:

   | Var | Meaning |
   |---|---|
   | `ES_SEARCH_ENDPOINT` | Cluster URL. Prod default: `https://ca8e80d7f930400fb386a29477353efa.us-west-1.aws.found.io:443`. (Legacy name `ES_URL` also accepted.) |
   | `ES_USERNAME` | Kibana / Elastic username. Service account preferred over personal login. (Legacy name `ES_USER` also accepted.) |
   | `ES_PASSWORD` | Password for that user. |
   | `ES_CLOUD_ID` | Optional. Elastic Cloud ID — only used by Elastic's official SDKs. The `es-*` scripts call the REST API directly via `ES_SEARCH_ENDPOINT`, so this is informational. Safe to leave set if another tool already populated it. |
   | `ES_DEFAULT_INDEX` | Default index pattern, e.g. `logstash-*`. Scripts fall back to this when `--index` isn't passed. |
   | `KIBANA_URL` | Web UI base for clickable pivot links. Default: `https://logstash.method.me` |

3. **Smoke test passes:**
   ```bash
   python ~/.claude/skills/es-setup/scripts/smoke_test.py
   ```
   Expected: cluster info, cluster health `green`/`yellow`, matching indices list, and a sample search showing docs in the last 15 minutes.

## How the other es-* skills find credentials

Every helper imports `es_client.py` (in `es-setup/scripts/`) which loads the shared `.env`. One credential file across the whole `es-*` family — never duplicate.

Bootstrapping a new es-* helper:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.home() / ".claude" / "skills" / "es-setup" / "scripts"))
from es_client import es_get, es_post, run_or_exit, resolve_index, print_json, kibana_discover_url
```

Exports:

| Symbol | Purpose |
|---|---|
| `es_get(path, params=None)` | `GET {ES_URL}{path}` with basic auth, returns parsed JSON. Raises `ElasticAPIError` on 4xx/5xx. |
| `es_post(path, body, params=None)` | `POST` with JSON body. Same error semantics. |
| `resolve_index(explicit)` | Returns the explicit arg or `ES_DEFAULT_INDEX`; errors out if neither is set. |
| `run_or_exit(fn)` | Calls `fn()`; on `ElasticAPIError` prints a remediation hint and `sys.exit(2)`. |
| `print_json(obj)` | Pretty JSON to stdout. |
| `kibana_discover_url(index, query, frm, to)` | Builds a best-effort clickable Kibana Discover URL. |
| `ES_URL`, `ES_USER`, `DEFAULT_INDEX`, `KIBANA_URL` | Resolved values. |

## Troubleshooting

**`ERROR: ~/.claude/skills/es-setup/.env does not exist`** — copy `.env.example` to `.env` and fill in the values.

**`401 Unauthorized`** — credentials wrong or account disabled. Try logging into https://logstash.method.me with the same user/pass.

**`403 Forbidden`** — account is valid but lacks read access on the target index. Ask infra to grant the `viewer` role on `logstash-*` (or whatever pattern you're using), or switch to a service account.

**`404` on a search** — the index pattern doesn't match anything. Run `es-indices list_indices.py` to see what exists.

**SSL / certificate errors** — Method's cluster terminates TLS at the Elastic Cloud edge with a valid cert; errors here usually mean a corporate proxy intercepting traffic. Check with infra before disabling cert verification.

**Smoke test connects but 0 docs in last 15m** — the default index pattern (`logstash-*`) may be stale or rolled over. Check in Kibana which index pattern is live, and update `ES_DEFAULT_INDEX`.

## What this skill does NOT do

- Does not write to the cluster. Read-only by design — don't grant this account write/admin scopes.
- Does not save stored searches, dashboards, or Kibana saved objects. Use the Kibana UI for those.
- Does not mirror data locally. Every query hits the live cluster.
