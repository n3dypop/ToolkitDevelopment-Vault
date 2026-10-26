[CmdletBinding()]
param(
    [ValidateSet('Check', 'RepoToWorkspace', 'WorkspaceToRepo')]
    [string]$Mode = 'Check',
    [string]$WorkspaceRoot,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$python = $null
foreach ($name in @('python', 'python3', 'py')) {
    $candidate = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $candidate) {
        & $candidate.Source -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
    }
}
if ($null -eq $python) { throw 'Python 3.11 or later is required.' }
$arguments = @((Join-Path $PSScriptRoot 'sync-agents.py'), '--mode', $Mode)
if ($WorkspaceRoot) { $arguments += @('--workspace-root', $WorkspaceRoot) }
if ($DryRun) { $arguments += '--dry-run' }
& $python.Source @arguments
if ($LASTEXITCODE -ne 0) { throw "Agent synchronization failed (exit $LASTEXITCODE)." }
