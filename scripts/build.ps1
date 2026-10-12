# Builds the executable and the Windows installer.
# Run from the project root: .\scripts\build.ps1
# Everything stays inside the project folder (temp files, caches, output).

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:TEMP = Join-Path $root ".tmp"
$env:TMP = $env:TEMP
$env:PYINSTALLER_CONFIG_DIR = Join-Path $root ".tmp\pyi"
New-Item -ItemType Directory -Force $env:TEMP | Out-Null

$version = (Select-String -Path "src\pulse_studio\__init__.py" -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value

.\.venv\Scripts\python.exe scripts\make_icon.py
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed" }
# PyInstaller writes progress to stderr, which is not an error.
.\.venv\Scripts\pyinstaller.exe pulse-studio.spec --noconfirm --distpath dist --workpath build 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$iscc = @("D:\Tools\InnoSetup\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup (ISCC.exe) not found" }
& $iscc "/DMyAppVersion=$version" "installer\pulse-studio.iss" | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

Get-ChildItem dist -Filter "PulseStudio-Setup-*.exe" | Select-Object Name, Length
