"""SQLite backup, verification, and local recovery utility.

Restore is intentionally a local CLI-only operation. It validates the backup,
then preserves the current database alongside the target before replacing it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid
from sqlite_config import connect as sqlite_connect


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "handicrafts.db"
SUMMARY_IGNORED_TABLES = {"database_backup_runs"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup(path: Path) -> dict:
    source = path.resolve()
    if not source.is_file():
        raise ValueError("Backup file does not exist")
    uri = f"file:{source.as_posix()}?mode=ro"
    connection = sqlite_connect(uri, writable=False, uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"Backup integrity check failed: {integrity}")
    finally:
        connection.close()
    return {"file": source.name, "path": str(source), "bytes": source.stat().st_size, "sha256": sha256(source), "integrity": integrity}


def database_summary(path: Path) -> dict:
    """Small logical fingerprint used by non-destructive restore rehearsals."""
    connection = sqlite_connect(path, writable=False)
    try:
        tables = [
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            if row[0] not in SUMMARY_IGNORED_TABLES
        ]
        counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34) * 2)}"').fetchone()[0] for table in tables}
    finally:
        connection.close()
    return {"tables": tables, "counts": counts}


def create_backup(destination: Path, source: Path = DEFAULT_DB) -> dict:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise ValueError("Source database does not exist")
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = destination / f"handicrafts-{stamp}.db"
    source_connection = sqlite_connect(source, writable=False)
    target_connection = sqlite_connect(target)
    try:
        source_connection.backup(target_connection)
    finally:
        target_connection.close()
        source_connection.close()
    metadata = verify_backup(target)
    metadata["createdAt"] = datetime.now(timezone.utc).isoformat()
    (target.with_suffix(".json")).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    connection = sqlite_connect(source)
    try:
        connection.execute(
            "INSERT INTO database_backup_runs (id, file_name, sha256, byte_size) VALUES (?, ?, ?, ?)",
            (f"backup-{uuid.uuid4().hex}", target.name, metadata["sha256"], metadata["bytes"]),
        )
        connection.commit()
    finally:
        connection.close()
    return metadata


def rehearse_restore(destination: Path, source: Path = DEFAULT_DB) -> dict:
    """Restore a fresh backup into an isolated copy and verify logical contents."""
    source = source.resolve()
    destination = destination.resolve()
    before = database_summary(source)
    backup_metadata = create_backup(destination, source)
    backup_path = destination / backup_metadata["file"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    rehearsal_target = destination / f"restore-drill-{stamp}.db"
    incoming = sqlite_connect(backup_path, writable=False)
    replacement = sqlite_connect(rehearsal_target)
    try:
        incoming.backup(replacement)
    finally:
        replacement.close()
        incoming.close()
    verification = verify_backup(rehearsal_target)
    after = database_summary(rehearsal_target)
    if after != before:
        raise ValueError("Restore rehearsal content mismatch")
    return {"backup": backup_metadata, "restored": verification, "target": str(rehearsal_target), "verifiedAt": datetime.now(timezone.utc).isoformat()}


def restore_backup(backup: Path, target: Path = DEFAULT_DB) -> dict:
    backup = backup.resolve()
    target = target.resolve()
    if target != DEFAULT_DB.resolve():
        raise ValueError("Restore target must be the configured database path")
    metadata = verify_backup(backup)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safety_copy = target.with_name(f"{target.stem}-before-restore-{stamp}{target.suffix}")
    if target.exists():
        current = sqlite_connect(target, writable=False)
        preserved = sqlite_connect(safety_copy)
        try:
            current.backup(preserved)
        finally:
            preserved.close()
            current.close()
    incoming = sqlite_connect(backup, writable=False)
    replacement = sqlite_connect(target)
    try:
        incoming.backup(replacement)
    finally:
        replacement.close()
        incoming.close()
    connection = sqlite_connect(target)
    try:
        updated = connection.execute(
            "UPDATE database_backup_runs SET restored_at = CURRENT_TIMESTAMP WHERE sha256 = ?",
            (metadata["sha256"],),
        ).rowcount
        if not updated:
            connection.execute(
                "INSERT INTO database_backup_runs (id, file_name, sha256, byte_size, restored_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (f"backup-{uuid.uuid4().hex}", backup.name, metadata["sha256"], metadata["bytes"]),
            )
        connection.commit()
    finally:
        connection.close()
    metadata["safetyCopy"] = str(safety_copy) if safety_copy.exists() else None
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Handicrafts SQLite backup utility")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--destination", required=True, type=Path)
    create.add_argument("--source", type=Path, default=DEFAULT_DB)
    verify = commands.add_parser("verify")
    verify.add_argument("--file", required=True, type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("--file", required=True, type=Path)
    restore.add_argument("--target", type=Path, default=DEFAULT_DB)
    drill = commands.add_parser("drill")
    drill.add_argument("--destination", required=True, type=Path)
    drill.add_argument("--source", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if args.command == "create":
        result = create_backup(args.destination, args.source)
    elif args.command == "verify":
        result = verify_backup(args.file)
    elif args.command == "drill":
        result = rehearse_restore(args.destination, args.source)
    else:
        result = restore_backup(args.file, args.target)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
