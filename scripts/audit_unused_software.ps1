# Audit Unused Software — scans installed programs and checks last-activity dates.
# Finds programs unused for 60+ days. Run: powershell -File audit_unused_software.ps1
# In bash/MSYS: use -JsonOut flag to write JSON file, then analyze with Python.
param([switch]$JsonOut)

$ErrorActionPreference = 'SilentlyContinue'
$now = Get-Date
$cutoff = $now.AddDays(-60)

$apps = @()
$paths = @(
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
foreach ($path in $paths) {
    $items = Get-ItemProperty $path
    foreach ($item in $items) {
        if ($item.DisplayName) {
            $loc = if ($item.InstallLocation) { $item.InstallLocation.TrimEnd('\').Trim('"') } else { '' }
            $exeTime = $null
            $dirTime = $null
            if ($loc -and (Test-Path $loc)) {
                $dirTime = (Get-Item $loc).LastWriteTime
                $exes = Get-ChildItem -Path $loc -Filter *.exe -Recurse -Depth 2 -ErrorAction SilentlyContinue |
                    Sort-Object LastWriteTime -Descending | Select-Object -First 1
                if ($exes) { $exeTime = $exes.LastWriteTime }
            }
            $latest = if ($exeTime -and $dirTime) {
                if ($exeTime -gt $dirTime) { $exeTime } else { $dirTime }
            } elseif ($exeTime) { $exeTime } elseif ($dirTime) { $dirTime } else { $null }
            
            $apps += [PSCustomObject]@{
                Name = $item.DisplayName
                Location = $loc
                UninstallString = if ($item.UninstallString) { $item.UninstallString } else { '' }
                LastActivity = if ($latest) { $latest.ToString('yyyy-MM-dd') } else { '' }
                DaysIdle = if ($latest) { [math]::Floor(($now - $latest).TotalDays) } else { -1 }
            }
        }
    }
}

# Filter system components
$skipPatterns = @(
    'Microsoft Visual C++', 'Driver', 'Runtime', 'Update for', 'Package',
    'Language Pack', 'SDK', '.NET', 'WebView2', 'Update for Microsoft',
    'Security Update', 'Hotfix', 'Service Pack', 'Windows', 'Office',
    'Edge', 'OneDrive', 'Update Health', 'Core Interpreter',
    'Development Libraries', 'Documentation', 'Executables',
    'pip Bootstrap', 'Standard Library', 'Tcl/Tk Support', 'Test Suite',
    'Add to Path', 'Python Launcher'
)
$filtered = $apps | Where-Object {
    $n = $_.Name
    $skip = $false
    foreach ($p in $skipPatterns) { if ($n -match $p) { $skip = $true; break } }
    -not $skip
}

if ($JsonOut) {
    # JSON file output — use when calling from bash/MSYS to avoid encoding issues
    $outPath = Join-Path (Get-Location) "_app_analysis.json"
    $filtered | Sort-Object Name | ConvertTo-Json -Depth 2 | Out-File -FilePath $outPath -Encoding UTF8
    Write-Host "Wrote $($filtered.Count) apps to $outPath"
    Write-Host "Analyze with: python -c \"import json,datetime; ...\""
} else {
    # Direct console output
    Write-Host "=== IDLE 60+ DAYS ===" -ForegroundColor Red
    $filtered | Where-Object { $_.DaysIdle -gt 60 } | Sort-Object DaysIdle -Descending | ForEach-Object {
        Write-Host "  $($_.DaysIdle)d  $($_.Name)" -ForegroundColor Yellow
        Write-Host "        Last: $($_.LastActivity) | $($_.Location)"
    }

    Write-Host ""
    Write-Host "=== ACTIVE (< 60 DAYS) ===" -ForegroundColor Green
    $filtered | Where-Object { $_.DaysIdle -ge 0 -and $_.DaysIdle -le 60 } | Sort-Object DaysIdle | ForEach-Object {
        Write-Host "  $($_.DaysIdle)d  $($_.Name)"
    }

    Write-Host ""
    Write-Host "=== UNKNOWN (no timestamp) ===" -ForegroundColor Gray
    $filtered | Where-Object { $_.DaysIdle -lt 0 } | ForEach-Object {
        Write-Host "  ???  $($_.Name) -- $($_.Location)"
    }

    Write-Host ""
    $idleCount = ($filtered | Where-Object { $_.DaysIdle -gt 60 }).Count
    $activeCount = ($filtered | Where-Object { $_.DaysIdle -ge 0 -and $_.DaysIdle -le 60 }).Count
    $unknownCount = ($filtered | Where-Object { $_.DaysIdle -lt 0 }).Count
    Write-Host "Summary: $idleCount idle | $activeCount active | $unknownCount unknown"
}
