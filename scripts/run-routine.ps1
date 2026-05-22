param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('triage','heartbeat','stability-review','pir-ingest')]
    [string]$Routine,

    [switch]$Force
)

$ErrorActionPreference = 'Continue'
$repoRoot = 'C:\MethodDev\triage-bot'
Set-Location $repoRoot

# Load .env into the process env so the routine's helper scripts
# (scripts/dd_search.py, es_search.py, sql_query.py, mongo_query.py)
# can read DD_API_KEY / ELK_* / SQL_* / MONGO_URI_* etc.
# The cloud routine got these via its secrets store; Task Scheduler
# doesn't, so we hydrate them here.
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

# stability-review runs on the FIRST Tuesday of each month.
# Task Scheduler has no first-Tuesday-of-month trigger, so we use a weekly
# Tuesday trigger and bail out here on later Tuesdays. -Force bypasses
# the guard for manual/ad-hoc runs.
if ($Routine -eq 'stability-review' -and -not $Force -and (Get-Date).Day -gt 7) {
    exit 0
}

$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $repoRoot 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$outFile = Join-Path $logDir "$Routine-$ts.json"
$runsLog = Join-Path $logDir 'runs.jsonl'

$prompts = @{
    'triage' = 'Run the triage routine. Read routines/triage.yaml and prompt.md from this repo for the procedure, then execute it end-to-end. Operate as the triage-bot: investigate new alerts, classify them, DM Ben, write directly to kb/known-issues.json or kb/false-alarms.json when warranted, and commit per the prompt instructions.'
    'heartbeat' = 'Run the heartbeat routine. Read routines/heartbeat.yaml from this repo for the full inline prompt and execute it end-to-end.'
    'stability-review' = 'Run the stability-review routine. Read routines/stability-review.yaml and stability-review-prompt.md from this repo for the full procedure and execute it end-to-end.'
    'pir-ingest' = 'Run the pir-ingest routine. Read routines/pir-ingest.yaml from this repo for the full inline prompt and execute it end-to-end. Fetch the Method PIR Confluence blog (pageId 133496969) via Atlassian MCP, parse engineer-authored incident blocks, dedupe against kb/known-issues.json, and write any new entries with confidence=0.95.'
}

$prompt = $prompts[$Routine]
$startedAt = Get-Date
$claude = 'C:\Users\MachineUser\.local\bin\claude.exe'
$gh = 'C:\Program Files\GitHub CLI\gh.exe'
$exitCode = 1

try {
    # Pipe $null so claude.exe sees an immediate EOF on stdin instead of
    # waiting 3s for input it'll never get from Task Scheduler.
    $null | & $claude -p $prompt --output-format json *>&1 | Out-File -FilePath $outFile -Encoding utf8
    $exitCode = $LASTEXITCODE
} catch {
    "Exception: $($_.Exception.Message)" | Out-File -FilePath $outFile -Encoding utf8 -Append
    $exitCode = 1
}

# Push any commits the routine made. The bot's prompts expect GH_TOKEN
# in the env, which Task Scheduler doesn't provide — so we fetch the
# user's gh token and push with an inline URL.
$pushResult = 'skipped'
try {
    $token = & $gh auth token 2>$null
    if ($token) {
        $pushUrl = "https://x-access-token:$token@github.com/bgrady-method/triage-bot.git"
        $pushOut = & git push $pushUrl main 2>&1
        $pushResult = if ($LASTEXITCODE -eq 0) { 'ok' } else { 'failed' }
        "--- push ($pushResult) ---" | Out-File -FilePath $outFile -Append -Encoding utf8
        $pushOut | Out-File -FilePath $outFile -Append -Encoding utf8
    } else {
        $pushResult = 'no-token'
    }
} catch {
    $pushResult = 'error'
    "Push exception: $($_.Exception.Message)" | Out-File -FilePath $outFile -Append -Encoding utf8
}

$endedAt = Get-Date
$durationS = [math]::Round(($endedAt - $startedAt).TotalSeconds, 1)
$status = if ($exitCode -eq 0) { 'ok' } else { 'failed' }
$entry = [pscustomobject]@{
    routine = $Routine
    started_at = $startedAt.ToUniversalTime().ToString('o')
    ended_at = $endedAt.ToUniversalTime().ToString('o')
    duration_s = $durationS
    exit_code = $exitCode
    status = $status
    push = $pushResult
    output_file = $outFile
} | ConvertTo-Json -Compress
Add-Content -Path $runsLog -Value $entry -Encoding utf8
exit $exitCode
