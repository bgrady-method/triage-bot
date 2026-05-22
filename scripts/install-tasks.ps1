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

$principal = New-ScheduledTaskPrincipal `
    -UserId $user `
    -LogonType Interactive `
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
