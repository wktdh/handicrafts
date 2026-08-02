$ErrorActionPreference = "Stop"

$e2eDatabase = Join-Path $PSScriptRoot "handicrafts-e2e.db"
foreach ($path in @($e2eDatabase, "$e2eDatabase-wal", "$e2eDatabase-shm")) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

$env:HANDICRAFTS_DB_PATH = $e2eDatabase
$env:HANDICRAFTS_PORT = "8788"
& python (Join-Path $PSScriptRoot "init_db.py")
& python (Join-Path $PSScriptRoot "server.py")
