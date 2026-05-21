---
name: dd-setup
description: One-time bootstrap for the dd-* Datadog skill family — install Python deps, place credentials, and verify the four required app-key scopes. TRIGGER: when any dd-logs/dd-metrics/dd-monitors/dd-apm/dd-investigate script fails with a credential or import error, or when the user is wiring up Datadog access for the first time.
user_invocable: true
---

# dd-setup — bootstrap the Datadog skill family

This skill installs nothing on its own. It documents the one-time setup the `dd-*` scripts assume, and ships a smoke test that proves it worked.

## Required state

1. **Python deps** present on PATH:
   ```bash
   pip install requests python-dotenv
   ```
2. **`.env` file** at `~/.claude/skills/dd-setup/.env` (gitignored), containing:
   - `DD_API_KEY` — from Datadog UI -> *Organization Settings -> API Keys*. No scopes required on the API key itself.
   - `DD_APP_KEY` — from Datadog UI -> *Personal Settings -> Application Keys*. **Must have all four scopes:** `logs_read_data`, `metrics_read`, `monitors_read`, `apm_read`. If the key is missing scopes, edit the existing key (don't create a new one) so existing automations keep working.
   - `DD_SITE` — region host. Default `datadoghq.com` (US1). Other valid values: `datadoghq.eu`, `us3.datadoghq.com`, `us5.datadoghq.com`, `ap1.datadoghq.com`, `ddog-gov.com`. Look at the URL you log into Datadog with — that's your site.

   Use `.env.example` (in this directory) as a template.

3. **Smoke test passes:**
   ```bash
   python ~/.claude/skills/dd-setup/scripts/smoke_test.py
   ```

   Expected output (last line):
   ```
   All scopes valid. dd-* skills are ready to use.
   ```

## How the other dd-* skills find credentials

Every helper script imports `dd_client.py` (in `dd-setup/scripts/`) which reads the shared `.env`. There is **one** credential file across the whole `dd-*` family — never duplicate it into each skill.

If you need to bootstrap a new dd-* helper, start with:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.home() / ".claude" / "skills" / "dd-setup" / "scripts"))
from dd_client import dd_get, dd_post, parse_time_iso, parse_time_unix, run_or_exit, print_json
```

`dd_client` exports:

| Symbol | Purpose |
|---|---|
| `dd_get(path, params=None)` | `GET https://api.<site><path>`, returns parsed JSON. Raises `DatadogAPIError` on 4xx/5xx. |
| `dd_post(path, body)` | `POST` with JSON body, same error semantics. |
| `parse_time_unix(s)` | `'now'` / `'now-15m'` / ISO 8601 / unix epoch -> int seconds. Use for v1 query API. |
| `parse_time_iso(s)` | Same input, returns ISO 8601 with `Z`. Use for v2 logs/spans APIs. |
| `run_or_exit(fn)` | Calls `fn()`; on `DatadogAPIError` prints a remediation hint and `sys.exit(2)`. Wrap the body of `main()`. |
| `print_json(obj)` | Pretty-printed JSON to stdout. |
| `web_url(path='')` | Builds an `https://app.<site><path>` URL — use to print clickable pivot links. |
| `SITE`, `API_KEY`, `APP_KEY` | Resolved values. |

## Troubleshooting

**`ERROR: ~/.claude/skills/dd-setup/.env does not exist`** — copy `.env.example` to `.env` in this directory and fill in the values.

**`401 Unauthorized` on `/api/v1/validate`** — `DD_API_KEY` is wrong or revoked. Generate a fresh API key in *Organization Settings* and update `.env`.

**`403 Forbidden` on a probe** — the App key is missing a scope. The smoke test prints which probe failed; map it to the scope:

| Probe | Scope to add |
|---|---|
| `logs_read_data` failure | `logs_read_data` |
| `metrics_read` failure   | `metrics_read` |
| `monitors_read` failure  | `monitors_read` |
| `apm_read` failure       | `apm_read` |

Then re-run the smoke test.

**`ERROR: 'requests' not installed`** — run `pip install requests python-dotenv` in whichever Python environment is first on PATH (the same one `jira-ticket-enhancer` uses).

**Wrong site** — the smoke test will return DNS or 404 errors. Find the correct host from the Datadog web UI URL and update `DD_SITE`.

## What this skill does NOT do

- Does not write to Datadog. Read-only by design.
- Does not bootstrap an MCP server — the `dd-*` family uses the REST API directly.
- Does not store credentials anywhere except the local `.env`. Do not paste keys into chat, settings.json, or git-tracked files.
