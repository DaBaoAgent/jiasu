# redirect_known_folders.ps1 - Redirect user folders (Desktop/Documents/...) to another drive.
# Same approach as Sophia's Known Folder relocation: only registry pointers change (HKCU),
# files are NOT moved. Reversible with -Undo. No admin needed (HKCU keys).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File redirect_known_folders.ps1                          # show current
#   powershell -ExecutionPolicy Bypass -File redirect_known_folders.ps1 -Redirect D:\Users\xxx13 # redirect
#   powershell -ExecutionPolicy Bypass -File redirect_known_folders.ps1 -Undo                    # restore defaults
#
# NOTE: files already in the old C: folders are NOT moved automatically.
#       Move them first (robocopy "C:\Users\<user>\Desktop" "D:\Users\<user>\Desktop" /MOVE /E).
param(
    [string]$Redirect = "",
    [switch]$Undo
)

$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
$folders = @{
    "Desktop"   = "Desktop"
    "Documents" = "Personal"
    "Downloads" = "{374DE290-123F-4565-9164-39C4925E467B}"
    "Pictures"  = "My Pictures"
    "Music"     = "My Music"
    "Videos"    = "My Video"
}

if (-not $Undo -and $Redirect -eq "") {
    Write-Host "Current user folder pointers:"
    foreach ($name in $folders.Keys) {
        $val = (Get-ItemProperty -Path $key -Name $folders[$name] -ErrorAction SilentlyContinue).($folders[$name])
        Write-Host ("  {0,-10} {1}" -f $name, $val)
    }
    Write-Host ""
    Write-Host "Usage: -Redirect D:\Users\xxx13   or   -Undo"
    exit
}

# Backup current settings first (reversibility guarantee)
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupDir = Join-Path $env:USERPROFILE "jiasu_known_folder_backup"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
reg export $key.Replace('HKCU:', 'HKCU') (Join-Path $backupDir "user_shell_folders_$ts.reg") /y | Out-Null
Write-Host "Backup saved -> $backupDir\user_shell_folders_$ts.reg"

if ($Undo) {
    Write-Host "Restoring default user folder pointers:"
    foreach ($name in $folders.Keys) {
        Remove-ItemProperty -Path $key -Name $folders[$name] -ErrorAction SilentlyContinue
        Write-Host "  OK $name -> default"
    }
    Write-Host "Done. Explorer restart may be needed."
    exit
}

$target = $Redirect.TrimEnd('\')
if (-not (Test-Path $target)) {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Write-Host "Created target dir: $target"
}
Write-Host "Redirecting user folders -> $target :"
foreach ($name in $folders.Keys) {
    $dest = Join-Path $target $name
    Set-ItemProperty -Path $key -Name $folders[$name] -Value $dest -Type ExpandString
    Write-Host "  OK $name -> $dest"
}
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Move old files: robocopy \"C:\Users\$env:USERNAME\Desktop\" \"$target\Desktop\" /MOVE /E"
Write-Host "  2. Restart Explorer or sign out/in"
Write-Host "  Rollback: rerun with -Undo, or reg import the backup .reg"
