MotionSmith for Windows
=======================

Install for the current Windows user:

1. Extract MotionSmith-windows.zip.
2. In PowerShell from the extracted folder, run:

   powershell -ExecutionPolicy Bypass -File .\install.ps1

3. Launch MotionSmith from the Start Menu shortcut.

Uninstall:

   powershell -ExecutionPolicy Bypass -File .\uninstall.ps1

Notes:
- No administrator permission is required; the default install path is %LOCALAPPDATA%\MotionSmith.
- Research/test builds signed with a self-signed certificate may still show a Windows SmartScreen warning.
  Replace the GitHub WINDOWS_CERT_PFX secret with a CA-issued code-signing certificate for trusted public distribution.
