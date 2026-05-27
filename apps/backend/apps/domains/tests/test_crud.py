from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.domains.models import Domain, DomainStatus
from apps.users.models import User


@pytest.fixture
def user_a(db) -> User:
    return User.objects.create_user(wallet_address="0x" + "a" * 40)


@pytest.fixture
def user_b(db) -> User:
    return User.objects.create_user(wallet_address="0x" + "b" * 40)


def _client_for(user: User) -> APIClient:
    client = APIClient()
    access = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.mark.django_db
class TestDomainList:
    def test_returns_empty_list_when_no_domains(self, user_a: User) -> None:
        resp = _client_for(user_a).get(reverse("domain-list"))
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_returns_only_my_domains(self, user_a: User, user_b: User) -> None:
        Domain.objects.create(owner=user_a, name="mine", tld="com")
        Domain.objects.create(owner=user_b, name="theirs", tld="com")
        resp = _client_for(user_a).get(reverse("domain-list"))
        assert resp.status_code == 200
        names = [d["name"] for d in resp.json()["results"]]
        assert names == ["mine"]

    def test_unauthenticated_returns_401(self) -> None:
        resp = APIClient().get(reverse("domain-list"))
        assert resp.status_code == 401


@pytest.mark.django_db
class TestDomainCreate:
    def test_creates_with_pending_status_by_default(self, user_a: User) -> None:
        resp = _client_for(user_a).post(
            reverse("domain-list"),
            {"name": "yurika", "tld": "space", "description": "the asset"},
            format="json",
        )
        assert resp.status_code == 201, resp.json()
        body = resp.json()
        assert body["status"] == DomainStatus.PENDING
        assert body["verification_record_name"] == "_yurika-verify.yurika.space"

    def test_client_cannot_force_status_at_creation(self, user_a: User) -> None:
        resp = _client_for(user_a).post(
            reverse("domain-list"),
            {"name": "yurika", "tld": "space", "status": DomainStatus.VAULTED},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == DomainStatus.PENDING  # read-only, ignored

    def test_duplicate_name_rejected(self, user_a: User) -> None:
        Domain.objects.create(owner=user_a, name="yurika", tld="space")
        resp = _client_for(user_a).post(
            reverse("domain-list"),
            {"name": "yurika", "tld": "com"},
            format="json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestDomainDetail:
    def test_owner_can_retrieve(self, user_a: User) -> None:
        d = Domain.objects.create(owner=user_a, name="yurika", tld="space")
        resp = _client_for(user_a).get(reverse("domain-detail", args=[d.id]))
        assert resp.status_code == 200
        assert resp.json()["name"] == "yurika"

    def test_other_user_gets_404_not_403(self, user_a: User, user_b: User) -> None:
        """A 403 would leak the existence of someone else's domain. 404 is correct."""
        d = Domain.objects.create(owner=user_a, name="yurika", tld="space")
        resp = _client_for(user_b).get(reverse("domain-detail", args=[d.id]))
        assert resp.status_code == 404

    def test_patch_updates_mutable_fields(self, user_a: User) -> None:
        d = Domain.objects.create(owner=user_a, name="yurika", tld="space")
        resp = _client_for(user_a).patch(
            reverse("domain-detail", args=[d.id]),
            {"description": "updated", "registrar": "Namecheap"},
            format="json",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["description"] == "updated"
        assert body["registrar"] == "Namecheap"

    def test_patch_cannot_force_status(self, user_a: User) -> None:
        d = Domain.objects.create(owner=user_a, name="yurika", tld="space")
        resp = _client_for(user_a).patch(
            reverse("domain-detail", args=[d.id]),
            {"status": DomainStatus.VAULTED},
            format="json",
        )
        d.refresh_from_db()
        assert d.status == DomainStatus.PENDING  # ignored — status is read-only on PATCH

    def test_delete_transitions_to_withdrawn(self, user_a: User) -> None:
        d = Domain.objects.create(owner=user_a, name="yurika", tld="space")
        resp = _client_for(user_a).delete(reverse("domain-detail", args=[d.id]))
        assert resp.status_code == 200
        d.refresh_from_db()
        assert d.status == DomainStatus.WITHDRAWN
        # Soft delete — row still exists
        assert Domain.objects.filter(pk=d.id).exists()
