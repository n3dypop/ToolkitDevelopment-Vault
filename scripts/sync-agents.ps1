[CmdletBinding()]
param(
    [ValidateSet('Check', 'RepoToWorkspace', 'WorkspaceToRepo')]
    [string]$Mode = 'Check',
    [string]$WorkspaceRoot,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).ProviderPath
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Split-Path $repoRoot -Parent
    if ((Split-Path $WorkspaceRoot -Leaf) -ine 'Toolkit') {
        throw 'Repository is not directly under Toolkit; specify -WorkspaceRoot.'
    }
}
$workspace = Get-Item -LiteralPath $WorkspaceRoot -Force
if (-not $workspace.PSIsContainer) { throw 'Workspace root must be an existing directory.' }
$workspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).ProviderPath
$pathComparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
if ([string]::Equals($repoRoot, $workspaceRoot, $pathComparison)) {
    throw 'Repository and workspace targets must be distinct.'
}
$repoAgents = Join-Path $repoRoot 'AGENTS.md'
$workspaceAgents = Join-Path $workspaceRoot 'AGENTS.md'

function Read-Agents {
    param([string]$Path, [switch]$Optional)
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -eq $item) {
        if ($Optional) { return $null }
        throw "AGENTS.md is missing: $Path"
    }
    if ($item.PSIsContainer -or $item.LinkType -or
        (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw "Expected a regular, unlinked file: $Path"
    }
    $data = [IO.File]::ReadAllBytes($Path)
    $utf8 = [Text.UTF8Encoding]::new($false, $true)
    try { $text = $utf8.GetString($data).TrimStart([char]0xFEFF) }
    catch { throw "Expected UTF-8 text: $Path" }
    if ([string]::IsNullOrWhiteSpace($text) -or $text.Contains([char]0)) {
        throw "Expected nonempty instruction text: $Path"
    }
    return ,$data
}

function Test-EqualBytes {
    param([AllowNull()][byte[]]$Left, [AllowNull()][byte[]]$Right)
    if ($null -eq $Left -or $null -eq $Right) { return $false }
    return [Convert]::ToBase64String($Left) -ceq [Convert]::ToBase64String($Right)
}

$repoBytes = Read-Agents -Path $repoAgents -Optional
$workspaceBytes = Read-Agents -Path $workspaceAgents -Optional
if ($Mode -eq 'Check') {
    if (-not (Test-EqualBytes $repoBytes $workspaceBytes)) {
        throw 'AGENTS.md is missing or out of sync; choose a direction explicitly.'
    }
    Write-Host 'AGENTS.md is synchronized (byte-identical).'
    return
}
if ($Mode -eq 'RepoToWorkspace') {
    $source = $repoAgents; $destination = $workspaceAgents
    $sourceBytes = $repoBytes; $previous = $workspaceBytes
} else {
    $source = $workspaceAgents; $destination = $repoAgents
    $sourceBytes = $workspaceBytes; $previous = $repoBytes
}
if ($null -eq $sourceBytes) { throw "AGENTS.md is missing: $source" }
if (Test-EqualBytes $sourceBytes $previous) { Write-Host "unchanged: $destination"; return }
if ($DryRun) { Write-Host "would copy: $source -> $destination"; return }

$temporary = Join-Path (Split-Path $destination -Parent) ('.AGENTS.md.sync-' + [Guid]::NewGuid().ToString('N'))
$backup = $null
try {
    $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    try { $stream.Write($sourceBytes, 0, $sourceBytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
    if (-not (Test-EqualBytes (Read-Agents -Path $source) $sourceBytes)) {
        throw 'Source changed during synchronization.'
    }
    $current = Read-Agents -Path $destination -Optional
    if ($null -eq $previous) {
        if ($null -ne $current) { throw 'Destination appeared during synchronization.' }
    } else {
        if (-not (Test-EqualBytes $current $previous)) { throw 'Destination changed during synchronization.' }
        $backup = $destination + '.sync-' + [Guid]::NewGuid().ToString('N') + '.bak'
        [IO.File]::Copy($destination, $backup, $false)
        if (-not (Test-EqualBytes ([IO.File]::ReadAllBytes($backup)) $previous)) {
            throw 'Backup verification failed.'
        }
        if (-not (Test-EqualBytes (Read-Agents -Path $destination) $previous)) {
            throw 'Destination changed during synchronization.'
        }
    }
    [IO.File]::Move($temporary, $destination, $true)
    if (-not (Test-EqualBytes ([IO.File]::ReadAllBytes($destination)) $sourceBytes)) {
        throw 'Post-write verification failed.'
    }
    Write-Host "copied: $source -> $destination"
    if ($backup) { Write-Host "backup: $backup" }
} finally {
    if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
}
