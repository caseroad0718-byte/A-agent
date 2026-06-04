param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$ApiKey = "",
    [string]$StrongModel = "deepseek-v4-pro",
    [string]$FastModel = "deepseek-v4-flash",
    [string]$BaseUrl = "https://api.deepseek.com",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$envPath = Join-Path $ProjectRoot ".env"
$examplePath = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path -LiteralPath $examplePath)) {
    throw ".env.example not found at $examplePath"
}

if (-not $ApiKey) {
    $secure = Read-Host "Paste DEEPSEEK_API_KEY" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

if (-not $ApiKey.StartsWith("sk-")) {
    Write-Warning "The supplied key does not start with sk-. Continuing because some gateways use different prefixes."
}

if ((Test-Path -LiteralPath $envPath) -and -not $Force) {
    throw ".env already exists. Re-run with -Force to update it."
}

$apiTokenBytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($apiTokenBytes)
$apiToken = [Convert]::ToBase64String($apiTokenBytes).Replace("+", "").Replace("/", "").Replace("=", "")

$content = @(
    "# Local secrets. Do not commit or paste this file into Dify prompts.",
    "A_STOCK_API_KEY=$apiToken",
    "DEEPSEEK_API_KEY=$ApiKey",
    "DEEPSEEK_BASE_URL=$BaseUrl",
    "DEEPSEEK_MODEL_STRONG=$StrongModel",
    "DEEPSEEK_MODEL_FAST=$FastModel",
    "DEEPSEEK_MODEL=$StrongModel",
    "TUSHARE_TOKEN=",
    "SERVERCHAN_SENDKEY=",
    "TELEGRAM_BOT_TOKEN=",
    "TELEGRAM_CHAT_ID=",
    "A_STOCK_DB_PATH=data/a_stock_system.sqlite",
    "A_STOCK_TRADING_ENABLED=false",
    "A_STOCK_USE_FIXTURE_DATA=false"
)

Set-Content -LiteralPath $envPath -Value $content -Encoding UTF8
Write-Host "Configured $envPath"
Write-Host "Use A_STOCK_API_KEY from .env as the Dify Custom Tool Bearer token."
