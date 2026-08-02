"""Shared SQLite connection safeguards for the single-node deployment."""

from __future__ import annotations

import os
import sqlite3


BUSY_TIMEOUT_MS = max(1_000, int(os.environ.get("HANDICRAFTS_SQLITE_BUSY_TIMEOUT_MS", "8000")))


def configure_connection(connection: sqlite3.Connection, *, writable: bool = True) -> sqlite3.Connection:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    if writable:
        # WAL permits readers while one request is committing a business transaction.
        connection.execute("PRAGMA journal_mode = WAL").fetchone()
        connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def connect(path: str | os.PathLike[str], *, writable: bool = True, uri: bool = False) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000, uri=uri)
    return configure_connection(connection, writable=writable)
