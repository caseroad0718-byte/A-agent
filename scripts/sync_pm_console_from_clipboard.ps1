param(
    [string]$AppId = "ce7ea102-78f9-40c5-b489-4b562e633b60",
    [string]$Proxy = "http://127.0.0.1:7892",
    [string]$Python = "python",
    [string]$HeadersFile = "",
    [int]$WaitForFileSeconds = 0,
    [int]$WaitSeconds = 0,
    [switch]$OpenEditor,
    [switch]$NoProxy,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-FirstMatch {
    param(
        [string]$Text,
        [string[]]$Patterns
    )
    foreach ($pattern in $Patterns) {
        $match = [regex]::Match($Text, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Multiline)
        if ($match.Success -and $match.Groups.Count -gt 1) {
            return (($match.Groups[1].Value -split "\r?\n")[0]).Trim()
        }
    }
    return ""
}

function Parse-DifyHeadersText {
    param([string]$HeadersText)
    if (-not $HeadersText) {
        return @{ Cookie = ""; Csrf = ""; Error = "Header text is empty." }
    }

    $cookieValue = Get-FirstMatch -Text $HeadersText -Patterns @(
        "(?im)^\s*cookie\s*:\s*(.+)$",
        "(?im)(?:-H|--header)\s+['""]cookie\s*:\s*([^'""]+)['""]",
        "cookie\s*是\s*(.+)$"
    )
    $cookieValue = ($cookieValue -replace "\s+x-csrf-token\b.*$", "").Trim().TrimStart([char]0xFEFF)
    $csrfValue = Get-FirstMatch -Text $HeadersText -Patterns @(
        "(?im)^\s*x-csrf-token\s*:\s*(\S+)",
        "(?im)(?:-H|--header)\s+['""]x-csrf-token\s*:\s*([^'""]+)['""]",
        "x-csrf-token\s*(?:是|:)?\s*(\S+)"
    )

    if ($cookieValue -and $cookieValue -notmatch "__Host-access_token=") {
        $cookieValue = ""
    }
    $csrfValue = $csrfValue.Trim().TrimStart([char]0xFEFF)
    if ($csrfValue -eq "..." -or $csrfValue -eq "<redacted>") {
        $csrfValue = ""
    }

    if (-not $cookieValue -or -not $csrfValue) {
        $lines = @($HeadersText -split "\r?\n" | ForEach-Object { $_.Trim().TrimStart([char]0xFEFF) })
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ((-not $cookieValue) -and $lines[$i] -match "^(?i)cookie$" -and ($i + 1) -lt $lines.Count -and $lines[$i + 1] -match "__Host-access_token=") {
                $cookieValue = $lines[$i + 1].Trim()
            }
            if ((-not $csrfValue) -and $lines[$i] -match "^(?i)x-csrf-token$" -and ($i + 1) -lt $lines.Count) {
                $csrfValue = $lines[$i + 1].Trim()
            }
        }
    }
    if (-not $cookieValue) {
        foreach ($line in $HeadersText -split "\r?\n") {
            if ($line -match "__Host-access_token=") {
                $cookieValue = $line.Trim().TrimStart([char]0xFEFF)
                break
            }
        }
    }

    if (-not $cookieValue -or $cookieValue -notmatch "__Host-access_token=") {
        return @{ Cookie = ""; Csrf = ""; Error = "Could not find a valid Dify Cookie header in the clipboard." }
    }
    if (-not $csrfValue -or $csrfValue.Length -lt 20) {
        return @{ Cookie = ""; Csrf = ""; Error = "Could not find x-csrf-token in the clipboard." }
    }
    return @{ Cookie = $cookieValue; Csrf = $csrfValue; Error = "" }
}

function Read-DifyHeadersFromClipboard {
    $clipboardText = ""
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        try {
            $clipboardText = Get-Clipboard -Raw
            break
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $clipboardText) {
        return @{ Cookie = ""; Csrf = ""; Error = "Clipboard is empty." }
    }
    return Parse-DifyHeadersText -HeadersText $clipboardText
}

