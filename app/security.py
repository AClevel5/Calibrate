"""Password hashing (stdlib scrypt) and ingest-token generation — no extra deps."""

import base64
import hashlib
import hmac
import secrets

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_b64, dk_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        salt = _unb64(salt_b64)
        expected = _unb64(dk_b64)
        dk = hashlib.scrypt(password.encode(), salt=salt, **{**_SCRYPT, "dklen": len(expected)})
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


def new_ingest_token() -> str:
    return secrets.token_urlsafe(24)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s.encode())
