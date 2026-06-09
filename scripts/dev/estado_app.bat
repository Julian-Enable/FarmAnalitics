@echo off
setlocal
echo ==============================================
echo       Estado FarmaAnalytics Local
echo ==============================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ports=@(8002,5173); foreach($port in $ports){ $ids=@(); foreach($line in (netstat -ano)){ if($line -match ('^\s*TCP\s+\S+:' + $port + '\s+\S+\s+LISTENING\s+(\d+)$')){ $ids += [int]$Matches[1] } }; $ids=$ids | Select-Object -Unique; if($ids){ Write-Host ('Puerto ' + $port + ': ACTIVO PID ' + ($ids -join ',')) } else { Write-Host ('Puerto ' + $port + ': APAGADO') } }"
echo.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8002/docs
endlocal
