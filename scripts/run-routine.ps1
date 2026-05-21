param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('triage','kb-approver','heartbeat','stability-review')]
    [string]$Routine,

    [switch]$Force
)

$ErrorActionPreference = 'Continue'
$repoRoot = 'C:\MethodDev\triage-bot'
Set-Location $repoRoot

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
    'triage' = 'Run the triage routine. Read routines/triage.yaml and prompt.md from this repo for the procedure, then execute it end-to-end. Operate as the triage-bot: investigate new alerts, classify them, DM Ben, update KB proposals, and commit per the prompt instructions.'
    'kb-approver' = 'Run the kb-approver routine. Read routines/kb-approver.yaml from this repo for the full inline prompt and execute it end-to-end.'
    'heartbeat' = 'Run the heartbeat routine. Read routines/heartbeat.yaml from this repo for the full inline prompt and execute it end-to-end.'
    'stability-review' = 'Run the stability-review routine. Read routines/stability-review.yaml and stability-review-prompt.md from this repo for the full procedure and execute it end-to-end.'
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

# Push any commits the routine made. The bot's own kb-approver bootstrap
# expects GH_TOKEN in the env, which Task Scheduler doesn't provide — so
# we fetch the user's gh token and push with an inline URL.
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
