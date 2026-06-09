@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ports=@(8002); $ids=@(); foreach($line in (netstat -ano)){ foreach($port in $ports){ if($line -match ('^\s*TCP\s+\S+:' + $port + '\s+\S+\s+LISTENING\s+(\d+)$')){ $ids += [int]$Matches[1] } } }; $ids=$ids | Select-Object -Unique; if($ids){ foreach($procId in $ids){ Write-Host ('[Backend] Cerrando PID ' + $procId); Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } } else { Write-Host '[Backend] No habia proceso escuchando en 8002' }"
endlocal
