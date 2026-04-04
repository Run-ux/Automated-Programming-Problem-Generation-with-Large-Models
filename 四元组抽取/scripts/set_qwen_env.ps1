[CmdletBinding()]
param(
    [string]$ApiKey,
    [ValidateSet("DASHSCOPE_API_KEY", "QWEN_API_KEY")]
    [string]$ApiKeyName = "DASHSCOPE_API_KEY",
    [string]$ExtractModel = "qwen3.6-plus",
    [string]$NormalizeModel = "qwen3.6-plus",
    [string]$EmbeddingModel = "text-embedding-v3",
    [switch]$PersistUser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Set-EnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Value,
        [switch]$PersistUser
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }

    Set-Item -Path "Env:$Name" -Value $Value

    if ($PersistUser) {
        [System.Environment]::SetEnvironmentVariable($Name, $Value, "User")
    }
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    $ApiKey = Read-Host "Enter API key for $ApiKeyName"
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "API key is required."
}

Set-EnvValue -Name $ApiKeyName -Value $ApiKey -PersistUser:$PersistUser
Set-EnvValue -Name "QWEN_EXTRACT_MODEL" -Value $ExtractModel -PersistUser:$PersistUser
Set-EnvValue -Name "QWEN_NORMALIZE_MODEL" -Value $NormalizeModel -PersistUser:$PersistUser
Set-EnvValue -Name "QWEN_EMBEDDING_MODEL" -Value $EmbeddingModel -PersistUser:$PersistUser

Write-Host "Configured environment variables:"
Write-Host "  $ApiKeyName = <hidden>"
Write-Host "  QWEN_EXTRACT_MODEL = $env:QWEN_EXTRACT_MODEL"
Write-Host "  QWEN_NORMALIZE_MODEL = $env:QWEN_NORMALIZE_MODEL"
Write-Host "  QWEN_EMBEDDING_MODEL = $env:QWEN_EMBEDDING_MODEL"

if ($PersistUser) {
    Write-Host "User-level environment variables were updated."
    Write-Host "Open a new PowerShell window to use the persisted values."
} else {
    Write-Host "Values were written to the current PowerShell session only."
}
