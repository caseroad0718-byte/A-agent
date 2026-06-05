param(
    [string]$RepoUrl = "https://github.com/caseroad0718-byte/A-agent",
    [string]$Branch = "main",
    [string]$ServiceName = "a-stock-system",
    [string]$OwnerId = "",
    [string]$RenderTokenFile = "$env:TEMP\render_token.txt",
    [string]$AStockApiKeyFile = "$env:TEMP\a_stock_api_key.txt",
    [string]$DeepSeekApiKeyFile = "$env:TEMP\deepseek_api_key.txt",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Read-SecretFile {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        return (Get-Content -LiteralPath $Path -Raw).Trim()
    }
    return ""
}

function New-RandomBearer {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

$renderToken = Read-SecretFile -Path $RenderTokenFile
if (-not $renderToken) {
    throw "Render token file not found or empty: $RenderTokenFile"
}

$headers = @{
    Authorization = "Bearer $renderToken"
    "Content-Type" = "application/json"
    Accept = "application/json"
}

if (-not $OwnerId) {
    $owners = Invoke-RestMethod -Method Get -Uri "https://api.render.com/v1/owners" -Headers $headers
    $firstOwner = @($owners)[0]
    if ($firstOwner.owner.id) {
        $OwnerId = $firstOwner.owner.id
    } elseif ($firstOwner.id) {
        $OwnerId = $firstOwner.id
    }
}
if (-not $OwnerId) {
    throw "Could not determine Render owner id. Pass -OwnerId explicitly."
}

$aStockApiKey = Read-SecretFile -Path $AStockApiKeyFile
if (-not $aStockApiKey) {
    $aStockApiKey = New-RandomBearer
    Set-Content -LiteralPath $AStockApiKeyFile -Value $aStockApiKey -Encoding ASCII
    Write-Host "Generated A_STOCK_API_KEY and saved it to $AStockApiKeyFile"
}

$envVars = @(
    @{ key = "A_STOCK_TRADING_ENABLED"; value = "false" },
    @{ key = "A_STOCK_USE_FIXTURE_DATA"; value = "false" },
    @{ key = "DEEPSEEK_BASE_URL"; value = "https://api.deepseek.com" },
    @{ key = "DEEPSEEK_MODEL"; value = "deepseek-v4-pro" },
    @{ key = "DEEPSEEK_MODEL_STRONG"; value = "deepseek-v4-pro" },
    @{ key = "DEEPSEEK_MODEL_FAST"; value = "deepseek-v4-flash" },
    @{ key = "A_STOCK_API_KEY"; value = $aStockApiKey }
)

$deepSeekApiKey = Read-SecretFile -Path $DeepSeekApiKeyFile
if ($deepSeekApiKey) {
    $envVars += @{ key = "DEEPSEEK_API_KEY"; value = $deepSeekApiKey }
}

$body = @{
    type = "web_service"
    name = $ServiceName
    ownerId = $OwnerId
    repo = $RepoUrl
    branch = $Branch
    serviceDetails = @{
        runtime = "python"
        plan = "starter"
        region = "oregon"
        buildCommand = "pip install -r requirements.txt"
        startCommand = "python api_server.py --host 0.0.0.0 --port `$PORT"
        autoDeploy = "yes"
        env = "python"
        envVars = $envVars
    }
} | ConvertTo-Json -Depth 10

if ($DryRun) {
    $body
    exit 0
}

$service = Invoke-RestMethod -Method Post -Uri "https://api.render.com/v1/services" -Headers $headers -Body $body
$service | ConvertTo-Json -Depth 10
