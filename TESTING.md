# Quality Checks

Run the full delivery gate:

```powershell
npm run test:all
```

The gate runs SQLite-backed backend tests, React component tests, the production build, and Playwright end-to-end tests.

On a machine without Playwright browsers, install Chromium once before running E2E tests:

```powershell
npx playwright install chromium
```

E2E starts the SQLite API on port `8788` and Vite on port `5174` when those services are not already running. On Windows it prefers `venv\\Scripts\\python.exe` so media validation runs with the project's Python dependencies. Failures retain a Playwright trace and screenshot under `test-results/`.

## SQLite Protection

All application and migration connections enable SQLite WAL mode, foreign-key checks, and an 8-second busy timeout by default. Override the timeout only when necessary with `HANDICRAFTS_SQLITE_BUSY_TIMEOUT_MS`.

Create a verified backup:

```powershell
python database/backup.py create --destination database/backups
```

Run a non-destructive backup and restore rehearsal. It restores only into a new file under the given directory, then compares its logical contents with the source database:

```powershell
python database/backup.py drill --destination database/backups
```

`restore` replaces `database/handicrafts.db` after creating a safety copy. Use it only during a maintenance window after verifying the selected backup:

```powershell
python database/backup.py verify --file database/backups/handicrafts-<timestamp>.db
python database/backup.py restore --file database/backups/handicrafts-<timestamp>.db
```
