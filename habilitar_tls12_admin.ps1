$path = "HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2\Client"

New-Item -Path $path -Force | Out-Null
New-ItemProperty -Path $path -Name "Enabled" -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $path -Name "DisabledByDefault" -Value 0 -PropertyType DWord -Force | Out-Null

Get-ItemProperty $path

Write-Host ""
Write-Host "TLS 1.2 Client habilitado. Reinicia Windows antes de volver a descargar el historico."
