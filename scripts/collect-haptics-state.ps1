# Keep the sibling .sh file beside this script. Requires adb on PATH.
param([string]$Serial = '')
$ErrorActionPreference = 'Stop'
$adbArgs = @()
if ($Serial) { $adbArgs = @('-s', $Serial) }
$state = & adb @adbArgs get-state 2>&1
if ($LASTEXITCODE -ne 0 -or (($state -join "`n").Trim() -ne 'device')) {
    throw "ADB is not connected to one recovery device: $state"
}
$collector = Join-Path $PSScriptRoot 'collect-haptics-state.sh'
if (-not (Test-Path -LiteralPath $collector)) { throw "Missing $collector" }
$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $PID
$remote = '/tmp/dijun-haptics-state-' + $stamp
$dest = Join-Path (Get-Location) ('dijun-haptics-state-' + $stamp)
New-Item -ItemType Directory -Path $dest | Out-Null
& adb @adbArgs push $collector ($remote + '.sh')
if ($LASTEXITCODE -ne 0) { throw 'Could not push collector.' }
Write-Host 'Collecting existing haptics state; no playback or calibration. DSP reads may wake it.'
& adb @adbArgs shell sh ($remote + '.sh') $remote
$collectionExit = $LASTEXITCODE
& adb @adbArgs pull $remote $dest
if ($LASTEXITCODE -ne 0) { throw 'Could not pull collection; inspect the ADB error above.' }
Compress-Archive -Path (Join-Path $dest '*') -DestinationPath ($dest + '.zip')
Write-Host ('Saved: ' + $dest + '.zip')
if ($collectionExit -ne 0) {
    Write-Warning "Collection exited $collectionExit; partial results are preserved. Check commands.tsv and READ_EXIT."
}
