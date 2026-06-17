param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "MotionSmith"),
    [switch]$NoDesktopShortcut
)

$ErrorActionPreference = "Stop"

$SourceDir = Join-Path $PSScriptRoot "MotionSmith"
$SourceExe = Join-Path $SourceDir "MotionSmith.exe"
if (-not (Test-Path $SourceExe)) {
    throw "MotionSmith folder must be next to install.ps1. Extract the zip before installing."
}

Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $InstallDir) | Out-Null
Copy-Item -Recurse -Force $SourceDir $InstallDir

$InstalledExe = Join-Path $InstallDir "MotionSmith.exe"
$Shell = New-Object -ComObject WScript.Shell

$ProgramsDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
New-Item -ItemType Directory -Force -Path $ProgramsDir | Out-Null
$StartShortcut = $Shell.CreateShortcut((Join-Path $ProgramsDir "MotionSmith.lnk"))
$StartShortcut.TargetPath = $InstalledExe
$StartShortcut.WorkingDirectory = $InstallDir
$StartShortcut.Save()

if (-not $NoDesktopShortcut) {
    $DesktopShortcut = $Shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "MotionSmith.lnk"))
    $DesktopShortcut.TargetPath = $InstalledExe
    $DesktopShortcut.WorkingDirectory = $InstallDir
    $DesktopShortcut.Save()
}

Write-Host "MotionSmith installed to $InstallDir"
Write-Host "Launch it from the Start Menu shortcut or run $InstalledExe"
