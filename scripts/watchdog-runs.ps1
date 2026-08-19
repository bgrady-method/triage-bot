<#
.SYNOPSIS
  Credential-independent watchdog for the triage-bot routines.

.DESCRIPTION
  The triage/heartbeat/stability routines all run through the SAME `claude.exe`.
  When that auth breaks (e.g. the stored OAuth access token expires and the
  headless `claude -p` runs can't refresh it), every routine - INCLUDING the
  heartbeat health-canary - dies on turn 1 with HTTP 401 and no alert ever
  reaches Ben. The bot's self-monitoring is blind to its own auth failure.

  This watchdog closes that blind spot. It NEVER calls the Claude API. It reads
  the local run artifacts (logs/runs.jsonl + the latest logs/triage-*.json) and,
  if the recent triage runs are failing (or the scheduler has gone quiet during
  active hours), DMs Ben via scripts/slack_send.py (pure Slack Web API, the same
  send path the bot already uses). Because it depends only on the Slack bot token
  - not on the model credential - it survives the exact failure that silenced
  the routines on 2026-06-20.

  Schedule it on its own Task Scheduler trigger (e.g. every 2-3h) so it keeps
  watching even when claude.exe is completely dead.

.NOTES
  Failure modes detected:
    * auth-401        - latest triage run output contains api_error_status:401
    * runs-failed     - the last N triage runs in runs.jsonl are status=failed
    * scheduler-stale - no triage run produced in StaleMinutes during active hours
  De-dup: state in logs/watchdog-state.json; re-alerts at most every ReAlertHours
  while still unhealthy, plus a one-time "recovered" note on the way back up.
#>
param(
    [int]$FailStreak    = 2,    # how many trailing failed triage runs trigger an alert
    [int]$StaleMinutes  = 135,  # no triage run in this long (during active hours) = scheduler stale
    [int]$ReAlertHours  = 6,    # while still down, re-nag at most this often
    [int]$ActiveStart   = 7,    # local hour the hourly triage triggers begin (:07 past 07..18)
    [int]$ActiveEnd     = 19,
    [switch]$DryRun             # print what it would send; do not DM
)

$ErrorActionPreference = 'Continue'
$repoRoot = 'C:\MethodDev\triage-bot'
Set-Location $repoRoot

$logDir    = Join-Path $repoRoot 'logs'
$runsLog   = Join-Path $logDir 'runs.jsonl'
$stateFile = Join-Path $logDir 'watchdog-state.json'
$selfLog   = Join-Path $logDir 'watchdog.log'

function Write-SelfLog([string]$msg) {
    $line = "{0}  {1}" -f (Get-Date).ToUniversalTime().ToString('o'), $msg
    Add-Content -Path $selfLog -Value $line -Encoding utf8
}

# --- Load .env (same hydration run-routine.ps1 does) so we get SLACK_BOT_TOKEN ---
$envFile = Join-Path $repoRoot '.env'
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { return }
        $name = $line.Substring(0, $eq).Trim()
        $value = $line.Substring($eq + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "env:$name" -Value $value
    }
}

# Ben's Slack user id is resolved at runtime by the routine (via users.info) and
# isn't in .env; it's stable, so default it here with an env override.
$benUser = if ($env:BEN_USER_ID) { $env:BEN_USER_ID } else { 'U063EFBAY95' }

# --- Gather the recent triage run history from runs.jsonl ---
$triageRuns = @()
if (Test-Path $runsLog) {
    $triageRuns = Get-Content $runsLog -Tail 80 -Encoding utf8 | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { $null }
    } | Where-Object { $_ -and $_.routine -eq 'triage' }
}

# Trailing failure streak (most-recent-first)
$streak = 0
for ($i = $triageRuns.Count - 1; $i -ge 0; $i--) {
    if ($triageRuns[$i].status -eq 'failed') { $streak++ } else { break }
}

# --- Inspect the newest triage-*.json for the 401 signature + staleness ---
$latest = Get-ChildItem -Path $logDir -Filter 'triage-*.json' -File -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime | Select-Object -Last 1
$is401 = $false
$latestAgeMin = [double]::PositiveInfinity
if ($latest) {
    $latestAgeMin = ((Get-Date) - $latest.LastWriteTime).TotalMinutes
    if (Select-String -Path $latest.FullName -Pattern '"api_error_status":\s*401|401 Invalid authentication' -Quiet -ErrorAction SilentlyContinue) {
        $is401 = $true
    }
}

