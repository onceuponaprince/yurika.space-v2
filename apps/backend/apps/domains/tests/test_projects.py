from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.domains.models import Project
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
class TestProjectCRUD:
    def test_create_assigns_authenticated_user_as_owner(self, user_a: User) -> None:
        resp = _client_for(user_a).post(
            reverse("project-list"),
            {"name": "Yurika", "description": "Vaulted domains"},
            format="json",
        )
        assert resp.status_code == 201, resp.json()
        p = Project.objects.get()
        assert p.owner == user_a

    def test_list_returns_only_my_projects(self, user_a: User, user_b: User) -> None:
        Project.objects.create(owner=user_a, name="mine")
        Project.objects.create(owner=user_b, name="theirs")
        resp = _client_for(user_a).get(reverse("project-list"))
        names = [p["name"] for p in resp.json()["results"]]
        assert names == ["mine"]

    def test_other_user_gets_404_on_detail(
        self, user_a: User, user_b: User
    ) -> None:
        p = Project.objects.create(owner=user_a, name="mine")
        resp = _client_for(user_b).get(reverse("project-detail", args=[p.id]))
        assert resp.status_code == 404

    def test_patch_updates_description_and_urls(self, user_a: User) -> None:
        p = Project.objects.create(owner=user_a, name="Yurika")
        resp = _client_for(user_a).patch(
            reverse("project-detail", args=[p.id]),
            {
                "description": "Updated thesis",
                "pitch_deck_url": "https://example.com/deck",
                "repository_url": "https://github.com/example/repo",
            },
            format="json",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["description"] == "Updated thesis"
        assert body["pitch_deck_url"] == "https://example.com/deck"

    def test_delete_hard_deletes_row(self, user_a: User) -> None:
        """Unlike Domain (which soft-deletes via WITHDRAWN), Project has
        no lifecycle status, so DELETE is a hard delete."""
        p = Project.objects.create(owner=user_a, name="Yurika")
        resp = _client_for(user_a).delete(reverse("project-detail", args=[p.id]))
        assert resp.status_code == 204
        assert not Project.objects.filter(pk=p.id).exists()

    def test_unauthenticated_returns_401(self) -> None:
        resp = APIClient().get(reverse("project-list"))
        assert resp.status_code == 401