$headersFromFile = ""
if ($HeadersFile) {
    if ($OpenEditor -and -not (Test-Path -LiteralPath $HeadersFile)) {
        @"
Paste the full Dify Request Headers here, then save and close.
Required: cookie and x-csrf-token.
"@ | Set-Content -Encoding UTF8 -LiteralPath $HeadersFile
    }
    if ($OpenEditor) {
        Start-Process notepad.exe -ArgumentList $HeadersFile
    }
    $fileDeadline = (Get-Date).AddSeconds([Math]::Max(0, $WaitForFileSeconds))
    while ((-not (Test-Path -LiteralPath $HeadersFile)) -and $WaitForFileSeconds -gt 0 -and (Get-Date) -lt $fileDeadline) {
        Write-Host "Waiting for headers file to be created..."
        Start-Sleep -Seconds 2
    }
    if (-not (Test-Path -LiteralPath $HeadersFile)) {
        throw "Headers file not found: $HeadersFile"
    }
    $headersFromFile = Get-Content -Raw -LiteralPath $HeadersFile
    $parsedFileHeaders = Parse-DifyHeadersText -HeadersText $headersFromFile
    while ($parsedFileHeaders.Error -and $WaitForFileSeconds -gt 0 -and (Get-Date) -lt $fileDeadline) {
        Write-Host "Waiting for valid Dify request headers in file..."
        Start-Sleep -Seconds 2
        $headersFromFile = Get-Content -Raw -LiteralPath $HeadersFile
        $parsedFileHeaders = Parse-DifyHeadersText -HeadersText $headersFromFile
    }
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

$deadline = (Get-Date).AddSeconds([Math]::Max(0, $WaitSeconds))
$headers = if ($HeadersFile) { Parse-DifyHeadersText -HeadersText $headersFromFile } else { Read-DifyHeadersFromClipboard }
while ((-not $HeadersFile) -and $headers.Error -and $WaitSeconds -gt 0 -and (Get-Date) -lt $deadline) {
    Write-Host "Waiting for Dify request headers in clipboard..."
    Start-Sleep -Seconds 2
    $headers = Read-DifyHeadersFromClipboard
}
if ($headers.Error) {
    if ($HeadersFile) {
        throw ("Could not parse valid Dify request headers from file: " + $HeadersFile + ". " + $headers.Error)
    }
    throw $headers.Error
}

$oldCookie = [Environment]::GetEnvironmentVariable("DIFY_CONSOLE_COOKIE", "Process")
$oldCsrf = [Environment]::GetEnvironmentVariable("DIFY_CONSOLE_CSRF_TOKEN", "Process")
$oldProxy = [Environment]::GetEnvironmentVariable("DIFY_CONSOLE_PROXY", "Process")

try {
    $env:DIFY_CONSOLE_COOKIE = $headers.Cookie
    $env:DIFY_CONSOLE_CSRF_TOKEN = $headers.Csrf
    if (-not $NoProxy) {
        $env:DIFY_CONSOLE_PROXY = $Proxy
    }

    if ($DryRun) {
        Write-Host "Dry run: clipboard headers parsed. No Dify request will be sent."
        & $Python scripts/install_dify_cloud_assets.py --sync-pm-console-id $AppId
    }
    else {
        Write-Host "Syncing PM Console draft and publishing. Secrets are held only in this process."
        & $Python scripts/install_dify_cloud_assets.py --sync-pm-console-id $AppId --execute
    }
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    if ($null -eq $oldCookie) { Remove-Item Env:DIFY_CONSOLE_COOKIE -ErrorAction SilentlyContinue } else { $env:DIFY_CONSOLE_COOKIE = $oldCookie }
    if ($null -eq $oldCsrf) { Remove-Item Env:DIFY_CONSOLE_CSRF_TOKEN -ErrorAction SilentlyContinue } else { $env:DIFY_CONSOLE_CSRF_TOKEN = $oldCsrf }
    if ($null -eq $oldProxy) { Remove-Item Env:DIFY_CONSOLE_PROXY -ErrorAction SilentlyContinue } else { $env:DIFY_CONSOLE_PROXY = $oldProxy }
}
