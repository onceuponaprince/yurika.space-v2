from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.domains import dns
from apps.domains.models import Domain, DomainStatus
from apps.users.models import User


@pytest.fixture
def user_a(db) -> User:
    return User.objects.create_user(wallet_address="0x" + "a" * 40)


@pytest.fixture
def user_b(db) -> User:
    return User.objects.create_user(wallet_address="0x" + "b" * 40)


@pytest.fixture
def domain(user_a: User) -> Domain:
    return Domain.objects.create(owner=user_a, name="yurika", tld="space")


def _client_for(user: User) -> APIClient:
    client = APIClient()
    access = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.mark.django_db
class TestVerifyInstructions:
    def test_returns_record_name_and_nonce(self, user_a: User, domain: Domain) -> None:
        resp = _client_for(user_a).get(
            reverse("domain-verify-instructions", args=[domain.id])
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["record_name"] == "_yurika-verify.yurika.space"
        assert body["record_value"] == domain.verification_nonce
        assert body["fqdn"] == "yurika.space"

    def test_other_user_gets_404(self, user_a: User, user_b: User, domain: Domain) -> None:
        resp = _client_for(user_b).get(
            reverse("domain-verify-instructions", args=[domain.id])
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestVerifyDomain:
    def test_happy_path_pending_to_verified(
        self, user_a: User, domain: Domain, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            dns, "lookup_txt", lambda name: [domain.verification_nonce]
        )

        resp = _client_for(user_a).post(reverse("domain-verify", args=[domain.id]))

        assert resp.status_code == 200, resp.json()
        assert resp.json()["status"] == DomainStatus.VERIFIED
        domain.refresh_from_db()
        assert domain.status == DomainStatus.VERIFIED

    def test_txt_record_missing_returns_400(
        self, user_a: User, domain: Domain, monkeypatch
    ) -> None:
        monkeypatch.setattr(dns, "lookup_txt", lambda name: [])

        resp = _client_for(user_a).post(reverse("domain-verify", args=[domain.id]))

        assert resp.status_code == 400
        body = resp.json()
        assert body["expected_value"] == domain.verification_nonce
        domain.refresh_from_db()
        assert domain.status == DomainStatus.PENDING  # not advanced

    def test_txt_record_wrong_value_returns_400(
        self, user_a: User, domain: Domain, monkeypatch
    ) -> None:
        monkeypatch.setattr(dns, "lookup_txt", lambda name: ["someone-elses-nonce"])

        resp = _client_for(user_a).post(reverse("domain-verify", args=[domain.id]))

        assert resp.status_code == 400
        domain.refresh_from_db()
        assert domain.status == DomainStatus.PENDING

    def test_dns_lookup_failure_returns_424(
        self, user_a: User, domain: Domain, monkeypatch
    ) -> None:
        def boom(name: str) -> list[str]:
            raise dns.DNSLookupError("nameserver unreachable")

        monkeypatch.setattr(dns, "lookup_txt", boom)

        resp = _client_for(user_a).post(reverse("domain-verify", args=[domain.id]))

        assert resp.status_code == 424
        domain.refresh_from_db()
        assert domain.status == DomainStatus.PENDING

    def test_already_verified_domain_returns_409(
        self, user_a: User, domain: Domain, monkeypatch
    ) -> None:
        domain.status = DomainStatus.VERIFIED
        domain.save()
        monkeypatch.setattr(
            dns, "lookup_txt", lambda name: [domain.verification_nonce]
        )

        resp = _client_for(user_a).post(reverse("domain-verify", args=[domain.id]))

        assert resp.status_code == 409

    def test_other_user_cannot_verify(
        self, user_a: User, user_b: User, domain: Domain
    ) -> None:
        resp = _client_for(user_b).post(reverse("domain-verify", args=[domain.id]))
        assert resp.status_code == 404


@pytest.mark.django_db
class TestVaultDomain:
    def test_verified_to_vaulted_writes_mock_addresses(
        self, user_a: User, domain: Domain
    ) -> None:
        domain.transition_to(DomainStatus.VERIFIED)
        domain.save()

        resp = _client_for(user_a).post(reverse("domain-vault", args=[domain.id]))

        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["status"] == DomainStatus.VAULTED
        assert body["vault_contract_address"].startswith("0x")
        assert len(body["vault_contract_address"]) == 42
        assert body["shard_contract_address"].startswith("0x")
        assert body["vault_contract_address"] != body["shard_contract_address"]

    def test_pending_domain_cannot_skip_to_vaulted(
        self, user_a: User, domain: Domain
    ) -> None:
        resp = _client_for(user_a).post(reverse("domain-vault", args=[domain.id]))
        assert resp.status_code == 409
        domain.refresh_from_db()
        assert domain.status == DomainStatus.PENDING

    def test_already_vaulted_cannot_be_revaulted(
        self, user_a: User, domain: Domain
    ) -> None:
        domain.transition_to(DomainStatus.VERIFIED)
        domain.transition_to(DomainStatus.VAULTED)
        domain.save()

        resp = _client_for(user_a).post(reverse("domain-vault", args=[domain.id]))
        assert resp.status_code == 409

    def test_other_user_cannot_vault(
        self, user_a: User, user_b: User, domain: Domain
    ) -> None:
        domain.transition_to(DomainStatus.VERIFIED)
        domain.save()
        resp = _client_for(user_b).post(reverse("domain-vault", args=[domain.id]))
        assert resp.status_code == 404


@pytest.mark.django_db
class TestS3VerifyGate:
    """The README's stated subsystem 3 verify gate:
    'Full domain lifecycle PENDING -> VAULTED'.

    This test exercises the entire happy path through HTTP, using only
    the public API surface a founder would actually use.
    """

    def test_full_lifecycle_pending_verified_vaulted(
        self, user_a: User, monkeypatch
    ) -> None:
        client = _client_for(user_a)

        # 1. Submit a new domain
        create_resp = client.post(
            reverse("domain-list"),
            {"name": "yurika", "tld": "space", "description": "rebuild"},
            format="json",
        )
        assert create_resp.status_code == 201
        domain_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == DomainStatus.PENDING

        # 2. Get the TXT-record instructions
        instr_resp = client.get(
            reverse("domain-verify-instructions", args=[domain_id])
        )
        assert instr_resp.status_code == 200
        expected_nonce = instr_resp.json()["record_value"]
        expected_record = instr_resp.json()["record_name"]
        assert expected_record == "_yurika-verify.yurika.space"

        # 3. Founder publishes the TXT record (simulated via dns mock)
        monkeypatch.setattr(dns, "lookup_txt", lambda name: [expected_nonce])

        # 4. Backend resolves DNS and verifies
        verify_resp = client.post(reverse("domain-verify", args=[domain_id]))
        assert verify_resp.status_code == 200
        assert verify_resp.json()["status"] == DomainStatus.VERIFIED

        # 5. Founder triggers vaulting; mock contract addresses are issued
        vault_resp = client.post(reverse("domain-vault", args=[domain_id]))
        assert vault_resp.status_code == 200
        vaulted = vault_resp.json()
        assert vaulted["status"] == DomainStatus.VAULTED
        assert vaulted["vault_contract_address"].startswith("0x")
        assert vaulted["shard_contract_address"].startswith("0x")
        assert vaulted["vault_contract_address"] != vaulted["shard_contract_address"]
