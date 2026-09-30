Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "SECURE SSI PLATFORM - ACADEMIC THESIS DEMO RUNNER" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
if (Test-Path ".\.venv\Scripts\python.exe") {
    & ".\.venv\Scripts\python.exe" scripts/start_demo.py flow
} else {
    python scripts/start_demo.py flow
}
