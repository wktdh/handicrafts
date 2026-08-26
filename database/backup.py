"""SQLite backup, verification, and local recovery utility.

Restore is intentionally a local CLI-only operation. It validates the backup,
then preserves the current database alongside the target before replacing it.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import uuid
from sqlite_config import connect as sqlite_connect

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from qcloud_cos import CosConfig, CosS3Client
except ImportError:
    CosConfig = None
    CosS3Client = None


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "handicrafts.db"
SUMMARY_IGNORED_TABLES = {"database_backup_runs"}


def load_environment() -> None:
    """Load the deployment .env without ever printing its values."""
    env_file = ROOT.parent / ".env"
    if load_dotenv:
        load_dotenv(env_file)


def configured_database_path() -> Path:
    return Path(os.environ.get("HANDICRAFTS_DB_PATH", DEFAULT_DB))


def cos_backup_settings() -> dict[str, str]:
    """Read the private backup location from the same COS credentials as media."""
    required = {
        "secret_id": os.environ.get("HANDICRAFTS_COS_SECRET_ID", "").strip(),
        "secret_key": os.environ.get("HANDICRAFTS_COS_SECRET_KEY", "").strip(),
        "bucket": os.environ.get("HANDICRAFTS_COS_BACKUP_BUCKET", "").strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError("COS backup configuration is missing: " + ", ".join(missing))
    prefix = os.environ.get("HANDICRAFTS_COS_BACKUP_PREFIX", "backups/sqlite").strip("/ ")
    if not prefix:
        raise RuntimeError("HANDICRAFTS_COS_BACKUP_PREFIX must not be empty")
    return {
        **required,
        "region": os.environ.get("HANDICRAFTS_COS_REGION", "ap-guangzhou").strip() or "ap-guangzhou",
        "prefix": prefix,
    }


def cos_backup_client(settings: dict[str, str]) -> object:
    if CosConfig is None or CosS3Client is None:
        raise RuntimeError("COS backup requires cos-python-sdk-v5; install requirements.txt first")
    return CosS3Client(CosConfig(Region=settings["region"], SecretId=settings["secret_id"], SecretKey=settings["secret_key"]))


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


def upload_backup_to_cos(metadata: dict, destination: Path) -> dict:
    """Upload a verified backup and its checksum manifest to a private COS prefix."""
    settings = cos_backup_settings()
    client = cos_backup_client(settings)
    backup_path = destination / metadata["file"]
    manifest_path = backup_path.with_suffix(".json")
    if not manifest_path.is_file():
        raise ValueError("Backup manifest does not exist")

    database_key = f"{settings['prefix']}/{backup_path.name}"
    manifest_key = f"{settings['prefix']}/{manifest_path.name}"
    try:
        client.upload_file(
            Bucket=settings["bucket"],
            Key=database_key,
            LocalFilePath=str(backup_path),
            EnableMD5=True,
            ACL="private",
            ContentType="application/vnd.sqlite3",
            ContentDisposition=f'attachment; filename="{backup_path.name}"',
        )
        client.upload_file(
            Bucket=settings["bucket"],
            Key=manifest_key,
            LocalFilePath=str(manifest_path),
            EnableMD5=True,
            ACL="private",
            ContentType="application/json",
            ContentDisposition=f'attachment; filename="{manifest_path.name}"',
        )
    except Exception as error:
        raise RuntimeError("COS backup upload failed; verify CAM access to the private backup prefix") from error
    return {"bucket": settings["bucket"], "keys": [database_key, manifest_key]}


def _as_utc(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def remove_expired_cos_backups(retention_days: int) -> int:
    """Delete only old backup objects from this app's dedicated private prefix."""
    if retention_days < 1:
        raise ValueError("Remote backup retention must be at least one day")
    settings = cos_backup_settings()
    client = cos_backup_client(settings)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    prefix = f"{settings['prefix']}/"
    marker = ""
    deleted = 0
    while True:
        response = client.list_objects(Bucket=settings["bucket"], Prefix=prefix, Marker=marker, MaxKeys=1000)
        candidates = [
            {"Key": item["Key"]}
            for item in response.get("Contents", [])
            if item.get("Key", "").endswith((".db", ".json"))
            and (_as_utc(item.get("LastModified")) or cutoff) < cutoff
        ]
        if candidates:
            client.delete_objects(Bucket=settings["bucket"], Delete={"Objects": candidates, "Quiet": True})
            deleted += len(candidates)
        if not response.get("IsTruncated"):
            return deleted
        marker = response.get("NextMarker") or response.get("Contents", [])[-1]["Key"]


def remove_expired_local_backups(destination: Path, retention_days: int) -> int:
    if retention_days < 1:
        raise ValueError("Local backup retention must be at least one day")
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    removed = 0
    for path in destination.glob("handicrafts-*"):
        if path.suffix not in {".db", ".json"} or not path.is_file():
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if modified < cutoff:
            path.unlink()
            removed += 1
    return removed


def create_and_sync_backup(destination: Path, source: Path, *, remote_retention_days: int, local_retention_days: int) -> dict:
    """Create and verify a SQLite snapshot before uploading it to private COS."""
    metadata = create_backup(destination, source)
    remote = upload_backup_to_cos(metadata, destination)
    metadata["cos"] = remote
    metadata["expiredRemoteObjectsDeleted"] = remove_expired_cos_backups(remote_retention_days)
    metadata["expiredLocalFilesDeleted"] = remove_expired_local_backups(destination, local_retention_days)
    return metadata


@contextmanager
def exclusive_lock(lock_path: Path):
    """Prevent overlapping scheduler runs on Linux without affecting local tooling."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        try:
            import fcntl
        except ImportError:  # pragma: no cover - Windows is not the production scheduler.
            yield
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("A database backup is already running") from error
        yield
    finally:
        handle.close()


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
    if target != configured_database_path().resolve():
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
    load_environment()
    configured_db = configured_database_path()
    parser = argparse.ArgumentParser(description="Handicrafts SQLite backup utility")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--destination", required=True, type=Path)
    create.add_argument("--source", type=Path, default=configured_db)
    verify = commands.add_parser("verify")
    verify.add_argument("--file", required=True, type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("--file", required=True, type=Path)
    restore.add_argument("--target", type=Path, default=configured_db)
    drill = commands.add_parser("drill")
    drill.add_argument("--destination", required=True, type=Path)
    drill.add_argument("--source", type=Path, default=configured_db)
    sync = commands.add_parser("sync", help="Create, verify, and upload a private COS backup")
    sync.add_argument("--destination", required=True, type=Path)
    sync.add_argument("--source", type=Path, default=configured_db)
    sync.add_argument("--remote-retention-days", type=int, default=int(os.environ.get("HANDICRAFTS_COS_BACKUP_RETENTION_DAYS", "90")))
    sync.add_argument("--local-retention-days", type=int, default=int(os.environ.get("HANDICRAFTS_LOCAL_BACKUP_RETENTION_DAYS", "7")))
    args = parser.parse_args()
    if args.command == "create":
        result = create_backup(args.destination, args.source)
    elif args.command == "verify":
        result = verify_backup(args.file)
    elif args.command == "drill":
        result = rehearse_restore(args.destination, args.source)
    elif args.command == "sync":
        with exclusive_lock(args.destination / ".backup.lock"):
            result = create_and_sync_backup(
                args.destination,
                args.source,
                remote_retention_days=args.remote_retention_days,
                local_retention_days=args.local_retention_days,
            )
    else:
        result = restore_backup(args.file, args.target)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
