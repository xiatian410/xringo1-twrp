# Keep shell syntax in a pushed file to avoid Windows native argument quoting.
param([string]$Serial = '')
$ErrorActionPreference = 'Stop'
$adbArgs = @()
if ($Serial) { $adbArgs = @('-s', $Serial) }
$state = & adb @adbArgs get-state 2>&1
if ($LASTEXITCODE -ne 0 -or (($state -join "`n").Trim() -ne 'device')) {
    throw "ADB is not connected to one recovery device: $state"
}
$script = Join-Path $PSScriptRoot 'collect-touch-v1-debug.sh'
if (-not (Test-Path -LiteralPath $script)) { throw "Missing $script" }
$dest = Join-Path (Get-Location) ('os4-touch-v1-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $dest | Out-Null
& adb @adbArgs push $script /tmp/collect-touch-v1-debug.sh
if ($LASTEXITCODE -ne 0) { throw 'Could not push collector.' }
Write-Host 'Temporarily enables vendor debug logging. Swipe when SWIPE NOW appears.'
& adb @adbArgs shell sh /tmp/collect-touch-v1-debug.sh
$collectionExit = $LASTEXITCODE
& adb @adbArgs pull /tmp/dijun-touch-v1-debug $dest
if ($LASTEXITCODE -ne 0) { throw 'Could not pull collected files.' }
Compress-Archive -Path (Join-Path $dest '*') -DestinationPath ($dest + '.zip')
Write-Host ('Saved: ' + $dest + '.zip')
if ($collectionExit -ne 0) {
    Write-Warning "Collector exited $collectionExit; inspect partial logs and original log-level restoration."
}
