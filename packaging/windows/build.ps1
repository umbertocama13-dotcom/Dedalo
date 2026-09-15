<#
.SYNOPSIS
  Builds packaging\windows\output\Dedalo-Setup.exe on a Windows machine.

.DESCRIPTION
  Steps: export of the embedding model to ONNX, runtime environment, desktop build of the
  frontend, icon, WebView2 bootstrapper, PyInstaller, Inno Setup.
  Requirements and copy-paste commands: packaging\windows\BUILD.md.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -Version 2.0.0
#>
param(
    [string]$Version = "2.0.0",
    # Reuse backend\models if the model was already exported (the export downloads ~1 GB).
    [switch]$SkipModelExport
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Packaging = $PSScriptRoot
$Build = Join-Path $Packaging "build"
$ModelDir = Join-Path $Root "backend\models\sentence-bert-base-italian-xxl-uncased"
$InnoCompiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
$WebView2Bootstrapper = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

# PowerShell does not stop on a failing external program: check every exit code explicitly.
function Invoke-Step {
    param([string]$Description, [scriptblock]$Command)
    Write-Host "`n=== $Description" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Failed: $Description (exit code $LASTEXITCODE)" }
}

function New-Venv {
    param([string]$Path)
    if (-not (Test-Path (Join-Path $Path "Scripts\python.exe"))) {
        py -3.12 -m venv $Path
        if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment $Path (is Python 3.12 installed?)" }
    }
    return (Join-Path $Path "Scripts\python.exe")
}

Write-Host "Dedalo $Version - build in $Root"
foreach ($tool in @("py", "npm")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool not found: see BUILD.md" }
}
if (-not (Test-Path $InnoCompiler)) { throw "Inno Setup 6 not found in $InnoCompiler: see BUILD.md" }
New-Item -ItemType Directory -Force $Build | Out-Null

# 1. Embedding model -> ONNX, in a separate environment (needs PyTorch, which the app does not ship).
if ($SkipModelExport -and (Test-Path (Join-Path $ModelDir "model.onnx"))) {
    Write-Host "`n=== Model export skipped: using $ModelDir" -ForegroundColor Cyan
} else {
    $ExportPython = New-Venv (Join-Path $Build "venv-export")
    Invoke-Step "Update pip (export environment)" { & $ExportPython -m pip install --upgrade pip }
    Invoke-Step "Install PyTorch CPU (export only)" {
        & $ExportPython -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    }
    Invoke-Step "Install optimum-onnx (export only)" { & $ExportPython -m pip install optimum-onnx onnxruntime==1.30.0 }
    Invoke-Step "Export the embedding model to ONNX" {
        & $ExportPython (Join-Path $Root "backend\scripts\export_onnx_model.py") --output $ModelDir
    }
}

# 2. Runtime environment: only what the installed app needs.
$DesktopPython = New-Venv (Join-Path $Build "venv-desktop")
Invoke-Step "Update pip (runtime environment)" { & $DesktopPython -m pip install --upgrade pip }
Invoke-Step "Install runtime dependencies" {
    & $DesktopPython -m pip install -r (Join-Path $Packaging "requirements-desktop.txt")
}
Invoke-Step "Record the exact installed versions" {
    & $DesktopPython -m pip freeze | Out-File -Encoding utf8 (Join-Path $Build "requirements-desktop.lock.txt")
}
Invoke-Step "Check that the app imports without PyTorch" {
    $env:PYTHONPATH = Join-Path $Root "backend"
    & $DesktopPython -c "import desktop.launcher, onnxruntime, webview; print('imports ok')"
}

# 3. Frontend built for same-origin API calls.
Push-Location (Join-Path $Root "frontend")
try {
    Invoke-Step "Install frontend dependencies" { npm ci }
    Invoke-Step "Build the frontend (desktop mode)" { npm run build -- --mode desktop }
} finally {
    Pop-Location
}

# 4. Icon and WebView2 bootstrapper.
Invoke-Step "Draw the icon" { & $DesktopPython (Join-Path $Packaging "make_icon.py") (Join-Path $Build "dedalo.ico") }
Write-Host "`n=== Download the WebView2 bootstrapper" -ForegroundColor Cyan
Invoke-WebRequest -Uri $WebView2Bootstrapper -OutFile (Join-Path $Build "MicrosoftEdgeWebview2Setup.exe")

# 5. Application folder and installer.
Invoke-Step "Package the app with PyInstaller" {
    & $DesktopPython -m PyInstaller --noconfirm --clean `
        --distpath (Join-Path $Packaging "dist") `
        --workpath (Join-Path $Build "pyinstaller") `
        (Join-Path $Packaging "dedalo.spec")
}
Invoke-Step "Compile the installer with Inno Setup" {
    & $InnoCompiler "/DAppVersion=$Version" (Join-Path $Packaging "installer.iss")
}

$Installer = Get-Item (Join-Path $Packaging "output\Dedalo-Setup.exe")
Write-Host ("`nDone: {0} ({1:N0} MB)" -f $Installer.FullName, ($Installer.Length / 1MB)) -ForegroundColor Green
