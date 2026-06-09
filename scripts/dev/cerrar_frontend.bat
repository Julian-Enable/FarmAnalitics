@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ports=@(5173); $ids=@(); foreach($line in (netstat -ano)){ foreach($port in $ports){ if($line -match ('^\s*TCP\s+\S+:' + $port + '\s+\S+\s+LISTENING\s+(\d+)$')){ $ids += [int]$Matches[1] } } }; $ids=$ids | Select-Object -Unique; if($ids){ foreach($procId in $ids){ Write-Host ('[Frontend] Cerrando PID ' + $procId); Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } } else { Write-Host '[Frontend] No habia proceso escuchando en 5173' }"
endlocal
