$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonExe = if (Test-Path -LiteralPath $bundledPython) { $bundledPython } else { 'python' }
$packages = Join-Path $PSScriptRoot '.packages'
if (-not (Test-Path -LiteralPath (Join-Path $packages 'django\__init__.py'))) {
    & $pythonExe -m pip install --target $packages -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$env:PYTHONPATH = $packages
& $pythonExe manage.py migrate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonExe manage.py runserver
