[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('triage', 'heartbeat', 'kb-approver', 'stability-review')]
    [string]$Routine
)

$ErrorActionPreference = 'Stop'

$RepoRoot = 'C:\MethodDev\triage-bot'
Set-Location $RepoRoot

# Ensure user-scope Python is on PATH for the claude subprocess (winget
# user-scope installs don't always propagate to non-interactive shells).
$pyDir = Join-Path $env:USERPROFILE 'AppData\Local\Programs\Python\Python312'
$pyScripts = Join-Path $pyDir 'Scripts'
if ((Test-Path $pyDir) -and ($env:Path -notlike "*$pyDir*")) {
    $env:Path = "$pyDir;$pyScripts;$env:Path"
}

# Load .env so child processes (claude, python scripts) inherit credentials.
$envFile = Join-Path $RepoRoot '.env'
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq '' -or $line.StartsWith('#')) { return }
        $parts = $line.Split('=', 2)
        if ($parts.Count -ne 2) { return }
        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        Set-Item -Path "Env:$name" -Value $value
    }
}

# Pull latest main so prompt edits propagate without redeploying the script.
# Non-fatal: if pull fails (network, conflicts, branch divergence), keep going
# with the local tree.
try {
    git pull --ff-only 2>&1 | Write-Host
}
catch {
    Write-Warning "git pull --ff-only failed: $_  -- continuing with local tree"
}

$logsDir = Join-Path $RepoRoot 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')
$logFile = Join-Path $logsDir ($Routine + '-' + $stamp + '.json')

$promptFile = Join-Path $RepoRoot ('routines\' + $Routine + '.prompt.md')
if (-not (Test-Path $promptFile)) {
    Write-Error "Prompt file not found: $promptFile"
    exit 1
}

$claudeExe = Join-Path $env:USERPROFILE '.local\bin\claude.exe'
if (-not (Test-Path $claudeExe)) { $claudeExe = 'claude' }

Write-Host "invoke-routine: $Routine -> $logFile"

Get-Content -Raw $promptFile |
    & $claudeExe -p '' --output-format json --permission-mode acceptEdits 2>&1 |
    Tee-Object -FilePath $logFile

exit $LASTEXITCODE
