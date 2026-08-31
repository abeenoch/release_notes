"""
Cross-database UUID column helper.

- SQLite: uses String(36) 
- PostgreSQL: uses native UUID type
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import String
from sqlalchemy.orm import mapped_column


def uuid_column(**kwargs: Any) -> Any:
    """
    Returns a mapped_column that works across SQLite and PostgreSQL.
    In SQLite, stores UUID as String(36). In PostgreSQL, uses native UUID.
    """
    return mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        **kwargs,
    )