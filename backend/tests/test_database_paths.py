"""ensure_sqlite_dir — backend/data/ is no longer tracked in git, so the
app must create it before SQLite touches the file."""
from app.database import ensure_sqlite_dir


def test_in_memory_urls_are_skipped():
    assert ensure_sqlite_dir("sqlite+aiosqlite://") is None
    assert ensure_sqlite_dir("sqlite+aiosqlite:///:memory:") is None


def test_file_url_creates_missing_directories(tmp_path):
    target = tmp_path / "fresh" / "nested" / "app.db"
    created = ensure_sqlite_dir(f"sqlite+aiosqlite:///{target}")
    assert created == target.parent
    assert target.parent.is_dir()


def test_existing_directory_is_idempotent(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/app.db"
    first = ensure_sqlite_dir(url)
    assert first is not None and first.is_dir()
    assert ensure_sqlite_dir(url) == first
