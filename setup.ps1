# InternTrack Setup Script for Windows
# Run this script in PowerShell to set up the project

# Stop on errors
$ErrorActionPreference = "Stop"

# Set execution policy for this session
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction SilentlyContinue

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "   InternTrack Setup Script" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Python not found" }
    
    # Check if version is 3.11+
    $versionString = (python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    $versionParts = $versionString.Split('.')
    $major = [int]$versionParts[0]
    $minor = [int]$versionParts[1]
    
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
        Write-Host "Python 3.11+ required. Found: $pythonVersion" -ForegroundColor Red
        exit 1
    }
    Write-Host "Python found: $pythonVersion (3.11+ verified)" -ForegroundColor Green
} catch {
    Write-Host "Python not found. Please install Python 3.11+ from https://python.org" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
Write-Host "Virtual environment activated" -ForegroundColor Green

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
Write-Host "Dependencies installed" -ForegroundColor Green

# Copy environment file
Write-Host ""
Write-Host "Setting up environment..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env file from .env.example" -ForegroundColor Green
    Write-Host "Please edit .env with your configuration" -ForegroundColor Yellow
} else {
    Write-Host ".env file already exists" -ForegroundColor Green
}

# Create directories
Write-Host ""
Write-Host "Creating directories..." -ForegroundColor Yellow
if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path "data" }
if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" }
if (-not (Test-Path "backups")) { New-Item -ItemType Directory -Path "backups" }
Write-Host "Directories created" -ForegroundColor Green

# Verify installation
Write-Host ""
Write-Host "Verifying installation..." -ForegroundColor Yellow
$env:PYTHONPATH = "src"
python -c "import interntrack; print('Import successful')"
Write-Host "Installation verified" -ForegroundColor Green

# Print summary
Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the application:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Activate virtual environment:" -ForegroundColor White
Write-Host "     venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. Set PYTHONPATH:" -ForegroundColor White
Write-Host "     `$env:PYTHONPATH = `"src`"" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. Start the API server:" -ForegroundColor White
Write-Host "     uvicorn interntrack.main:app --reload" -ForegroundColor Yellow
Write-Host ""
Write-Host "  4. Open browser:" -ForegroundColor White
Write-Host "     http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "  5. (Optional) Start dashboard:" -ForegroundColor White
Write-Host "     streamlit run dashboard/app.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
