from __future__ import annotations

from datetime import datetime, timezone

from django.conf import settings
from eth_utils import to_checksum_address
from siwe import SiweMessage


def build_message(
    *,
    domain: str,
    uri: str,
    address: str,
    nonce: str,
    issued_at: datetime | None = None,
) -> str:
    """Build a canonical EIP-4361 SIWE message string.

    Delegates to the siwe library so the output is guaranteed to round-trip
    through SiweMessage.from_message() on the verify path.
    """
    issued = (issued_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    if issued.endswith("+00:00"):
        issued = issued[:-6] + "Z"
    msg = SiweMessage(
        domain=domain,
        address=to_checksum_address(address),
        uri=uri,
        version="1",
        chain_id=settings.SIWE_CHAIN_ID,
        nonce=nonce,
        issued_at=issued,
        statement=settings.SIWE_STATEMENT,
    )
    return msg.prepare_message()
