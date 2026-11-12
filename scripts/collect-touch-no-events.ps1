# Run in Windows PowerShell with adb on PATH and the sibling .sh file present.
# Optional: -Serial DEVICE_SERIAL when more than one ADB device is connected.
param([string]$Serial = '')
$ErrorActionPreference = 'Stop'
$adbArgs = @()
if ($Serial) { $adbArgs = @('-s', $Serial) }
$state = & adb @adbArgs get-state 2>&1
if ($LASTEXITCODE -ne 0 -or (($state -join "`n").Trim() -ne 'device')) {
    throw "ADB is not connected to one recovery device: $state"
}
$collector = Join-Path $PSScriptRoot 'collect-touch-no-events.sh'
if (-not (Test-Path -LiteralPath $collector)) { throw "Missing $collector" }
$dest = Join-Path (Get-Location) ('os4-touch-directed-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $dest | Out-Null
& adb @adbArgs push $collector /tmp/dijun-collect-touch.sh
if ($LASTEXITCODE -ne 0) { throw 'Could not push collector.' }
Write-Host 'Keep recovery visible. Wait for TOUCH, then swipe continuously for 12 seconds.'
& adb @adbArgs shell sh /tmp/dijun-collect-touch.sh
$collectionExit = $LASTEXITCODE
& adb @adbArgs pull /tmp/dijun-touch-no-events $dest
if ($LASTEXITCODE -ne 0) { throw 'Could not pull collected logs.' }
Compress-Archive -Path (Join-Path $dest '*') -DestinationPath ($dest + '.zip')
Write-Host ('Saved: ' + $dest + '.zip')
if ($collectionExit -ne 0) {
    Write-Warning "Collector exited $collectionExit; the archive may contain partial logs."
}
