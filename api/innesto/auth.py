"""Identity. Phase 1: a single implicit local user. Phase 5 swaps this for a
session cookie populated by Google OIDC; the rest of the app only ever calls
`current_user_id`."""

from __future__ import annotations

from . import config


def current_user_id() -> str:
    return config.LOCAL_USER_ID
