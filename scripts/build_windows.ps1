<#
.SYNOPSIS
    Builds Clicksmith.exe (and optionally a Setup installer) on Windows.

.DESCRIPTION
    1. Creates/uses a virtual environment and installs requirements-dev.txt.
    2. Generates the Win32 version-info resource from the package version.
    3. Runs PyInstaller against packaging\pyinstaller\clicksmith.spec.
    4. If Inno Setup's ISCC.exe is on PATH (or -InnoSetupPath is given), also builds the
       installer at packaging\inno\Output\Clicksmith-Setup-<version>.exe.

.EXAMPLE
    .\scripts\build_windows.ps1
    .\scripts\build_windows.ps1 -SkipVenv -InnoSetupPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
#>
[CmdletBinding()]
param(
    [switch]$SkipVenv,
    [string]$InnoSetupPath
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Step($Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }

if (-not $SkipVenv) {
    Step "Setting up .venv"
    if (-not (Test-Path ".venv")) { py -3.12 -m venv .venv }
    . .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements-dev.txt
}

Step "Running the test suite"
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed - aborting the build." }

Step "Generating the Windows version-info resource"
python packaging\pyinstaller\generate_version_info.py

Step "Running PyInstaller"
Remove-Item -Recurse -Force "packaging\pyinstaller\build", "packaging\pyinstaller\dist" -ErrorAction SilentlyContinue
pyinstaller packaging\pyinstaller\clicksmith.spec --noconfirm --distpath packaging\pyinstaller\dist --workpath packaging\pyinstaller\build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$ExePath = "packaging\pyinstaller\dist\Clicksmith\Clicksmith.exe"
Step "Running the frozen self-test (--selftest)"
& $ExePath --selftest
if ($LASTEXITCODE -ne 0) { throw "The frozen build failed its self-test." }
Write-Host "Built: $ExePath" -ForegroundColor Green

$Version = (Select-String -Path "src\clicksmith\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value

$Iscc = $InnoSetupPath
if (-not $Iscc) {
    $Candidate = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($Candidate) { $Iscc = $Candidate.Source }
}
if ($Iscc -and (Test-Path $Iscc)) {
    Step "Building the installer with Inno Setup"
    & $Iscc "/DAppVersion=$Version" "packaging\inno\clicksmith.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }
    Write-Host "Built: packaging\inno\Output\Clicksmith-Setup-$Version.exe" -ForegroundColor Green
} else {
    Write-Host "`nInno Setup (ISCC.exe) was not found - skipping the installer." -ForegroundColor Yellow
    Write-Host "Install it from https://jrsoftware.org/isdl.php to also build Clicksmith-Setup-$Version.exe," -ForegroundColor Yellow
    Write-Host "or pass -InnoSetupPath. The portable Clicksmith.exe above works fine without it." -ForegroundColor Yellow
}
