from __future__ import annotations

import pytest
from django.core.cache import cache
from django.urls import reverse
from eth_account import Account
from eth_account.messages import encode_defunct
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.fixture
def api_client() -> APIClient:
    cache.clear()
    return APIClient()


@pytest.fixture
def signer():
    """Create a fresh keypair + a function that signs SIWE messages with it."""
    acct = Account.create()

    def sign(message: str) -> str:
        signed = acct.sign_message(encode_defunct(text=message))
        return signed.signature.hex()

    return acct.address.lower(), sign


def _mint_message(api_client: APIClient, address: str) -> tuple[str, str]:
    resp = api_client.get(reverse("wallet-nonce"), {"address": address})
    assert resp.status_code == 200
    body = resp.json()
    return body["message"], body["nonce"]


@pytest.mark.django_db
class TestVerifyEndpoint:
    def test_happy_path_creates_user_and_issues_jwt(
        self, api_client: APIClient, signer
    ) -> None:
        address, sign = signer
        message, _ = _mint_message(api_client, address)
        signature = sign(message)

        resp = api_client.post(
            reverse("wallet-verify"),
            {"message": message, "signature": signature},
            format="json",
        )

        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["wallet_address"] == address
        assert body["access"]
        assert body["refresh"]
        assert User.objects.filter(wallet_address=address).exists()

    def test_replay_with_same_nonce_rejected(
        self, api_client: APIClient, signer
    ) -> None:
        address, sign = signer
        message, _ = _mint_message(api_client, address)
        signature = sign(message)

        first = api_client.post(
            reverse("wallet-verify"),
            {"message": message, "signature": signature},
            format="json",
        )
        assert first.status_code == 200

        replay = api_client.post(
            reverse("wallet-verify"),
            {"message": message, "signature": signature},
            format="json",
        )
        assert replay.status_code == 401

    def test_returning_user_does_not_double_create(
        self, api_client: APIClient, signer
    ) -> None:
        address, sign = signer

        # First sign-in
        msg1, _ = _mint_message(api_client, address)
        api_client.post(
            reverse("wallet-verify"),
            {"message": msg1, "signature": sign(msg1)},
            format="json",
        )

        # Second sign-in (fresh nonce)
        msg2, _ = _mint_message(api_client, address)
        resp = api_client.post(
            reverse("wallet-verify"),
            {"message": msg2, "signature": sign(msg2)},
            format="json",
        )

        assert resp.status_code == 200
        assert User.objects.filter(wallet_address=address).count() == 1

    def test_bad_signature_rejected(self, api_client: APIClient, signer) -> None:
        address, sign = signer
        message, _ = _mint_message(api_client, address)

        # Sign a DIFFERENT message — signature won't recover to the right address
        wrong_signature = sign("totally different content")

        resp = api_client.post(
            reverse("wallet-verify"),
            {"message": message, "signature": wrong_signature},
            format="json",
        )
        assert resp.status_code == 401
        assert not User.objects.filter(wallet_address=address).exists()

    def test_malformed_siwe_message_rejected(
        self, api_client: APIClient, signer
    ) -> None:
        _, sign = signer
        resp = api_client.post(
            reverse("wallet-verify"),
            {"message": "this is not a SIWE message", "signature": sign("anything")},
            format="json",
        )
        assert resp.status_code == 400

    def test_missing_body_fields_rejected(self, api_client: APIClient) -> None:
        resp = api_client.post(reverse("wallet-verify"), {}, format="json")
        assert resp.status_code == 400
