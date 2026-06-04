param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$Python = "python",
    [string]$Date = "2026-06-03",
    [string]$PublicBaseUrl = "",
    [switch]$SkipInstall,
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

Push-Location $ProjectRoot
try {
    Write-Host "== A Stock System bootstrap =="
    Write-Host "ProjectRoot: $ProjectRoot"
    Write-Host "Python: $Python"

    if (-not (Test-Path -LiteralPath ".env")) {
        Write-Warning ".env is missing. Run scripts/configure_deepseek.ps1 before real Dify use. Bootstrap will use fixture-safe checks."
    }

    if (-not $SkipInstall) {
        & $Python -m pip install -r requirements.txt
    }

    $env:A_STOCK_USE_FIXTURE_DATA = "true"
    $tempDb = Join-Path $ProjectRoot "data/bootstrap_smoke.sqlite"
    if (Test-Path -LiteralPath $tempDb) {
        Remove-Item -LiteralPath $tempDb -Force
    }

    & $Python -m pytest -q
    & $Python scripts/validate_dify_app_spec.py
    & $Python scripts/validate_dify_workflows.py
    & $Python scripts/provision_dify_knowledge.py --dry-run
    & $Python scripts/accept_dify_app_api.py --dry-run
    & $Python scripts/audit_pdf_requirements.py
    & $Python scripts/check_dify_readiness.py --allow-missing-secrets
    & $Python main_pipeline.py --date $Date --db-path $tempDb

    if (-not $SkipSmoke) {
        $port = 8780
        $args = "api_server.py --host 127.0.0.1 --port $port --db-path `"$tempDb`""
        $proc = Start-Process -FilePath $Python -ArgumentList $args -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
        Start-Sleep -Seconds 2
        try {
            & $Python scripts/check_dify_readiness.py --allow-missing-secrets --base-url "http://127.0.0.1:$port"
            & $Python scripts/smoke_dify_tool_flow.py --base-url "http://127.0.0.1:$port" --date $Date
        } finally {
            Stop-Process -Id $proc.Id -Force
        }
    }

    if ($PublicBaseUrl) {
        & $Python scripts/export_dify_import_bundle.py --public-base-url $PublicBaseUrl
    } else {
        Write-Host "Skipping Dify import bundle generation because -PublicBaseUrl was not supplied."
    }

    Write-Host "== Bootstrap complete =="
    Write-Host "Next: deploy Python Core to HTTPS, import /openapi.yaml in Dify, bind Bearer token, upload knowledge base, then run accept_dify_app_api.py."
} finally {
    Pop-Location
}

