param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$Python = "python",
    [string]$CloudflaredPath = "",
    [string]$StateDir = "",
    [int]$Port = 8780,
    [string]$DbPath = "",
    [string]$ApiKey = "",
    [switch]$EnableHermesBridge,
    [switch]$StopExisting,
    [switch]$Http2,
    [int]$WaitSeconds = 12
)

$ErrorActionPreference = "Stop"

function New-RandomToken {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "A").Replace("/", "B")
}

function Stop-MatchingProcesses {
    param([int]$Port)
    $matches = Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -eq "python.exe" -and $_.CommandLine -match "api_server.py" -and $_.CommandLine -match "--port $Port") -or
        ($_.Name -eq "cloudflared.exe" -and $_.CommandLine -match "tunnel --url http://127.0.0.1:$Port") -or
        ($_.Name -eq "powershell.exe" -and $_.CommandLine -match "api_server.py --host 127.0.0.1 --port $Port") -or
        ($_.Name -eq "powershell.exe" -and $_.CommandLine -match "cloudflared.exe.*127.0.0.1:$Port")
    }
    foreach ($proc in $matches) {
        if ($proc.ProcessId -ne $PID) {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
if (-not $StateDir) {
    $StateDir = (Resolve-Path (Join-Path $ProjectRoot "..\..\work")).Path
}
if (-not (Test-Path -LiteralPath $StateDir)) {
    New-Item -ItemType Directory -Path $StateDir | Out-Null
}
if (-not $CloudflaredPath) {
    $CloudflaredPath = Join-Path $StateDir "cloudflared.exe"
}
if (-not (Test-Path -LiteralPath $CloudflaredPath)) {
    throw "cloudflared.exe not found: $CloudflaredPath"
}
if (-not $DbPath) {
    $DbPath = Join-Path $StateDir "dify_public_tool.sqlite"
}

$secretStatePath = Join-Path $StateDir "dify_public_endpoint_state.secret.json"
$publicStatePath = Join-Path $StateDir "dify_public_endpoint_state.json"
$oldState = $null
if (Test-Path -LiteralPath $secretStatePath) {
    try { $oldState = Get-Content -Raw -LiteralPath $secretStatePath | ConvertFrom-Json } catch { $oldState = $null }
}
if (-not $ApiKey) {
    if ($oldState -and $oldState.temporary_bearer_token) {
        $ApiKey = $oldState.temporary_bearer_token
    } else {
        $ApiKey = New-RandomToken
    }
}

if ($StopExisting) {
    Stop-MatchingProcesses -Port $Port
    Start-Sleep -Seconds 2
}

$apiOut = Join-Path $StateDir "dify_public_api.out.log"
$apiErr = Join-Path $StateDir "dify_public_api.err.log"
$tunnelOut = Join-Path $StateDir "dify_public_tunnel.out.log"
$tunnelErr = Join-Path $StateDir "dify_public_tunnel.err.log"
Clear-Content -Path $apiOut,$apiErr,$tunnelOut,$tunnelErr -ErrorAction SilentlyContinue

$bridge = if ($EnableHermesBridge) { "true" } else { "false" }
$apiCmd = @"
`$statePath = '$secretStatePath'
`$state = if (Test-Path `$statePath) { Get-Content -Raw `$statePath | ConvertFrom-Json } else { `$null }
`$env:A_STOCK_API_KEY = if (`$state -and `$state.temporary_bearer_token) { `$state.temporary_bearer_token } else { '$ApiKey' }
`$env:A_STOCK_DB_PATH = '$DbPath'
`$env:A_STOCK_ENABLE_HERMES_BRIDGE = '$bridge'
Set-Location '$ProjectRoot'
& '$Python' api_server.py --host 127.0.0.1 --port $Port --db-path '$DbPath' *> '$apiOut' 2> '$apiErr'
"@
$apiWrapper = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $apiCmd) -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 3

$protocolArgs = if ($Http2) { "--protocol http2" } else { "" }
$tunnelCmd = "& '$CloudflaredPath' tunnel --url http://127.0.0.1:$Port $protocolArgs --no-autoupdate *> '$tunnelOut' 2> '$tunnelErr'"
$tunnelWrapper = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $tunnelCmd) -WindowStyle Hidden -PassThru
Start-Sleep -Seconds $WaitSeconds

$log = Get-Content -Raw -LiteralPath $tunnelErr -ErrorAction SilentlyContinue
$publicUrl = ([regex]::Match($log, "https://[a-z0-9-]+\.trycloudflare\.com")).Value
if (-not $publicUrl) {
    throw "Could not discover trycloudflare URL. See $tunnelErr"
}

$health = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 20
$secretState = [pscustomobject]@{
    api_pid = $apiWrapper.Id
    tunnel_pid = $tunnelWrapper.Id
    public_url = $publicUrl
    temporary_bearer_token = $ApiKey
    token_env = "A_STOCK_API_KEY"
    health = $health
}
$publicState = [pscustomobject]@{
    api_pid = $apiWrapper.Id
    tunnel_pid = $tunnelWrapper.Id
    public_url = $publicUrl
    token_env = "A_STOCK_API_KEY"
    health = $health
}
$secretState | ConvertTo-Json -Depth 10 | Set-Content -Path $secretStatePath -Encoding UTF8
$publicState | ConvertTo-Json -Depth 10 | Set-Content -Path $publicStatePath -Encoding UTF8

Push-Location $ProjectRoot
try {
    & $Python scripts/export_dify_import_bundle.py --public-base-url $publicUrl | Out-Host
} finally {
    Pop-Location
}

$publicState | ConvertTo-Json -Depth 10
