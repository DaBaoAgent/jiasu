# system_repair.ps1 - Windows system repair toolkit (like winutil's Fixes tab)
# Use when: "PC slow / system corrupt / update fails / after BSOD". Needs admin for fix steps.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File system_repair.ps1 -Steps sfc
#   powershell -ExecutionPolicy Bypass -File system_repair.ps1 -Steps sfc,dism   # default
#   powershell -ExecutionPolicy Bypass -File system_repair.ps1 -Steps all       # everything incl. WU reset
#   powershell -ExecutionPolicy Bypass -File system_repair.ps1 -Steps check     # diagnose only
# Log: C:\Users\<user>\system_repair.log  (elevated output lands in user dir - see SKILL.md)
param(
    [string]$Steps = "sfc,dism"
)

$ErrorActionPreference = 'Continue'
$log = Join-Path $env:USERPROFILE "system_repair.log"
function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding UTF8
}
if (-not (Test-Path $log)) { New-Item -Path $log -ItemType File -Force | Out-Null }

$steps = @($Steps.Split(',') | ForEach-Object { $_.Trim().ToLower() })
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
            ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Log "WARN: not elevated - diagnose steps only. Run elevated for full repair."
}

Log "===== system_repair start (steps: $($steps -join ',')) ====="

if ($steps -contains 'check' -or $steps -contains 'all') {
    Log "--- diagnose ---"
    $os = Get-CimInstance Win32_OperatingSystem
    Log "Windows: $($os.Caption) $($os.Version)"
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    Log ("C: {0:N1} GB used / {1:N1} GB free" -f ($disk.Size/1GB), ($disk.FreeSpace/1GB))
    Log "If system files may be corrupt, run: sfc /scannow + DISM /RestoreHealth"
}

if ($steps -contains 'sfc' -or $steps -contains 'all') {
    Log "--- SFC scannow (5-15 min, window may look frozen) ---"
    sfc /scannow | Out-Host
    Log "SFC done, exit=$LASTEXITCODE (0=ok, 1=fixed, 2=reboot and rerun)"
}

if ($steps -contains 'dism' -or $steps -contains 'all') {
    Log "--- DISM RestoreHealth (10-30 min, may download repair source) ---"
    Dism /Online /Cleanup-Image /RestoreHealth | Out-Host
    Log "DISM done, exit=$LASTEXITCODE (0=ok, 1=reboot, 2=needs mounted source)"
}

if ($steps -contains 'wu' -or $steps -contains 'all') {
    Log "--- Windows Update service reset (use when updates stuck/failing) ---"
    Log "WARN: clears update cache; next update re-downloads"
    Stop-Service wuauserv, bits, cryptsvc, msiserver -Force -ErrorAction SilentlyContinue
    Rename-Item C:\Windows\SoftwareDistribution SoftwareDistribution.old -Force -ErrorAction SilentlyContinue
    Rename-Item C:\Windows\System32\catroot2 Catroot2.old -Force -ErrorAction SilentlyContinue
    Start-Service wuauserv, bits, cryptsvc, msiserver -ErrorAction SilentlyContinue
    Log "WU reset done. Old caches renamed to *.old; delete after updates work"
}

if ($steps -contains 'net' -or $steps -contains 'all') {
    Log "--- network stack reset (reboot required) ---"
    netsh winsock reset | Out-Host
    netsh int ip reset | Out-Host
    Log "network reset done. Reboot recommended"
}

if ($steps -contains 'all') {
    Log "All steps done. If system was broken, reboot and rerun sfc /scannow to confirm"
}

Log "===== system_repair end, log: $log ====="
