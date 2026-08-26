# Private SQLite backups to COS

`database/backup.py sync` makes a SQLite online snapshot, verifies it with
`PRAGMA integrity_check`, uploads the database and SHA-256 manifest to COS,
then removes expired copies. It never sends a backup through the CDN.

## Required COS security boundary

Use a **separate private COS bucket** for backups. Do not place backups in the
public product-image bucket, do not configure a CDN domain for this bucket,
and do not grant anonymous-read access.

The existing server-side COS credentials require these permissions on only the
backup prefix:

- `name/cos:PutObject`
- `name/cos:PutObjectACL`
- `name/cos:DeleteObject`
- `name/cos:GetBucket`

Create a bucket, for example `handicraft-backups-1330129678`, in Guangzhou or
the same region as the server. Its access permission must be **private**. Add
these non-secret values to the production `.env` file:

```text
HANDICRAFTS_COS_BACKUP_BUCKET=handicraft-backups-1330129678
HANDICRAFTS_COS_BACKUP_PREFIX=backups/production/sqlite
HANDICRAFTS_COS_BACKUP_RETENTION_DAYS=90
HANDICRAFTS_LOCAL_BACKUP_RETENTION_DAYS=7
```

The `ACL=private` upload setting is an additional safeguard, but it does not
replace keeping the bucket/prefix private in the COS console.

## Run once manually

Run as the same `www` user that owns the live database:

```bash
cd /www/wwwroot/shouzuohub.com/handicrafts && install -d -o www -g www database/backups && sudo -u www -H /usr/bin/python3 database/backup.py sync --destination database/backups
```

Success prints JSON containing the backup file checksum and COS object keys;
it never prints credentials. Confirm both the `.db` and matching `.json` file
exist under the private COS prefix.

## Baota scheduled task

Create a Shell Script task, run daily at 03:20, with this command:

```bash
cd /www/wwwroot/shouzuohub.com/handicrafts && install -d -o www -g www database/backups && sudo -u www -H sh -c '/usr/bin/python3 database/backup.py sync --destination database/backups >> database/backups/backup.log 2>&1'
```

The process-local lock prevents a second task from making a competing backup.
Review `database/backups/backup.log` after the first scheduled run. Perform a
restore rehearsal at least quarterly in a separate temporary directory; do not
run `restore` on production unless recovering from an incident.
