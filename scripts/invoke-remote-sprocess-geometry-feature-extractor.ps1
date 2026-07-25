param(
    [Parameter(Mandatory=$true)] [string]$HostAlias,
    [Parameter(Mandatory=$true)] [string]$RemoteWorkDir,
    [Parameter(Mandatory=$true)] [string]$GrdPath,
    [Parameter(Mandatory=$true)] [string]$TargetRegion,
    [Parameter(Mandatory=$true)] [string]$TargetMaterial,
    [Parameter(Mandatory=$true)] [double]$XMin,
    [Parameter(Mandatory=$true)] [double]$XMax,
    [Parameter(Mandatory=$true)] [double]$YMin,
    [Parameter(Mandatory=$true)] [double]$YMax,
    [string]$VertexJson = "material_vertices.json",
    [string]$VertexCsv = "material_vertices.csv",
    [string]$FeatureJson = "material_features_auto.json",
    [string]$FeatureCsv = "material_features_auto.csv"
)

$skillRoot = Split-Path -Parent $PSScriptRoot
$extractScript = Join-Path $PSScriptRoot 'extract_material_vertices.py'
$measureScript = Join-Path $PSScriptRoot 'measure_material_features.py'

if (!(Test-Path $extractScript)) { throw "Missing $extractScript" }
if (!(Test-Path $measureScript)) { throw "Missing $measureScript" }

Write-Host "[1/4] Create remote workdir: $RemoteWorkDir"
ssh $HostAlias "mkdir -p '$RemoteWorkDir'"

Write-Host "[2/4] Upload scripts"
scp $extractScript ${HostAlias}:$RemoteWorkDir/
scp $measureScript ${HostAlias}:$RemoteWorkDir/

Write-Host "[3/4] Run boundary/vertex extraction"
$extractCmd = @"
python3 '$RemoteWorkDir/extract_material_vertices.py' \
  --grd '$GrdPath' \
  --target-region '$TargetRegion' \
  --target-material '$TargetMaterial' \
  --xmin $XMin --xmax $XMax --ymin $YMin --ymax $YMax \
  --json-out '$RemoteWorkDir/$VertexJson' \
  --csv-out '$RemoteWorkDir/$VertexCsv'
"@
ssh $HostAlias $extractCmd

Write-Host "[4/4] Run automatic protrusion/recess measurement"
$measureCmd = @"
python3 '$RemoteWorkDir/measure_material_features.py' \
  --input '$RemoteWorkDir/$VertexJson' \
  --json-out '$RemoteWorkDir/$FeatureJson' \
  --csv-out '$RemoteWorkDir/$FeatureCsv'
"@
ssh $HostAlias $measureCmd

Write-Host "Done. Outputs:"
Write-Host "  vertices json:  $RemoteWorkDir/$VertexJson"
Write-Host "  vertices csv:   $RemoteWorkDir/$VertexCsv"
Write-Host "  features json:  $RemoteWorkDir/$FeatureJson"
Write-Host "  features csv:   $RemoteWorkDir/$FeatureCsv"
