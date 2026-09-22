# apply_local.ps1 -- overlay the staged files onto one of the LOCAL server
# mirror folders (the copies on this workstation that get pushed to the servers
# by Remote Desktop).
#
#     .\apply_local.ps1 -Target dev        # C:\BrainPanel\CleanEEGProject - development
#     .\apply_local.ps1 -Target prod       # C:\BrainPanel\CleanEEGProject - production
#     .\apply_local.ps1 -Target prod -WithOptional   # also process\detect_artifact.py
#
# What it does, in order:
#   1. Backs up every file about to be replaced into <root>\_backup-2026-09\
#      (only those files, not the whole 280 MB tree).
#   2. Copies staged\ (and staged-optional\ if -WithOptional) over the root.
#   3. Runs verify_copy.ps1 so the result is checked against SHA256SUMS.txt.
#
# It never touches plot\plot_svc.py or tomwatchdog.py -- both differ between the
# dev and production mirrors for reasons unrelated to this deployment, and must
# stay as they are in each folder.

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "prod")]
    [string]$Target,

    [switch]$WithOptional,

    # Testing hook: point at some other project folder instead of the two
    # mirrors. Not needed for a real deployment.
    [string]$RootOverride
)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$roots = @{
    dev  = "C:\BrainPanel\CleanEEGProject - development"
    prod = "C:\BrainPanel\CleanEEGProject - production"
}
$root = $roots[$Target]
if ($RootOverride) { $root = $RootOverride }

if (-not (Test-Path (Join-Path $root "module7.py"))) {
    Write-Host "Not a project folder (no module7.py): $root" -ForegroundColor Red
    exit 2
}

$sources = @((Join-Path $here "staged"))
if ($WithOptional) { $sources += (Join-Path $here "staged-optional") }

# --- 1. back up exactly the files that are about to change -------------------
$backup = Join-Path $root "_backup-2026-09"
New-Item -ItemType Directory -Force $backup | Out-Null
$n = 0
foreach ($src in $sources) {
    Get-ChildItem $src -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($src.Length).TrimStart('\')
        $existing = Join-Path $root $rel
        if (Test-Path $existing) {
            $dest = Join-Path $backup $rel
            New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
            Copy-Item $existing $dest -Force
            $n++
        }
    }
}
Write-Host ("Backed up {0} existing file(s) to {1}" -f $n, $backup)

# --- 2. overlay ----------------------------------------------------------------
foreach ($src in $sources) {
    # /E copy subdirs, /NJH /NJS quiet headers. Exit codes < 8 are success.
    robocopy $src $root /E /NJH /NJS /NDL | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Host ("robocopy failed ({0}) copying {1}" -f $LASTEXITCODE, $src) -ForegroundColor Red
        exit 1
    }
}
Write-Host ("Overlaid onto {0}" -f $root)

# --- 3. verify ----------------------------------------------------------------
$verify = Join-Path $here "verify_copy.ps1"
if ($WithOptional) {
    & $verify -ProjectRoot $root
} else {
    & $verify -ProjectRoot $root -SkipOptional
}
exit $LASTEXITCODE
