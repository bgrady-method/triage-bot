$ErrorActionPreference = 'Stop'

$repoRoot = 'C:\MethodDev\triage-bot'
$wrapperPath = Join-Path $repoRoot 'scripts\run-routine.ps1'
$user = "$env:USERDOMAIN\$env:USERNAME"
$folder = 'TriageBot'

if (-not (Test-Path $wrapperPath)) {
    throw "Wrapper not found at $wrapperPath"
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

# LogonType S4U ("run whether user is logged on or not"), not Interactive.
#
# Why: on 2026-07-15 a Windows update rebooted the box at 03:48. The machine was
# up the whole morning, but every task sat ineligible until someone logged in at
# 10:55 — because Interactive tasks require a logon session to exist. Four triage
# cycles (07:07-10:07) and one heartbeat were silently missed. StartWhenAvailable
# cannot help: with no session the task is never eligible in the first place.
#
# S4U runs as $user without storing a password. claude.exe authenticates from
# CLAUDE_CODE_OAUTH_TOKEN in .env (see memory: headless claude auth 401), so it
# should not need the interactive profile — but S4U does NOT load the full user
# profile, so this needs real-world verification.
#
# VERIFY: the only true test is a reboot/logoff — confirm the next scheduled
# triage still exits 0 with a real commit. If it starts returning 401s, revert
# this single line to `-LogonType Interactive` and re-run this script. The
# watchdog below is credential-independent and will report the failure either
# way, which is most of the value.
$principal = New-ScheduledTaskPrincipal `
    -UserId $user `
    -LogonType S4U `
    -RunLevel Limited

function Register-RoutineTask {
    param(
        [string]$Name,
        [int[]]$Hours,
        [int]$Minute
    )

    $action = New-ScheduledTaskAction `
        -Execute 'powershell.exe' `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapperPath`" -Routine $Name" `
        -WorkingDirectory $repoRoot

    $triggers = @()
    foreach ($h in $Hours) {
        $when = [datetime]::Today.AddHours($h).AddMinutes($Minute)
        $triggers += New-ScheduledTaskTrigger -Daily -At $when
    }

    $taskName = "$folder\$Name"
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $triggers `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null

    $minStr = $Minute.ToString('00')
    Write-Host "Registered: $taskName ($($Hours.Count) daily triggers @ :$minStr)"
}

Register-RoutineTask -Name 'triage'       -Hours (7..18)                  -Minute 7
Register-RoutineTask -Name 'heartbeat'    -Hours @(0,6,12,18)             -Minute 3

# stability-review: weekly Tuesday 9:23am; wrapper enforces first-Tuesday-of-month
$srAction = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapperPath`" -Routine stability-review" `
    -WorkingDirectory $repoRoot
$srTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At '9:23am'
Register-ScheduledTask `
    -TaskName "$folder\stability-review" `
    -Action $srAction `
    -Trigger $srTrigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null
Write-Host "Registered: $folder\stability-review (weekly Tuesday 9:23am, wrapper guards first-Tuesday-of-month)"

# watchdog: credential-independent failure detector. Runs every 2h at :47 (offset
# ~40min after the :07 triage fire) so it catches auth-401 / failed / scheduler-stale
# states even when claude.exe is fully down. Pure PowerShell + slack_send.py — never
# calls the model, so it survives the exact failure that blinds the heartbeat canary.
$wdScript = Join-Path $repoRoot 'scripts\watchdog-runs.ps1'
$wdAction = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wdScript`"" `
    -WorkingDirectory $repoRoot
$wdTriggers = @()
foreach ($h in @(8,10,12,14,16,18,20)) {
    $wdTriggers += New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($h).AddMinutes(47))
}
Register-ScheduledTask `
    -TaskName "$folder\watchdog" `
    -Action $wdAction `
    -Trigger $wdTriggers `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null
Write-Host "Registered: $folder\watchdog ($($wdTriggers.Count) daily triggers @ :47, every 2h 08-20)"

# weekly-digest: Mondays 09:00, 15 min ahead of pir-ingest so the two weeklies
# don't contend for the same working tree. Reports the week's SUPPRESSED
# recurrences (triage no longer posts them) so that going quiet stays honest.
# Read-only: never classifies, never writes KB, never opens a PR.
$wdgAction = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapperPath`" -Routine weekly-digest" `
    -WorkingDirectory $repoRoot
$wdgTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At '9:00am'
Register-ScheduledTask `
    -TaskName "$folder\weekly-digest" `
    -Action $wdgAction `
    -Trigger $wdgTrigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null
Write-Host "Registered: $folder\weekly-digest (weekly Monday 9:00am)"

# pir-ingest: weekly Monday 9:15am
$piAction = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapperPath`" -Routine pir-ingest" `
    -WorkingDirectory $repoRoot
$piTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At '9:15am'
Register-ScheduledTask `
    -TaskName "$folder\pir-ingest" `
    -Action $piAction `
    -Trigger $piTrigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null
Write-Host "Registered: $folder\pir-ingest (weekly Monday 9:15am)"

Write-Host ''
Write-Host 'Done. Inspect with:  schtasks /query /tn "\TriageBot\heartbeat" /v /fo LIST'
Write-Host 'Run heartbeat now:   schtasks /run /tn "\TriageBot\heartbeat"'
