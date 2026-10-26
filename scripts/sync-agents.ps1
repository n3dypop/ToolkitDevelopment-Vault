[CmdletBinding()]
param(
    [ValidateSet('Check', 'RepoToWorkspace', 'WorkspaceToRepo')]
    [string]$Mode = 'Check',

    [string]$WorkspaceRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repoAgents = Join-Path $repoRoot 'AGENTS.md'

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $candidate = Split-Path $repoRoot -Parent
    if ((Split-Path $candidate -Leaf) -ne 'Toolkit') {
        throw 'The repository is not directly under Toolkit. Specify -WorkspaceRoot explicitly.'
    }
    $WorkspaceRoot = $candidate
}

$resolvedWorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
$workspaceAgents = Join-Path $resolvedWorkspaceRoot 'AGENTS.md'

function Get-AgentsHash {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "AGENTS.md is missing: $Path"
    }

    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

switch ($Mode) {
    'RepoToWorkspace' {
        Get-AgentsHash -Path $repoAgents | Out-Null
        Copy-Item -LiteralPath $repoAgents -Destination $workspaceAgents -Force
    }
    'WorkspaceToRepo' {
        Get-AgentsHash -Path $workspaceAgents | Out-Null
        Copy-Item -LiteralPath $workspaceAgents -Destination $repoAgents -Force
    }
}

$repoHash = Get-AgentsHash -Path $repoAgents
$workspaceHash = Get-AgentsHash -Path $workspaceAgents

if ($repoHash -ne $workspaceHash) {
    throw "AGENTS.md is out of sync. Repo=$repoHash Workspace=$workspaceHash"
}

Write-Host "AGENTS.md is synchronized: $repoHash"
