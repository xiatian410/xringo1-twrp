# Keep the sibling .sh beside this file. Run while recovery is already in ADB.
param([string]$Serial = '')
$ErrorActionPreference = 'Stop'
$adbArgs = @()
if ($Serial) { $adbArgs = @('-s', $Serial) }
$state = & adb @adbArgs get-state 2>&1
if ($LASTEXITCODE -ne 0 -or (($state -join "`n").Trim() -ne 'device')) {
    throw "Recovery ADB is not connected: $state"
}
$collector = Join-Path $PSScriptRoot 'collect-settings-state.sh'
if (-not (Test-Path -LiteralPath $collector)) { throw "Missing $collector" }
$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $PID
$remote = '/tmp/dijun-settings-' + $stamp
$dest = Join-Path (Get-Location) ('dijun-settings-' + $stamp)
New-Item -ItemType Directory -Path $dest | Out-Null
& adb @adbArgs push $collector ($remote + '.sh')
if ($LASTEXITCODE -ne 0) { throw 'Could not push collector.' }
function Save-Snapshot([string]$Phase) {
    & adb @adbArgs shell sh ($remote + '.sh') ($remote + '-' + $Phase)
    $snapshotExit = $LASTEXITCODE
    & adb @adbArgs pull ($remote + '-' + $Phase) $dest
    if ($LASTEXITCODE -ne 0) { throw "Could not pull $Phase snapshot." }
    if ($snapshotExit -ne 0) {
        Write-Warning "$Phase snapshot is partial; commands.tsv preserves individual failures."
    }
}
Save-Snapshot 'before'
Write-Host 'In recovery Settings > General, tap the checkbox for Swap navigation once.'
Write-Host 'Observe: no response, changes then reverts, or stays changed. Avoid wipe/install options.'
$observation = Read-Host 'Enter what happened, then press Enter to capture the after snapshot'
Set-Content -LiteralPath (Join-Path $dest 'observation.txt') -Value $observation -Encoding UTF8
Save-Snapshot 'after'
Compress-Archive -Path (Join-Path $dest '*') -DestinationPath ($dest + '.zip')
Write-Host ('Saved: ' + $dest + '.zip')
