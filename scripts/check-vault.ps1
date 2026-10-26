[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$errors = [System.Collections.Generic.List[string]]::new()
$markdownFiles = Get-ChildItem -LiteralPath $root -Recurse -File -Filter '*.md' |
    Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' }

foreach ($file in $markdownFiles) {
    $relative = [System.IO.Path]::GetRelativePath($root, $file.FullName)
    $content = Get-Content -LiteralPath $file.FullName -Raw
    $lines = Get-Content -LiteralPath $file.FullName

    $h1Count = 0
    $insideFence = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match '^\s*(```|~~~)') {
            $insideFence = -not $insideFence
        } elseif (-not $insideFence -and $lines[$index] -match '^# ') {
            $h1Count++
        }

        if ($lines[$index] -match '[ \t]+$') {
            $errors.Add("$relative`:$($index + 1): trailing whitespace")
        }
        if ($lines[$index] -match '(?<![A-Za-z0-9])[A-Za-z]:\\') {
            $errors.Add("$relative`:$($index + 1): absolute Windows path")
        }
    }

    $matches = [regex]::Matches($content, '!?(?<!\\)\[[^\]]*\]\((?<target>[^)]+)\)')
    foreach ($match in $matches) {
        $target = $match.Groups['target'].Value.Trim().Trim('<', '>')
        if ($target -match '^(?:https?://|mailto:|#)') {
            continue
        }

        $pathPart = ($target -split '#', 2)[0]
        if ([string]::IsNullOrWhiteSpace($pathPart)) {
            continue
        }

        $decodedPath = [System.Uri]::UnescapeDataString($pathPart)
        $resolvedTarget = Join-Path $file.DirectoryName $decodedPath
        if (-not (Test-Path -LiteralPath $resolvedTarget)) {
            $errors.Add("$relative`: broken link '$target'")
        }
    }

    if ($h1Count -ne 1) {
        $errors.Add("$relative`: expected exactly one H1, found $h1Count")
    }
}

$workspaceAgents = Join-Path (Split-Path $root -Parent) 'AGENTS.md'
$repoAgents = Join-Path $root 'AGENTS.md'
if (Test-Path -LiteralPath $workspaceAgents) {
    $workspaceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $workspaceAgents).Hash
    $repoHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $repoAgents).Hash
    if ($workspaceHash -ne $repoHash) {
        $errors.Add('AGENTS.md differs from the Toolkit workspace copy; run scripts/sync-agents.ps1 explicitly.')
    }
}

if ($errors.Count -gt 0) {
    $errors | Sort-Object -Unique | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Host "Vault check passed: $($markdownFiles.Count) Markdown files."
