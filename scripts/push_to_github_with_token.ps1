param(
    [string]$RemoteUrl = "https://github.com/caseroad0718-byte/A-agent.git",
    [string]$Branch = "main",
    [string]$TokenFile = "$env:TEMP\github_token.txt"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $TokenFile)) {
    throw "GitHub token file not found: $TokenFile"
}

$token = (Get-Content -LiteralPath $TokenFile -Raw).Trim()
if (-not $token) {
    throw "GitHub token file is empty: $TokenFile"
}

$askPass = Join-Path $env:TEMP ("git-askpass-" + [guid]::NewGuid().ToString("N") + ".ps1")
$askPassContent = @"
param([string]`$Prompt)
if (`$Prompt -like "*Username*") {
    Write-Output "x-access-token"
} else {
    Get-Content -LiteralPath "$TokenFile" -Raw
}
"@

try {
    Set-Content -LiteralPath $askPass -Value $askPassContent -Encoding UTF8
    git remote set-url origin $RemoteUrl
    $env:GIT_ASKPASS = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$askPass`""
    $env:GIT_TERMINAL_PROMPT = "0"
    git push -u origin $Branch
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Remove-Item Env:\GIT_ASKPASS -ErrorAction SilentlyContinue
    Remove-Item Env:\GIT_TERMINAL_PROMPT -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $askPass -Force -ErrorAction SilentlyContinue
}
