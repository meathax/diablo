param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SourceDirectory,

    [Parameter(Position = 1)]
    [ValidateSet('sync', 'compile', 'compress', 'timing')]
    [string]$Action = 'compile',

    [string]$QuartusRoot,

    [string]$RepositoryDirectory
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($QuartusRoot)) {
    $QuartusRoot = $env:DIABLO_QUARTUS_ROOT
}
if ([string]::IsNullOrWhiteSpace($QuartusRoot)) {
    $QuartusRoot = 'D:/Q17/quartus'
}

$scriptRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
if ([string]::IsNullOrWhiteSpace($RepositoryDirectory)) {
    $RepositoryDirectory = (Resolve-Path -LiteralPath (Join-Path $scriptRoot '../..')).Path
} else {
    $RepositoryDirectory = (Resolve-Path -LiteralPath $RepositoryDirectory).Path
}

if (-not (Test-Path -LiteralPath $SourceDirectory -PathType Container)) {
    throw "Source directory does not exist: $SourceDirectory"
}
$SourceDirectory = (Resolve-Path -LiteralPath $SourceDirectory).Path

$snapshotInputs = @(
    'Diablo.sv',
    'Diablo.qpf',
    'Diablo.qsf',
    'Diablo.sdc',
    'Diablo.srf',
    'files.qip',
    'build_id.v',
    'LICENSE.fpga',
    'rtl',
    'sys',
    'support/scripts/report_fpga_timing.tcl'
)
$manifestRelativePath = '.mister/fpga-source-snapshot.json'
$manifestPath = Join-Path $SourceDirectory $manifestRelativePath

function Get-RelativePath([string]$Base, [string]$Path) {
    $baseUri = [System.Uri]::new(($Base.TrimEnd('\') + '\'))
    $pathUri = [System.Uri]::new($Path)
    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pathUri).ToString()).Replace('/', '\')
}

function Get-SnapshotFiles([string]$Root, [string[]]$Inputs) {
    $files = [System.Collections.Generic.List[object]]::new()
    foreach ($input in $Inputs) {
        $path = Join-Path $Root $input
        if (-not (Test-Path -LiteralPath $path)) {
            throw "Required snapshot input is missing: $input"
        }
        $item = Get-Item -LiteralPath $path -Force
        if ($item.PSIsContainer) {
            $children = Get-ChildItem -LiteralPath $path -Recurse -File -Force | Sort-Object FullName
            foreach ($child in $children) {
                $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $child.FullName).Hash.ToLowerInvariant()
                $files.Add([ordered]@{
                        path = (Get-RelativePath $Root $child.FullName).Replace('\', '/')
                        bytes = [int64]$child.Length
                        sha256 = $hash
                    })
            }
        } else {
            $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $item.FullName).Hash.ToLowerInvariant()
            $files.Add([ordered]@{
                    path = (Get-RelativePath $Root $item.FullName).Replace('\', '/')
                    bytes = [int64]$item.Length
                    sha256 = $hash
                })
        }
    }
    $paths = @($files | ForEach-Object { $_['path'] })
    if ($paths.Count -ne (@($paths | Sort-Object -Unique)).Count) {
        throw 'Snapshot input list contains duplicate files'
    }
    return @($files | Sort-Object { $_['path'] })
}

function Assert-EmptySnapshot([string]$Path) {
    $existing = @(Get-ChildItem -LiteralPath $Path -Force)
    if ($existing.Count -ne 0) {
        $names = ($existing | Select-Object -First 8 -ExpandProperty Name) -join ', '
        throw "Refusing to merge into a non-empty snapshot: $Path ($names). Use a new empty build-ID directory."
    }
}

function Copy-SnapshotInputs([string]$Repository, [string]$Destination, [string[]]$Inputs) {
    foreach ($input in $Inputs) {
        $source = Join-Path $Repository $input
        if (-not (Test-Path -LiteralPath $source)) {
            throw "Required repository input is missing: $input"
        }
        $sourceItem = Get-Item -LiteralPath $source -Force
        $destinationPath = Join-Path $Destination $input
        if ($sourceItem.PSIsContainer) {
            New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null
            Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $destinationPath -Recurse -Force
        } else {
            $parent = Split-Path -Parent $destinationPath
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
            Copy-Item -LiteralPath $source -Destination $destinationPath -Force
        }
    }
}

function Write-SnapshotManifest([string]$Repository, [string]$Destination, [string[]]$Inputs) {
    $files = Get-SnapshotFiles $Destination $Inputs
    $manifestDirectory = Split-Path -Parent (Join-Path $Destination $manifestRelativePath)
    New-Item -ItemType Directory -Path $manifestDirectory -Force | Out-Null
    $manifest = [ordered]@{
        schema = 'diablo-fpga-source-snapshot-v1'
        created_utc = (Get-Date).ToUniversalTime().ToString('o')
        source_inputs = @($Inputs)
        files = $files
        source_repository = '.'
        tool_contract = 'Quartus executables are selected from -QuartusRoot or DIABLO_QUARTUS_ROOT; no project-local wrapper is required.'
    }
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Destination $manifestRelativePath) -Encoding UTF8
}

function Assert-SnapshotManifest([string]$Destination, [string[]]$Inputs) {
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "Snapshot manifest is missing: $manifestPath. Run -Action sync into a new empty directory first."
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema -ne 'diablo-fpga-source-snapshot-v1') {
        throw "Unsupported FPGA snapshot manifest schema: $($manifest.schema)"
    }
    $expected = @(Get-SnapshotFiles $Destination $Inputs)
    $expectedLines = @($expected | ForEach-Object {
            "$($_['path'])|$([int64]$($_['bytes']))|$($_['sha256'])"
        } | Sort-Object)
    $actualLines = @($manifest.files | ForEach-Object {
            "$($_.path)|$([int64]$_.bytes)|$($_.sha256)"
        } | Sort-Object)
    if (($expectedLines -join "`n") -cne ($actualLines -join "`n")) {
        throw "Snapshot files no longer match the recorded manifest: $manifestPath"
    }
}

