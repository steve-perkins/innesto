"""Nightly consistent SQLite snapshots.

The VM backup service tars the data volume while the app runs; a live SQLite
file (with WAL) copied that way may be mid-write. So every day at 06:30 UTC
(before the 07:00 backup), and at startup if today's copy is missing, the app
writes a consistent copy with SQLite's online backup API to
DATA_DIR/backups/innesto-YYYYMMDD.db (keeping 7) plus innesto-latest.db.

    python -m innesto.maintenance backup           # take a snapshot now
    python -m innesto.maintenance restore FILE     # replace the live db (app stopped!)
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

log = logging.getLogger("innesto.maintenance")
KEEP_DAYS = 7
SNAPSHOT_HOUR_UTC, SNAPSHOT_MINUTE_UTC = 6, 30


def backups_dir() -> Path:
    d = config.DATA_DIR / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def snapshot(now: datetime | None = None) -> Path:
    """Write a consistent copy of the database; returns the dated file."""
    now = now or datetime.now(timezone.utc)
    dest = backups_dir() / f"innesto-{now:%Y%m%d}.db"
    tmp = dest.with_suffix(".db.part")
    src = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    tmp.replace(dest)
    shutil.copyfile(dest, backups_dir() / "innesto-latest.db")
    prune(now)
    log.info("database snapshot written: %s (%d KB)", dest.name, dest.stat().st_size // 1024)
    return dest


def prune(now: datetime) -> None:
    cutoff = now - timedelta(days=KEEP_DAYS)
    for f in backups_dir().glob("innesto-????????.db"):
        try:
            stamp = datetime.strptime(f.stem.split("-")[1], "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if stamp < cutoff:
            f.unlink(missing_ok=True)


def restore(path: Path) -> None:
    """Replace the live database with a snapshot. Only with the app stopped."""
    src = sqlite3.connect(path)
    try:
        src.execute("PRAGMA integrity_check").fetchone()
    finally:
        src.close()
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(config.DB_PATH) + suffix)
        if p.exists():
            p.replace(p.with_name(p.name + ".bak"))
    shutil.copyfile(path, config.DB_PATH)
    print(f"restored {path} -> {config.DB_PATH} (previous db kept as .bak)")


def _seconds_until_next_run(now: datetime) -> float:
    target = now.replace(hour=SNAPSHOT_HOUR_UTC, minute=SNAPSHOT_MINUTE_UTC, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _loop() -> None:
    now = datetime.now(timezone.utc)
    if not (backups_dir() / f"innesto-{now:%Y%m%d}.db").exists():
        try:
            snapshot(now)
        except Exception:
            log.exception("startup snapshot failed")
    while True:
        time.sleep(_seconds_until_next_run(datetime.now(timezone.utc)))
        try:
            snapshot()
        except Exception:
            log.exception("nightly snapshot failed")


def start_scheduler() -> threading.Thread:
    t = threading.Thread(target=_loop, name="innesto-maintenance", daemon=True)
    t.start()
    return t


def main(argv: list[str]) -> int:
    if argv[:1] == ["backup"]:
        print(snapshot())
        return 0
    if argv[:1] == ["restore"] and len(argv) == 2:
        restore(Path(argv[1]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
