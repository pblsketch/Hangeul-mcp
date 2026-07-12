[CmdletBinding()]
param(
    [string[]]$Features = @(),
    [ValidateSet('claude', 'codex', 'antigravity', 'all')]
    [string]$Client = 'all',
    [string]$Version,
    [switch]$NonInteractive,
    [switch]$AllowWingetPythonInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$ArgumentList = @(),
        [switch]$AllowFailure,
        [switch]$PassThru
    )

    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = $FilePath
    foreach ($argument in $ArgumentList) {
        [void]$processInfo.ArgumentList.Add($argument)
    }
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $processInfo
    [void]$process.Start()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    if (-not $AllowFailure -and $process.ExitCode -ne 0) {
        $message = "Command failed: $FilePath (exit $($process.ExitCode))"
        if ($stderr) {
            $message = "$message`n$stderr"
        }
        throw $message
    }

    if ($PassThru) {
        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            StdOut = $stdout
            StdErr = $stderr
        }
    }

    return $stdout
}

function Get-PythonCommand {
    $probes = @(
        @{ FilePath = 'py'; Arguments = @('-3.13', '-c', 'import sys; print(sys.executable)') },
        @{ FilePath = 'py'; Arguments = @('-3.12', '-c', 'import sys; print(sys.executable)') },
        @{ FilePath = 'py'; Arguments = @('-3.11', '-c', 'import sys; print(sys.executable)') },
        @{ FilePath = 'py'; Arguments = @('-3.10', '-c', 'import sys; print(sys.executable)') },
        @{ FilePath = 'python'; Arguments = @('-c', 'import sys; print(sys.executable)') },
        @{ FilePath = 'python3'; Arguments = @('-c', 'import sys; print(sys.executable)') }
    )

    foreach ($probe in $probes) {
        try {
            $result = Invoke-CheckedCommand -FilePath $probe.FilePath -ArgumentList $probe.Arguments -PassThru -AllowFailure
            if ($result.ExitCode -ne 0) {
                continue
            }
            $pythonExe = $result.StdOut.Trim()
            if (-not $pythonExe) {
                continue
            }
            $versionOutput = Invoke-CheckedCommand -FilePath $pythonExe -ArgumentList @('-c', 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
            $versionText = $versionOutput.Trim()
            if ([version]$versionText -ge [version]'3.10') {
                return $pythonExe
            }
        }
        catch {
            continue
        }
    }

    return $null
}

function Ensure-PythonPresent {
    param([string]$PythonCommand)

    if (-not $PythonCommand) {
        Write-Error 'Python 3.10 or newer is required.'
        Write-Host 'Install Python from the official downloads page:'
        Write-Host '  https://www.python.org/downloads/windows/'
        Write-Host 'After installation, reopen PowerShell and re-run this installer.'
        Write-Host 'Optional winget command (explicit opt-in only):'
        Write-Host '  winget install --id Python.Python.3.12 -e'
        if ($AllowWingetPythonInstall) {
            Invoke-CheckedCommand -FilePath 'winget' -ArgumentList @('install', '--id', 'Python.Python.3.12', '-e') | Out-Null
            $script:PythonCommand = Get-PythonCommand
            if (-not $script:PythonCommand) {
                throw 'winget install completed without a usable Python 3.10+ command.'
            }
            return
        }
        throw 'Python 3.10 or newer was not found. Re-run with -AllowWingetPythonInstall to use winget explicitly.'
    }
}

function Get-ManagedRoot {
    if ($env:APPDATA) {
        return (Join-Path $env:APPDATA 'hangeul-mcp')
    }
    if ($env:LOCALAPPDATA) {
        return (Join-Path $env:LOCALAPPDATA 'hangeul-mcp')
    }
    return (Join-Path $HOME 'AppData\Roaming\hangeul-mcp')
}

function Get-ExtrasSuffix {
    if ($Features.Count -eq 0) {
        return ''
    }
    $clean = $Features | Where-Object { $_ } | ForEach-Object { $_.Trim() }
    if ($clean.Count -eq 0) {
        return ''
    }
    return '[' + ($clean -join ',') + ']'
}

function Get-LocalSourceRoot {
    $candidates = @(
        $PSScriptRoot,
        (Split-Path -Parent $PSScriptRoot)
    )
    foreach ($candidate in $candidates) {
        if ((Test-Path (Join-Path $candidate 'pyproject.toml')) -and (Test-Path (Join-Path $candidate 'hangeul_mcp'))) {
            return $candidate
        }
    }
    return $null
}

function Get-SourcePackageSpec {
    param([string]$ExtrasSuffix)

    $localRoot = Get-LocalSourceRoot
    if ($localRoot) {
        return "$localRoot$ExtrasSuffix"
    }
    if ($ExtrasSuffix) {
        return "hangeul-mcp$ExtrasSuffix @ git+https://github.com/pblsketch/Hangeul-mcp.git"
    }
    return 'git+https://github.com/pblsketch/Hangeul-mcp.git'
}

function Get-VersionedPackageSpec {
    param(
        [string]$ExtrasSuffix,
        [string]$PinnedVersion
    )

    return "hangeul-mcp$ExtrasSuffix==$PinnedVersion"
}

function New-CommandShim {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$BasePython,
        [Parameter(Mandatory = $true)]
        [string]$ModuleName
    )

    $content = @"
@echo off
"$BasePython" -m $ModuleName %*
"@
    Set-Content -Path $Path -Value $content -Encoding ASCII
}

function Ensure-UserPathContains {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $currentUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @()
    if ($currentUserPath) {
        $entries = $currentUserPath.Split(';') | Where-Object { $_ }
    }
    if ($entries -contains $Directory) {
        return
    }
    $updated = @($entries + $Directory) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $updated, 'User')
}

