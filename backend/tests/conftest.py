'''Shared test fixtures.

The app deliberately refuses to encrypt outside dev (no ENCRYPTION_KEY and
the default SECRET_KEY → RuntimeError), and CI runs with no .env — so any
test that stores encrypted secrets would pass locally and fail in CI.
Pin a valid Fernet key for the whole suite instead of depending on the
developer environment.'''

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())
