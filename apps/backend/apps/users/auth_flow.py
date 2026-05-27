"""SIWE verify-flow business logic.

Runs *after* the siwe library has cryptographically verified the signature
and confirmed the recovered address matches the SIWE message's address
field. By the time `resolve_signed_in_user` is called, you can trust the
address — but you have NOT yet decided whether this sign-in attempt is
acceptable as policy.

This module exists so the auth policy is unit-testable without HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.users.models import User
from apps.users.nonce import consume_nonce


class AuthFailure(Exception):
    """Expected control-flow exit. The view converts this to a 401.

    The `reason` is for logs only — never echo it to the client, since
    distinguishing failure modes helps attackers enumerate behavior.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class VerifiedSignIn:
    user: User
    was_created: bool


def resolve_signed_in_user(
    *,
    verified_address: str,
    submitted_nonce: str,
) -> VerifiedSignIn:
    """Decide whether a cryptographically-verified sign-in produces a user.

    Inputs:
      verified_address — lowercase 0x-address. The siwe library has already
                         verified that the signature came from the holder
                         of this address's private key.
      submitted_nonce  — the nonce string from the signed SIWE message.

    Returns:
      VerifiedSignIn(user=..., was_created=...) on success.

    Raises:
      AuthFailure on any policy violation.

    >>> USER WRITES THIS FUNCTION <<<

    Two real decisions live in 5-10 lines below:

    1. NONCE CONSUMPTION TIMING. Consume before or after user lookup?
       - Before: any signed-message replay burns the nonce regardless of
         downstream success — tight replay window, no half-states.
       - After: lets the user-lookup-or-create happen first; if that
         fails for any reason (DB hiccup, etc), the nonce survives so the
         client can retry without re-signing. Slightly slacker replay
         protection but better UX in failure modes.

    2. USER RESOLUTION. Auto-create (per the design choice) — but how?
       - `User.objects.get_or_create(wallet_address=...)` is the one-liner.
         Returns (user, created) tuple. Simple.
       - Explicit `try/except User.DoesNotExist` lets you do side-effects
         on first sign-in (welcome email, analytics event) without an
         extra DB read. Worth it if you'll add those soon.

    Auto-create policy was chosen at scaffold time, so unknown addresses
    DO produce a new User. If that changes, raise AuthFailure here on
    the not-allowlisted case instead.
    """
    if not consume_nonce(verified_address, submitted_nonce):
        raise AuthFailure("nonce invalid or replayed")
    user, was_created = User.objects.get_or_create(wallet_address=verified_address)
    return VerifiedSignIn(user=user, was_created=was_created)
