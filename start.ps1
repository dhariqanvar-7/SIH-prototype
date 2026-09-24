Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$runtimePython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonReady = $false
if (Test-Path -LiteralPath $projectPython) {
    & $projectPython --version 2>$null | Out-Null
    $pythonReady = $LASTEXITCODE -eq 0
}
if (-not $pythonReady) {
    if (-not (Test-Path -LiteralPath $runtimePython)) {
        throw 'Python environment is unavailable. Create .venv and install requirements.txt first.'
    }
    $projectPython = $runtimePython
    $env:PYTHONPATH = @(
        (Join-Path $PSScriptRoot '.venv\raster-deps'),
        (Join-Path $PSScriptRoot '.venv\Lib\site-packages')
    ) -join [IO.Path]::PathSeparator
}
$env:PYTHONUTF8 = '1'
& $projectPython -m streamlit run "$PSScriptRoot\app.py" --server.address 127.0.0.1 --server.port 8501 --server.headless true
