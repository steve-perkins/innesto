"""Run migrations programmatically at application startup.

Databases created before Alembic was introduced (phase 1-4) have the baseline
tables but no `alembic_version`; they are stamped at the baseline revision
first and then upgraded, so an existing library carries over untouched.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

BASELINE = "0001"
log = logging.getLogger("innesto.migrations")


def alembic_config(engine: Engine) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent))
    cfg.set_main_option("sqlalchemy.url", str(engine.url).replace("%", "%%"))
    return cfg


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def upgrade(engine: Engine) -> None:
    cfg = alembic_config(engine)
    tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    if tables and current_revision(engine) is None:
        log.info("pre-Alembic database detected; stamping baseline %s", BASELINE)
        command.stamp(cfg, BASELINE)
    command.upgrade(cfg, "head")
