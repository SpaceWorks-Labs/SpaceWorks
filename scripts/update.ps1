<# Production update entry point. #>
[CmdletBinding()]
param([switch]$Force)
throw "Run 'bash scripts/update.sh' from Git Bash, WSL2, or your Linux server (add --force only when needed). The Bash updater checks the required host operation lock."
