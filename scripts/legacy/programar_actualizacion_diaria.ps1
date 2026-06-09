$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$Script = Join-Path $ScriptDir "actualizar_historico_diario.bat"
$TaskName = "Farmazion SmartPOS - Actualizar historico diario"

if (-not (Test-Path $Script)) {
    throw "No existe el script diario: $Script"
}

$Action = New-ScheduledTaskAction -Execute $Script -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Actualiza el historico local desde SmartPOS y mezcla los ultimos 35 dias sin duplicados." `
    -Force

Write-Host "Tarea programada: $TaskName todos los dias a las 3:00 AM"
