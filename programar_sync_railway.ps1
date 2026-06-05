$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root "sincronizar_ahora.bat"
$TaskName = "Farmazion SmartPOS - Sincronizar Railway diario"

if (-not (Test-Path $Script)) {
    throw "No existe el script de sincronizacion: $Script"
}

$Action = New-ScheduledTaskAction -Execute $Script -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Actualiza historico, inventario actual y sube parquet al volumen de Railway." `
    -Force

Write-Host "Tarea programada: $TaskName todos los dias a las 3:00 AM"
