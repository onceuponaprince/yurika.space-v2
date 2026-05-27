from __future__ import annotations

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    cache.clear()
    return APIClient()


class TestNonceEndpoint:
    def test_returns_message_and_nonce_for_valid_address(self, api_client: APIClient) -> None:
        url = reverse("wallet-nonce")
        resp = api_client.get(url, {"address": "0x" + "a" * 40})
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        assert "nonce" in body
        assert body["nonce"] in body["message"]
        assert "wants you to sign in with your Ethereum account" in body["message"]
        assert "Chain ID: 8453" in body["message"]

    def test_accepts_checksum_address(self, api_client: APIClient) -> None:
        url = reverse("wallet-nonce")
        # Real EIP-55 checksum address (mixed case)
        resp = api_client.get(url, {"address": "0xAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAaAa"})
        assert resp.status_code == 200

    def test_rejects_malformed_address(self, api_client: APIClient) -> None:
        url = reverse("wallet-nonce")
        resp = api_client.get(url, {"address": "not-a-wallet"})
        assert resp.status_code == 400

    def test_rejects_missing_address(self, api_client: APIClient) -> None:
        url = reverse("wallet-nonce")
        resp = api_client.get(url)
        assert resp.status_code == 400

    def test_two_calls_return_different_nonces(self, api_client: APIClient) -> None:
        url = reverse("wallet-nonce")
        addr = "0x" + "a" * 40
        n1 = api_client.get(url, {"address": addr}).json()["nonce"]
        n2 = api_client.get(url, {"address": addr}).json()["nonce"]
        assert n1 != n2