function Write-Utf8NoBomText {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )

    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

$pythonCommand = Get-PythonCommand
Ensure-PythonPresent -PythonCommand $pythonCommand
$pythonCommand = if ($script:PythonCommand) { $script:PythonCommand } else { $pythonCommand }

$managedRoot = Get-ManagedRoot
$baseRoot = Join-Path $managedRoot 'base'
$versionsRoot = Join-Path $managedRoot 'versions'
$logsRoot = Join-Path $managedRoot 'logs'
$binRoot = Join-Path $managedRoot 'bin'
$baseVenv = Join-Path $baseRoot 'venv'
$currentVersion = if ($Version) { $Version } else { $null }
$currentRoot = $null
$currentVenv = $null
$configPath = Join-Path $managedRoot 'config.json'
$stateFile = Join-Path $managedRoot 'current.json'
$basePython = Join-Path $baseVenv 'Scripts\python.exe'
$currentPython = $null
$launcherShim = Join-Path $binRoot 'hangeul-mcp.cmd'
$manageShim = Join-Path $binRoot 'hangeul-mcp-manage.cmd'
$extrasSuffix = Get-ExtrasSuffix
$basePackageSpec = Get-SourcePackageSpec -ExtrasSuffix $extrasSuffix
$currentPackageSpec = $null
$installSource = if ($Version) { 'pypi' } else { 'bootstrap' }

foreach ($directory in @($managedRoot, $baseRoot, $versionsRoot, $logsRoot, $binRoot)) {
    if (-not (Test-Path -LiteralPath $directory)) {
        [void](New-Item -ItemType Directory -Path $directory -Force)
    }
}

Invoke-CheckedCommand -FilePath $pythonCommand -ArgumentList @('-m', 'venv', $baseVenv) | Out-Null
Invoke-CheckedCommand -FilePath $basePython -ArgumentList @('-m', 'pip', 'install', '--upgrade', 'pip') | Out-Null
Invoke-CheckedCommand -FilePath $basePython -ArgumentList @('-m', 'pip', 'install', '--upgrade', $basePackageSpec) | Out-Null
if (-not $currentVersion) {
    $currentVersion = (Invoke-CheckedCommand -FilePath $basePython -ArgumentList @('-c', 'import hangeul_mcp; print(hangeul_mcp.__version__)')).Trim()
}
$currentRoot = Join-Path $versionsRoot $currentVersion
$currentVenv = $currentRoot
$currentPython = Join-Path $currentVenv 'Scripts\python.exe'
$currentPackageSpec = if ($Version) {
    Get-VersionedPackageSpec -ExtrasSuffix $extrasSuffix -PinnedVersion $Version
} else {
    $basePackageSpec
}
if (Test-Path -LiteralPath $currentVenv) {
    Remove-Item -LiteralPath $currentVenv -Recurse -Force
}
Invoke-CheckedCommand -FilePath $pythonCommand -ArgumentList @('-m', 'venv', $currentVenv) | Out-Null
Invoke-CheckedCommand -FilePath $currentPython -ArgumentList @('-m', 'pip', 'install', '--upgrade', 'pip') | Out-Null
Invoke-CheckedCommand -FilePath $currentPython -ArgumentList @('-m', 'pip', 'install', '--upgrade', $currentPackageSpec) | Out-Null
Invoke-CheckedCommand -FilePath $currentPython -ArgumentList @('-c', 'import hangeul_mcp.server') | Out-Null

if (-not (Test-Path -LiteralPath $configPath)) {
    Write-Utf8NoBomText -Path $configPath -Content '{"auto":"notify","channel":"stable"}'
}

$state = [ordered]@{
    current_version = $currentVersion
    previous_version = $null
    install_source = $installSource
    updated_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
Write-Utf8NoBomText -Path $stateFile -Content ($state | ConvertTo-Json -Depth 5)
New-CommandShim -Path $launcherShim -BasePython $basePython -ModuleName 'hangeul_mcp.launcher'
New-CommandShim -Path $manageShim -BasePython $basePython -ModuleName 'hangeul_mcp.manage'
Ensure-UserPathContains -Directory $binRoot

$setupArguments = @('-m', 'hangeul_mcp.manage', 'setup', '--client', $Client)
if ($Features.Count -gt 0) {
    $setupArguments += @('--features')
    $setupArguments += $Features
}
if ($NonInteractive) {
    $setupArguments += '--yes'
}
$setupResult = Invoke-CheckedCommand -FilePath $basePython -ArgumentList $setupArguments -PassThru
if ($setupResult.StdOut) {
    Write-Host $setupResult.StdOut.Trim()
}
$setupJson = $setupResult.StdOut | ConvertFrom-Json
$doctorResult = Invoke-CheckedCommand -FilePath $basePython -ArgumentList @('-m', 'hangeul_mcp.manage', 'doctor', '--json') -PassThru
if ($doctorResult.StdOut) {
    Write-Host $doctorResult.StdOut.Trim()
}
$doctorJson = $doctorResult.StdOut | ConvertFrom-Json
if ($doctorJson.mcp_smoke.status -ne 'ok' -or -not $doctorJson.core_import.ok) {
    throw 'Installed runtime failed doctor verification.'
}

if ($setupJson.status -eq 'needs_manual_steps') {
    Write-Host 'Managed install completed with manual client follow-up required.'
} else {
    Write-Host 'Managed install completed.'
}
Write-Host "Stable launcher shim: $launcherShim"
Write-Host "Managed CLI shim: $manageShim"
Write-Host 'Reopen PowerShell so the updated user PATH picks up the managed shims.'
