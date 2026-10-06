$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonExe = 'D:\0TIGER\6months\PythonAPIDevelopment\venv_multi_query\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "找不到指定的 Python：$PythonExe"
}

Set-Location -LiteralPath $ProjectRoot
$AppHost = if ($env:ROOMSTYLER_HOST) { $env:ROOMSTYLER_HOST } else { '127.0.0.1' }
$AppPort = if ($env:ROOMSTYLER_PORT) { $env:ROOMSTYLER_PORT } else { '18083' }
& $PythonExe -m uvicorn app.main:app --host $AppHost --port $AppPort
