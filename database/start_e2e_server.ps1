$ErrorActionPreference = "Stop"

$e2eDatabase = Join-Path $PSScriptRoot "handicrafts-e2e.db"
foreach ($path in @($e2eDatabase, "$e2eDatabase-wal", "$e2eDatabase-shm")) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

$env:HANDICRAFTS_DB_PATH = $e2eDatabase
$env:HANDICRAFTS_PORT = "8788"
# The isolated test server must never attempt to send real SMS, even when a
# developer's local .env contains production provider credentials.
$env:HANDICRAFTS_SMS_ENABLED = "0"

# Prefer the project environment so E2E exercises the same media-validation
# dependencies (notably Pillow) as the application.  Falling back preserves
# compatibility with CI environments that install requirements globally.
$projectPython = Join-Path $PSScriptRoot "..\venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $projectPython) { $projectPython } else { "python" }
& $python (Join-Path $PSScriptRoot "init_db.py")
& $python (Join-Path $PSScriptRoot "server.py")
