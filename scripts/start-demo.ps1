param(
    [string]$Action = "status"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
$venvPy = Join-Path $rootDir ".venv\Scripts\python.exe"

if (Test-Path $venvPy) {
    & $venvPy (Join-Path $scriptDir "start_demo.py") $Action
} else {
    python (Join-Path $scriptDir "start_demo.py") $Action
}
