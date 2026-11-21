# bootstrap.ps1: one command to set up a new Windows machine.
#
#   powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
#   powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 --profile server
#
# This is PowerShell only because Python is not available yet. It installs
# mise if it is missing, then runs the Python task mise/tasks/setup, which
# does the rest: Python and the user tools, then the winget packages.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Get-Command mise -ErrorAction SilentlyContinue)) {
    winget install --id jdx.mise --exact --silent --accept-package-agreements --accept-source-agreements
    # winget changes the user Path; load it into this session.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

mise trust mise\config.toml
mise run setup @args
exit $LASTEXITCODE
