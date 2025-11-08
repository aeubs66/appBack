# Start Celery worker for PDF processing
# Run this from backend directory: .\start_worker.ps1

$ErrorActionPreference = "Stop"

# Check if venv exists
if (-not (Test-Path ".\venv\Scripts\Activate.ps1")) {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Create it with: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "=== Starting Celery Worker ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1

Write-Host "Starting Celery worker for PDF processing..." -ForegroundColor Green
Write-Host ""
Write-Host "Worker will process tasks from Redis queue" -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop the worker" -ForegroundColor Gray
Write-Host ""

# Start Celery worker with solo pool (required for Windows + Python 3.13)
# --pool=solo fixes "not enough values to unpack" error
python -m celery -A app.workers.celery_app worker --loglevel=info --pool=solo

