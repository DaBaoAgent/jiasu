# Pagefile migration: disable C: pagefile, create D: pagefile (system managed)
# Run as Administrator!
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File pagefile_migrate.ps1
# Or launch as admin from non-admin terminal:
#   Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File C:\path\to\pagefile_migrate.ps1'

Write-Host "=== Pagefile Migration ===" -ForegroundColor Cyan

try {
    # Get current state
    $pf = Get-CimInstance -ClassName Win32_PageFileUsage -ErrorAction SilentlyContinue
    if ($pf) {
        Write-Host "Current pagefiles:"
        foreach ($p in $pf) {
            Write-Host "  $($p.Name): $($p.AllocatedBaseSize) MB (max $($p.MaximumSize) MB)"
        }
    }

    # Step 1: Disable automatic management
    $sys = Get-CimInstance Win32_ComputerSystem
    if ($sys.AutomaticManagedPagefile -eq $true) {
        Write-Host "Disabling automatic pagefile management..."
        $sys.AutomaticManagedPagefile = $false
        Set-CimInstance -InputObject $sys
        Write-Host "OK - Auto management disabled" -ForegroundColor Green
    }

    # Step 2: Remove C: pagefile
    $c_pf = Get-CimInstance -ClassName Win32_PageFileSetting -Filter "SettingID='pagefile.sys @ C:'" -ErrorAction SilentlyContinue
    if ($c_pf) {
        Write-Host "Removing C: pagefile..."
        Remove-CimInstance -InputObject $c_pf
        Write-Host "OK - C: pagefile removed" -ForegroundColor Green
    }

    # Step 3: Create D: pagefile (system managed: InitialSize=0, MaximumSize=0 = system managed)
    Write-Host "Creating D: pagefile (system managed)..."
    Set-CimInstance -ClassName Win32_PageFileSetting -Arguments @{Name="D:\pagefile.sys"; InitialSize=0; MaximumSize=0}
    Write-Host "OK - D: pagefile created (system managed)" -ForegroundColor Green

    Write-Host ""
    Write-Host "Done! REBOOT required to apply changes." -ForegroundColor Yellow

} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "Run this script as Administrator!" -ForegroundColor Red
}
