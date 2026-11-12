# PowerShell 5.1 or newer. This only reads an already-connected recovery.
param([string]$Serial = '', [string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
if ($Serial -and $Serial -notmatch '^[A-Za-z0-9_.:-]+$') { throw 'Unsupported ADB serial characters.' }
$adb = (Get-Command adb -ErrorAction Stop).Source
$collector = Join-Path $PSScriptRoot 'collect-refresh-state.sh'
if (-not (Test-Path -LiteralPath $collector)) { throw "Missing sibling script: $collector" }
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path (Get-Location) ('refresh-stuck-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $PID)
}
$dest = (New-Item -ItemType Directory -Force -Path $OutputDirectory).FullName
$utf8 = New-Object System.Text.UTF8Encoding($false)
$records = New-Object System.Collections.Generic.List[string]
$records.Add("file`tstatus`texit_code")
function Save-AdbText([string]$Name, [string]$Script, [int]$TimeoutSeconds = 15) {
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $adb
    # Arguments are fixed tokens plus the validated serial; shell content goes via stdin.
    $info.Arguments = $(if ($Serial) { '-s ' + $Serial + ' ' } else { '' }) + 'shell sh'
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    $status = 'error'
    $exitCode = ''
    try {
        [void]$process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.Write($Script.Replace("`r", '') + "`n")
        $process.StandardInput.Close()
        if ($process.WaitForExit($TimeoutSeconds * 1000)) {
            $status = 'complete'
            $exitCode = [string]$process.ExitCode
        } else {
            $status = 'host-timeout'
            # Kill only this local adb client; never kill recovery or a device task.
            $process.Kill()
            [void]$process.WaitForExit(2000)
        }
        if ($stdout.Wait(2000)) { [System.IO.File]::WriteAllText((Join-Path $dest $Name), $stdout.Result, $utf8) }
        if ($stderr.Wait(2000)) { [System.IO.File]::WriteAllText((Join-Path $dest ($Name + '.stderr.txt')), $stderr.Result, $utf8) }
    } catch {
        [System.IO.File]::WriteAllText((Join-Path $dest ($Name + '.error.txt')), [string]$_, $utf8)
    } finally {
        $records.Add("$Name`t$status`t$exitCode")
        [System.IO.File]::WriteAllLines((Join-Path $dest 'capture-status.tsv'), $records, $utf8)
        $process.Dispose()
    }
    Write-Host ($Name + ': ' + $status)
}
Save-AdbText 'recovery.log' 'cat /tmp/recovery.log'
Save-AdbText 'recovery-stacks-before.txt' ([System.IO.File]::ReadAllText($collector)) 30
Save-AdbText 'logcat.txt' 'logcat -b all -d -t 3000'
Save-AdbText 'dmesg.txt' 'dmesg'
Save-AdbText 'properties.txt' 'getprop'
Save-AdbText 'recovery-stacks-after.txt' ([System.IO.File]::ReadAllText($collector)) 30
Save-AdbText 'recovery-after.log' 'cat /tmp/recovery.log'
try {
    Compress-Archive -Path (Join-Path $dest '*') -DestinationPath ($dest + '.zip') -Force
    Write-Host ('Saved archive: ' + $dest + '.zip')
} catch {
    Write-Warning ('Archive failed; keep the directory: ' + $dest)
}
Write-Host ('Saved directory: ' + $dest)
