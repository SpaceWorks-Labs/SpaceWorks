<#
  Space Works - developer helper for Windows checkouts. It does not install anything.
  Servers install with the one-line install.sh on Linux or macOS; on Windows run that inside
  WSL2 (Ubuntu) or a Linux VM. See docs/install-and-update.md.
#>
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

throw "Run 'bash setup.sh' from Git Bash, WSL2, or your Linux server. The Bash entry point checks the required host orchestration capabilities."
