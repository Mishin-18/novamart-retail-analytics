$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
docker compose up -d postgres mongodb clickhouse
if ($LASTEXITCODE -ne 0) { throw "Infrastructure startup failed (exit code $LASTEXITCODE)." }
docker compose run --rm pipeline
if ($LASTEXITCODE -ne 0) { throw "Pipeline failed (exit code $LASTEXITCODE)." }
docker compose ps
Write-Host "Tableau PostgreSQL: localhost:5433 / database novamart / schema marts"
Write-Host "ClickHouse HTTP: localhost:8124 / database analytics"
