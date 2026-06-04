param(
    [Parameter(Mandatory = $true)]
    [string]$PublicBaseUrl,
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$Python = "python",
    [string]$HeadersFile = "$env:TEMP\dify_headers.txt",
    [string]$Proxy = "http://127.0.0.1:7892",
    [string]$ApiKey = "",
    [switch]$SkipConsoleVerification,
    [switch]$SkipAppApiAcceptance
)

$ErrorActionPreference = "Stop"

function Read-DotEnv {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $values
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $key, $value = $trimmed.Split("=", 2)
        $values[$key.Trim()] = $value.Trim().Trim('"').Trim("'")
    }
    return $values
}

function Assert-HttpsUrl {
    param([string]$Url)
    if ($Url -notmatch "^https://[^/\s]+") {
        throw "PublicBaseUrl must be HTTPS, for example https://your-service.example.com"
    }
    if ($Url -match "\.trycloudflare\.com/?$") {
        throw "PublicBaseUrl is still a temporary trycloudflare URL. Use a permanent HTTPS backend for production cutover."
    }
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$PublicBaseUrl = $PublicBaseUrl.TrimEnd("/")
Assert-HttpsUrl -Url $PublicBaseUrl

Push-Location $ProjectRoot
try {
    $envValues = Read-DotEnv -Path (Join-Path $ProjectRoot ".env")
    if (-not $ApiKey) {
        if ($env:A_STOCK_API_KEY) {
            $ApiKey = $env:A_STOCK_API_KEY
        } elseif ($envValues.ContainsKey("A_STOCK_API_KEY")) {
            $ApiKey = $envValues["A_STOCK_API_KEY"]
        }
    }
    if (-not $ApiKey -or $ApiKey -eq "replace-with-random-bearer-token") {
        throw "A_STOCK_API_KEY is required. Pass -ApiKey or set it in the current environment/.env."
    }
    if (-not (Test-Path -LiteralPath $HeadersFile) -and -not $SkipConsoleVerification) {
        throw "Dify headers file not found: $HeadersFile"
    }

    Write-Host "Checking deployed backend..."
    & $Python scripts/check_dify_readiness.py --base-url $PublicBaseUrl
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python scripts/smoke_dify_tool_flow.py --base-url $PublicBaseUrl --token $ApiKey --date today
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Refreshing Dify import bundle..."
    & $Python scripts/export_dify_import_bundle.py --public-base-url $PublicBaseUrl
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not $SkipConsoleVerification) {
        Write-Host "Cutting Dify Custom Tool over to permanent backend..."
        & $Python scripts/cutover_dify_public_url.py --public-base-url $PublicBaseUrl --headers-file $HeadersFile --api-key $ApiKey --proxy $Proxy --execute
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "Verifying Dify Console assets..."
        & $Python scripts/verify_dify_console_assets.py --headers-file $HeadersFile --proxy $Proxy --update-cloud-status
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    Write-Host "Running final acceptance..."
    $finalArgs = @("scripts/final_acceptance.py", "--base-url", $PublicBaseUrl, "--token", $ApiKey, "--date", "today")
    if (-not $SkipConsoleVerification) {
        $finalArgs += @("--headers-file", $HeadersFile, "--proxy", $Proxy)
    }
    if ($SkipAppApiAcceptance) {
        $finalArgs += "--skip-dify-api"
    }
    & $Python $finalArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Production cutover complete."
} finally {
    Pop-Location
}
