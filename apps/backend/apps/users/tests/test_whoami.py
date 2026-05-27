"""Tests for /api/auth/whoami/.

>>> 4 TESTS FOR YOU TO COMPLETE <<<

Each test has a docstring explaining WHAT to assert + WHY it matters,
followed by a TODO block describing the test body. Replace the
`raise NotImplementedError` with your implementation.

Useful tools already imported below — you should not need any others.

If you get stuck: apps/users/tests/test_verify_view.py uses
APIClient + JWT credentials in the same style. The
`rest_framework_simplejwt.tokens.RefreshToken.for_user(user)` API
returns a refresh token whose `.access_token` attribute is the access
token (stringify it for the Authorization header).
"""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


def _auth_header(user: User) -> dict[str, str]:
    """Helper: mints a fresh JWT for `user` and returns the kwarg dict
    you can splat into `client.credentials(...)`."""
    access = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": f"Bearer {access}"}


@pytest.mark.django_db
class TestWhoamiEndpoint:

    def test_returns_wallet_address_for_valid_jwt(self) -> None:
        """Happy path: a request with a valid Bearer token returns 200
        and the authenticated user's wallet_address.

        WHY this matters: this is the foundational test — if this
        breaks, every other auth-dependent endpoint we build will
        also be broken. Failure here means JWT issuance and JWT
        consumption are misaligned.
        """
        user = User.objects.create_user(wallet_address="0x" + "a" * 40)
        client = APIClient()
        client.credentials(**_auth_header(user))

        resp = client.get(reverse("whoami"))

        assert resp.status_code == 200
        assert resp.json()["wallet_address"] == user.wallet_address

    def test_rejects_request_without_authorization_header(self) -> None:
        """An unauthenticated request returns 401 (not 200, not 403).

        WHY this matters: 200 means the auth gate is broken. 403 means
        Django thinks the user is authenticated but unauthorized —
        which would imply our IsAuthenticated permission is being
        confused with an anonymous-user model somewhere. The right
        answer is exactly 401.
        """
        client = APIClient()

        resp = client.get(reverse("whoami"))

        assert resp.status_code == 401

    def test_rejects_malformed_bearer_token(self) -> None:
        """A request with `Authorization: Bearer <garbage>` returns 401,
        not 500.

        WHY this matters: malformed tokens are sent constantly (by
        curl-experimenters, by stale clients, by attackers probing).
        A 500 means we'd be leaking stack traces to those probes —
        and would also drown the error log in noise. 401 is the
        graceful answer.
        """
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-jwt")

        resp = client.get(reverse("whoami"))

        assert resp.status_code == 401

    def test_returns_correct_user_when_multiple_exist(self) -> None:
        """When multiple users exist in the DB, the response identifies
        the user the JWT was minted for — not just "any user".

        WHY this matters: a passing happy-path test can mask a bug
        where the view returns `User.objects.first()` (or similar)
        instead of `request.user`. The only way to catch that is to
        have more than one user in the DB and verify the JWT picks
        out the right one.
        """
        user_a = User.objects.create_user(wallet_address="0x" + "a" * 40)
        user_b = User.objects.create_user(wallet_address="0x" + "b" * 40)
        client = APIClient()
        client.credentials(**_auth_header(user_b))  # token is for user_b

        resp = client.get(reverse("whoami"))

        assert resp.status_code == 200
        body = resp.json()
        assert body["wallet_address"] == user_b.wallet_address
        assert body["wallet_address"] != user_a.wallet_address
