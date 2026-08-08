$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

function Assert-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Command not found: $name. Install it and add it to PATH."
    }
}

function Ensure-ServiceRunning($name) {
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    if (-not $service) {
        throw "Windows service not found: $name."
    }
    if ($service.Status -ne "Running") {
        Write-Host "Starting service $name ..." -ForegroundColor Yellow
        Start-Service -Name $name
        $service.WaitForStatus("Running", [TimeSpan]::FromSeconds(30))
    }
}

Assert-Command "uv"
Assert-Command "npm"

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot ".env"))) {
    throw "Missing .env. Configure the project connection settings first."
}

Ensure-ServiceRunning "MySQL80"
Ensure-ServiceRunning "Redis"

Write-Host "Syncing Python environment..." -ForegroundColor Cyan
& uv sync --all-groups --frozen
if ($LASTEXITCODE -ne 0) {
    throw "uv sync failed with exit code: $LASTEXITCODE"
}

$frontNodeModules = Join-Path $projectRoot "front\node_modules"
if (-not (Test-Path -LiteralPath $frontNodeModules)) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    & npm --prefix (Join-Path $projectRoot "front") install
    if ($LASTEXITCODE -ne 0) {
        throw "npm install failed with exit code: $LASTEXITCODE"
    }
}

Write-Host "Starting project. Start TongdaXin manually; press Ctrl+C to stop." -ForegroundColor Green
$env:PYTHONIOENCODING = "utf-8"
& uv run --frozen python app.py
exit $LASTEXITCODE
