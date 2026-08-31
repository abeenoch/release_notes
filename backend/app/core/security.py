from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.config import settings


# Fernet encryption for user API keys at rest ─

def _get_fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        # In dev, derive a key from SECRET_KEY so we don't need a separate env var
        from base64 import urlsafe_b64encode
        raw = settings.secret_key.encode("utf-8").ljust(32, b"\0")[:32]
        key = urlsafe_b64encode(raw).decode()
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key for storage."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """Decrypt a stored API key."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


# JWT

def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc)
        + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes)),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """Return the payload or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None