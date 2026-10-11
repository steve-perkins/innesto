import sqlite3
from datetime import datetime, timezone


def test_snapshot_is_consistent_and_pruned(app_env):
    from innesto import config, maintenance
    first = maintenance.snapshot(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert first.name == "innesto-20260101.db"
    latest = maintenance.snapshot()                       # today
    with sqlite3.connect(latest) as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("SELECT count(*) FROM user").fetchone()[0] == 1
    assert (config.DATA_DIR / "backups" / "innesto-latest.db").exists()
    assert not first.exists()                             # older than KEEP_DAYS, pruned
