# verify_copy.ps1 -- confirm the staged files landed intact on a server.
#
# Run from the deploy folder AFTER copying staged\ (and optionally
# staged-optional\) into the project directory:
#
#     .\verify_copy.ps1 -ProjectRoot "C:\path\to\CleanEEGProject"
#
# Compares every file listed in SHA256SUMS.txt against the copy now sitting in
# the project. Exits 0 only if every expected file matches.
#
# NOTE: hashes are of the files as built on the dev workstation, which uses CRLF
# line endings to match production. If you copy through anything that rewrites
# line endings (some git clients, some SFTP text modes), hashes will not match
# even though the file may be usable -- recopy in binary rather than ignoring it.

param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [string]$SumsFile,

    # Skip rows under staged-optional\ (the numpy>=2 insurance file).
    [switch]$SkipOptional
)

if (-not $SumsFile) {
    # Resolve next to this script. Done here rather than as a param default:
    # $PSScriptRoot is not reliably populated in a param() default expression.
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $SumsFile = Join-Path $scriptDir "SHA256SUMS.txt"
}

if (-not (Test-Path $ProjectRoot)) {
    Write-Host "Project root not found: $ProjectRoot" -ForegroundColor Red
    exit 2
}
if (-not (Test-Path $SumsFile)) {
    Write-Host "Checksum file not found: $SumsFile" -ForegroundColor Red
    exit 2
}

$ok = 0
$bad = 0
$missing = 0

foreach ($line in Get-Content $SumsFile) {
    if ($line.Trim() -eq "") { continue }

    # "<64 hex>  <staged-or-staged-optional>/<relative path>"
    $parts = $line -split '\s+', 2
    $expected = $parts[0].Trim()
    $rel = $parts[1].Trim()

    if ($SkipOptional -and $rel -like "staged-optional/*") { continue }

    # Strip the staging prefix -- both trees overlay the project root directly.
    $inProject = $rel -replace '^staged-optional/', '' -replace '^staged/', ''
    $target = Join-Path $ProjectRoot ($inProject -replace '/', '\')

    if (-not (Test-Path $target)) {
        Write-Host ("MISSING  {0}" -f $inProject) -ForegroundColor Red
        $missing++
        continue
    }

    $actual = (Get-FileHash $target -Algorithm SHA256).Hash
    if ($actual -ieq $expected) {
        Write-Host ("OK       {0}" -f $inProject) -ForegroundColor Green
        $ok++
    } else {
        Write-Host ("MISMATCH {0}" -f $inProject) -ForegroundColor Red
        Write-Host ("           expected {0}" -f $expected)
        Write-Host ("           actual   {0}" -f $actual)
        $bad++
    }
}

Write-Host ""
Write-Host ("{0} ok, {1} mismatched, {2} missing" -f $ok, $bad, $missing)

if ($bad -gt 0 -or $missing -gt 0) {
    Write-Host "Do not proceed -- recopy the offending files." -ForegroundColor Red
    exit 1
}
Write-Host "All staged files verified." -ForegroundColor Green
exit 0
