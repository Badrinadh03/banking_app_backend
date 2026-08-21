import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    if settings.card_encryption_key:
        key = settings.card_encryption_key.encode()
    else:
        # No dedicated key configured — derive a stable one from the JWT
        # secret so a fresh .env can issue cards without extra setup.
        # Production deployments should set CARD_ENCRYPTION_KEY explicitly.
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret_key.encode()).digest())
    return Fernet(key)


def encrypt_value(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()
