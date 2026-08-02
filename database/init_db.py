from pathlib import Path
import os
import sqlite3
from sqlite_config import configure_connection


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("HANDICRAFTS_DB_PATH", ROOT / "handicrafts.db"))
MIGRATIONS = ROOT / "migrations"


def run_sql_file(connection: sqlite3.Connection, path: Path) -> None:
    connection.executescript(path.read_text(encoding="utf-8"))


def main() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        configure_connection(connection)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = {
            row[0] for row in connection.execute("SELECT name FROM schema_migrations")
        }
        for migration in sorted(MIGRATIONS.glob("*.sql")):
            if migration.name not in applied:
                run_sql_file(connection, migration)
                connection.execute(
                    "INSERT INTO schema_migrations (name) VALUES (?)", (migration.name,)
                )
        run_sql_file(connection, ROOT / "seed.sql")
        connection.commit()
    print(f"Database initialized: {DB_PATH}")


if __name__ == "__main__":
    main()
