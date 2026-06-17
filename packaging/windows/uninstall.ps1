param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "MotionSmith")
)

$ErrorActionPreference = "Stop"

$StartShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\MotionSmith.lnk"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "MotionSmith.lnk"

Remove-Item -Force $StartShortcut -ErrorAction SilentlyContinue
Remove-Item -Force $DesktopShortcut -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue

Write-Host "MotionSmith removed from $InstallDir"