function Invoke-Quartus([string]$Executable, [string[]]$Arguments, [string]$LogName) {
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "Configured Quartus executable is missing: $Executable"
    }
    $logDirectory = Join-Path $SourceDirectory '.mister/logs'
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $log = Join-Path $logDirectory $LogName
    & $Executable @Arguments *> $log
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        $tail = (Get-Content -LiteralPath $log -Tail 40 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
        throw "Quartus action failed with exit code $exitCode. Log: $log`n$tail"
    }
    Write-Output ([ordered]@{ executable = $Executable; arguments = $Arguments; log = $log; exit_code = $exitCode } | ConvertTo-Json -Compress)
}

if ($Action -eq 'sync') {
    Assert-EmptySnapshot $SourceDirectory
    Copy-SnapshotInputs $RepositoryDirectory $SourceDirectory $snapshotInputs
    Write-SnapshotManifest $RepositoryDirectory $SourceDirectory $snapshotInputs
    Write-Output "FPGA source snapshot created: $SourceDirectory"
    Write-Output "Manifest: $(Join-Path $SourceDirectory $manifestRelativePath)"
    exit 0
}

Assert-SnapshotManifest $SourceDirectory $snapshotInputs
if (-not (Test-Path -LiteralPath $QuartusRoot -PathType Container)) {
    throw "Configured Quartus root does not exist: $QuartusRoot"
}
$quartusRootResolved = (Resolve-Path -LiteralPath $QuartusRoot).Path
$quartusSh = Join-Path $quartusRootResolved 'bin64/quartus_sh.exe'
$quartusSta = Join-Path $quartusRootResolved 'bin64/quartus_sta.exe'
$quartusCpf = Join-Path $quartusRootResolved 'bin64/quartus_cpf.exe'

Push-Location -LiteralPath $SourceDirectory
try {
    if ($Action -eq 'compile') {
        Invoke-Quartus $quartusSh @('--flow', 'compile', 'Diablo') 'quartus-compile.log'
    } elseif ($Action -eq 'timing') {
        $timingScript = Join-Path $SourceDirectory 'support/scripts/report_fpga_timing.tcl'
        Invoke-Quartus $quartusSta @('-t', $timingScript, 'Diablo') 'quartus-timing.log'
    } elseif ($Action -eq 'compress') {
        Invoke-Quartus $quartusCpf @('-c', '-o', 'bitstream_compression=on',
            'output_files/Diablo.sof', 'output_files/Diablo.compressed.rbf') 'quartus-compress.log'
    }
} finally {
    Pop-Location
}
