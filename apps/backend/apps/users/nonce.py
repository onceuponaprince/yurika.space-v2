from __future__ import annotations

import secrets
import string

from django.core.cache import cache

NONCE_TTL_SECONDS = 300
NONCE_LENGTH = 16
_ALPHABET = string.ascii_letters + string.digits


def _key(wallet_address: str) -> str:
    return f"siwe:nonce:{wallet_address.lower()}"


def mint_nonce(wallet_address: str) -> str:
    nonce = "".join(secrets.choice(_ALPHABET) for _ in range(NONCE_LENGTH))
    cache.set(_key(wallet_address), nonce, timeout=NONCE_TTL_SECONDS)
    return nonce


def consume_nonce(wallet_address: str, submitted: str) -> bool:
    key = _key(wallet_address)
    stored = cache.get(key)
    if stored is None or stored != submitted:
        return False
    cache.delete(key)
    return True
