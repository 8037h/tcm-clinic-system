$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$ErrorActionPreference = 'Continue'

$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonExe = if (Test-Path -LiteralPath $bundledPython) { $bundledPython } else { 'python' }
$packages = Join-Path $PSScriptRoot '.packages'
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$packages;$env:PYTHONPATH" } else { $packages }

& $pythonExe -c 'import django.core, requests.sessions, bs4' 2>$null
if ($LASTEXITCODE -ne 0) {
    & $pythonExe -m pip install --target $packages -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $pythonExe manage.py crawl_medical_data @args
exit $LASTEXITCODE