$nowHour    = (Get-Date).Hour
$inActive   = ($nowHour -ge $ActiveStart -and $nowHour -lt $ActiveEnd)
$isStale    = ($inActive -and $latestAgeMin -gt $StaleMinutes)

# --- Decide health + reason ---
$unhealthy = $false
$reason    = $null
$detail    = $null
if ($is401) {
    $unhealthy = $true; $reason = 'auth-401'
    $detail = "headless claude.exe is returning HTTP 401 (auth). The OAuth access token expired and unattended runs don't refresh it. Fix: mint ``claude setup-token`` as MachineUser and set CLAUDE_CODE_OAUTH_TOKEN in .env."
}
elseif ($streak -ge $FailStreak) {
    $unhealthy = $true; $reason = 'runs-failed'
    $detail = "the last $streak triage runs exited status=failed. Check the newest logs/triage-*.json for the error."
}
elseif ($isStale) {
    $unhealthy = $true; $reason = 'scheduler-stale'
    $age = [math]::Round($latestAgeMin)
    $detail = "no triage run has been produced in ~$age min during active hours (expected hourly at :07). Task Scheduler may be stopped or the \TriageBot\triage task disabled."
}

# --- Load prior state for de-dup ---
$prev = $null
if (Test-Path $stateFile) {
    try { $prev = Get-Content $stateFile -Raw -Encoding utf8 | ConvertFrom-Json } catch { $prev = $null }
}
$prevStatus = if ($prev) { $prev.status } else { 'unknown' }
$prevAlertAt = if ($prev -and $prev.last_alert_at) { [datetime]::Parse($prev.last_alert_at).ToUniversalTime() } else { [datetime]::MinValue }

$nowUtc = (Get-Date).ToUniversalTime()
$status = if ($unhealthy) { 'unhealthy' } else { 'healthy' }

# When to actually send:
$shouldAlert = $false
$msg = $null
if ($unhealthy) {
    $newlyDown = ($prevStatus -ne 'unhealthy')
    $staleNag  = (($nowUtc - $prevAlertAt).TotalHours -ge $ReAlertHours)
    if ($newlyDown -or $staleNag) {
        $shouldAlert = $true
        $lastOk = ($triageRuns | Where-Object { $_.status -eq 'ok' } | Select-Object -Last 1)
        $lastOkTs = if ($lastOk) { $lastOk.ended_at } else { 'unknown' }
        $msg = ":rotating_light: triage-bot watchdog - routines DOWN ($reason). $detail Last healthy triage run: $lastOkTs. No alerts/DMs are being produced until this is fixed."
    }
}
elseif ($prevStatus -eq 'unhealthy') {
    # Recovered: one-time note
    $shouldAlert = $true
    $msg = ":white_check_mark: triage-bot watchdog - routines RECOVERED. Triage runs are succeeding again."
}

# --- Act ---
if ($shouldAlert -and $msg) {
    if ($DryRun) {
        Write-Output "[dry-run] would DM $benUser : $msg"
        Write-SelfLog "DRY-RUN alert ($status/$reason): $msg"
    } else {
        $py = (Get-Command python -ErrorAction SilentlyContinue).Source
        if (-not $py) { $py = 'python' }
        $sendScript = Join-Path $repoRoot 'scripts\slack_send.py'
        & $py $sendScript dm --user $benUser --text $msg --type health 2>&1 | ForEach-Object { Write-SelfLog "slack_send: $_" }
        if ($LASTEXITCODE -eq 0) {
            Write-SelfLog "ALERT SENT ($status/$reason)"
            $prevAlertAt = $nowUtc
        } else {
            Write-SelfLog "ALERT SEND FAILED (exit $LASTEXITCODE) ($status/$reason) - token/channel issue"
        }
    }
} else {
    Write-SelfLog "no-alert (status=$status reason=$reason streak=$streak latestAgeMin=$([math]::Round($latestAgeMin)) prev=$prevStatus)"
}

# --- Persist state ---
$newState = [pscustomobject]@{
    status        = $status
    reason        = $reason
    fail_streak   = $streak
    latest_log    = if ($latest) { $latest.Name } else { $null }
    checked_at    = $nowUtc.ToString('o')
    last_alert_at = if ($shouldAlert -and -not $DryRun) { $prevAlertAt.ToString('o') }
                    elseif ($prev) { $prev.last_alert_at } else { $null }
} | ConvertTo-Json -Compress
Set-Content -Path $stateFile -Value $newState -Encoding utf8

Write-Output "watchdog: status=$status reason=$reason streak=$streak latestAgeMin=$([math]::Round($latestAgeMin)) alerted=$shouldAlert"
