<#
  Space Works - Open Source Makerspace Manager first-run setup for self-hosting (Windows).
  Right-click -> "Run with PowerShell", or run:  powershell -ExecutionPolicy Bypass -File setup.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

throw "Run 'bash setup.sh' from Git Bash, WSL2, or your Linux server. The Bash entry point checks the required host orchestration capabilities."
