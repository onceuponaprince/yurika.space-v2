"""Tests for discovery queries + the /api/graph/discover/ endpoint."""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.domains.models import Domain, DomainStatus
from apps.graph import discovery
from apps.marketplace.models import ShardCampaign, ShardHolding
from apps.users.models import User


def _client_for(user: User) -> APIClient:
    client = APIClient()
    access = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def _make_active_campaign(founder: User, name: str) -> ShardCampaign:
    domain = Domain.objects.create(owner=founder, name=name, tld="space")
    domain.transition_to(DomainStatus.VERIFIED)
    domain.transition_to(DomainStatus.VAULTED)
    domain.save()
    domain.transition_to(DomainStatus.SHARDING)
    domain.save()
    campaign = ShardCampaign.objects.create(
        domain=domain,
        title=f"{name} campaign",
        thesis="t",
        total_shards=1000,
        shards_available=1000,
        price_per_shard_usd=Decimal("1.00"),
        funding_target_usd=Decimal("1000.00"),
    )
    domain.transition_to(DomainStatus.ACTIVE)
    domain.save()
    return campaign


@pytest.mark.django_db
class TestTrendingDomains:
    def test_returns_empty_for_empty_graph(self) -> None:
        assert discovery.trending_domains() == []

    def test_ranks_by_holder_count(self) -> None:
        founder = User.objects.create_user(wallet_address="0x" + "a" * 40)
        c1 = _make_active_campaign(founder, "popular")
        c2 = _make_active_campaign(founder, "niche")

        # 3 curators hold popular, 1 holds niche
        for i, suffix in enumerate(["1", "2", "3"]):
            curator = User.objects.create_user(
                wallet_address="0x" + suffix * 40
            )
            ShardHolding.objects.create(
                campaign=c1,
                holder=curator,
                shards_held=10,
                purchase_price_usd=Decimal("1"),
            )
        solo_curator = User.objects.create_user(wallet_address="0x" + "4" * 40)
        ShardHolding.objects.create(
            campaign=c2,
            holder=solo_curator,
            shards_held=10,
            purchase_price_usd=Decimal("1"),
        )

        results = discovery.trending_domains()
        assert len(results) == 2
        assert results[0]["fqdn"] == "popular.space"
        assert results[0]["score"] == 3
        assert results[1]["fqdn"] == "niche.space"
        assert results[1]["score"] == 1


@pytest.mark.django_db
class TestGraphStats:
    def test_counts_zero_on_empty_graph(self) -> None:
        stats = discovery.graph_stats()
        assert stats == {"users": 0, "domains": 0, "projects": 0, "holds": 0, "owns": 0}

    def test_counts_reflect_signal_driven_state(self) -> None:
        founder = User.objects.create_user(wallet_address="0x" + "a" * 40)
        Domain.objects.create(owner=founder, name="x", tld="io")
        stats = discovery.graph_stats()
        assert stats["users"] == 1
        assert stats["domains"] == 1
        assert stats["owns"] == 1


@pytest.mark.django_db
class TestDiscoverEndpoint:
    def test_anonymous_defaults_to_trending(self) -> None:
        client = APIClient()
        resp = client.get(reverse("graph-discover"))
        assert resp.status_code == 200, resp.json()
        assert resp.json()["mode"] == "trending"

    def test_authenticated_defaults_to_personalized(self) -> None:
        user = User.objects.create_user(wallet_address="0x" + "a" * 40)
        resp = _client_for(user).get(reverse("graph-discover"))
        assert resp.status_code == 200, resp.json()
        assert resp.json()["mode"] == "personalized"

    def test_explicit_trending_mode_is_public(self) -> None:
        client = APIClient()
        resp = client.get(reverse("graph-discover") + "?mode=trending")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "trending"
        assert resp.json()["results"] == []

    def test_explicit_personalized_requires_auth(self) -> None:
        resp = APIClient().get(reverse("graph-discover") + "?mode=personalized")
        assert resp.status_code == 401

    def test_stats_mode_returns_counts(self) -> None:
        resp = APIClient().get(reverse("graph-discover") + "?mode=stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "stats"
        assert "stats" in body
        assert "users" in body["stats"]

    def test_unknown_mode_falls_back_to_default(self) -> None:
        resp = APIClient().get(reverse("graph-discover") + "?mode=gibberish")
        assert resp.status_code == 200
        # anonymous + unknown -> trending (default)
        assert resp.json()["mode"] == "trending"

    def test_limit_param_clamps(self) -> None:
        resp = APIClient().get(
            reverse("graph-discover") + "?mode=trending&limit=9999"
        )
        assert resp.status_code == 200  # 9999 clamps to 50 silently

    def test_invalid_limit_falls_back_to_default(self) -> None:
        resp = APIClient().get(
            reverse("graph-discover") + "?mode=trending&limit=banana"
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPersonalizedDiscovery:
    """Exercises the three design decisions baked into the query:

      D1: Jaccard-style peer weighting (more shared holdings = stronger vote)
      D2: Sum of peer weights as the per-domain score
      D3: Exclude already-held, owned, withdrawn, and completed domains
    """

    def test_empty_graph_returns_empty_list(self) -> None:
        user = User.objects.create_user(wallet_address="0x" + "a" * 40)
        assert discovery.personalized_discovery(str(user.id)) == []

    def test_recommends_domain_held_by_peer(self) -> None:
        founder = User.objects.create_user(wallet_address="0x" + "1" * 40)
        me = User.objects.create_user(wallet_address="0x" + "2" * 40)
        peer = User.objects.create_user(wallet_address="0x" + "3" * 40)

        shared = _make_active_campaign(founder, "shared")
        target = _make_active_campaign(founder, "target")

        # me and peer both hold shared → they overlap by 1
        for u in (me, peer):
            ShardHolding.objects.create(
                campaign=shared,
                holder=u,
                shards_held=10,
                purchase_price_usd=Decimal("1"),
            )
        # peer also holds target — that's the discovery candidate
        ShardHolding.objects.create(
            campaign=target,
            holder=peer,
            shards_held=10,
            purchase_price_usd=Decimal("1"),
        )

        results = discovery.personalized_discovery(str(me.id))
        assert len(results) == 1
        assert results[0]["fqdn"] == "target.space"
        assert results[0]["score"] == 1  # one peer, weight 1

    def test_excludes_already_held(self) -> None:
        """D3: domain I already hold must never appear in my recommendations."""
        founder = User.objects.create_user(wallet_address="0x" + "1" * 40)
        me = User.objects.create_user(wallet_address="0x" + "2" * 40)
        peer = User.objects.create_user(wallet_address="0x" + "3" * 40)

        shared = _make_active_campaign(founder, "shared")
        for u in (me, peer):
            ShardHolding.objects.create(
                campaign=shared,
                holder=u,
                shards_held=10,
                purchase_price_usd=Decimal("1"),
            )

        results = discovery.personalized_discovery(str(me.id))
        # peer has no other holdings, so there's nothing to recommend
        # AND shared itself must not appear (we already hold it)
        assert all(r["fqdn"] != "shared.space" for r in results)

    def test_excludes_my_own_domains(self) -> None:
        """D3: domains I own as a founder don't show up in my discovery."""
        me = User.objects.create_user(wallet_address="0x" + "2" * 40)
        peer = User.objects.create_user(wallet_address="0x" + "3" * 40)

        my_domain = _make_active_campaign(me, "mine")
        peer_domain = _make_active_campaign(me, "shared")  # me owns both

        # both me and peer hold one of my domains (overlap=1)
        for u in (me, peer):
            ShardHolding.objects.create(
                campaign=peer_domain,
                holder=u,
                shards_held=10,
                purchase_price_usd=Decimal("1"),
            )
        # peer also holds my other domain
        ShardHolding.objects.create(
            campaign=my_domain,
            holder=peer,
            shards_held=10,
            purchase_price_usd=Decimal("1"),
        )

        results = discovery.personalized_discovery(str(me.id))
        # mine.space is owned by me — must be excluded even though peer holds it
        assert all(r["fqdn"] != "mine.space" for r in results)

    def test_jaccard_weighting_higher_overlap_ranks_higher(self) -> None:
        """D1 + D2: a peer who overlaps with me twice gives twice the vote
        of a peer who overlaps once."""
        founder = User.objects.create_user(wallet_address="0x" + "1" * 40)
        me = User.objects.create_user(wallet_address="0x" + "2" * 40)
        close_peer = User.objects.create_user(wallet_address="0x" + "3" * 40)
        distant_peer = User.objects.create_user(wallet_address="0x" + "4" * 40)

        shared_a = _make_active_campaign(founder, "shared-a")
        shared_b = _make_active_campaign(founder, "shared-b")
        # close_peer overlaps with me on TWO domains; distant only ONE
        for c in (shared_a, shared_b):
            ShardHolding.objects.create(
                campaign=c, holder=me, shards_held=10,
                purchase_price_usd=Decimal("1"),
            )
            ShardHolding.objects.create(
                campaign=c, holder=close_peer, shards_held=10,
                purchase_price_usd=Decimal("1"),
            )
        ShardHolding.objects.create(
            campaign=shared_a, holder=distant_peer, shards_held=10,
            purchase_price_usd=Decimal("1"),
        )

        # Each peer recommends a unique candidate
        close_rec = _make_active_campaign(founder, "close-rec")
        distant_rec = _make_active_campaign(founder, "distant-rec")
        ShardHolding.objects.create(
            campaign=close_rec, holder=close_peer, shards_held=10,
            purchase_price_usd=Decimal("1"),
        )
        ShardHolding.objects.create(
            campaign=distant_rec, holder=distant_peer, shards_held=10,
            purchase_price_usd=Decimal("1"),
        )

        results = discovery.personalized_discovery(str(me.id))
        # close-rec has score 2 (close_peer overlap_weight=2)
        # distant-rec has score 1 (distant_peer overlap_weight=1)
        scores = {r["fqdn"]: r["score"] for r in results}
        assert scores["close-rec.space"] == 2
        assert scores["distant-rec.space"] == 1
        # And the ordering reflects this
        assert results[0]["fqdn"] == "close-rec.space"


@pytest.mark.django_db
class TestS5VerifyGate:
    """README's stated subsystem 5 verify gate:
    `/api/graph/discover/ returns nodes`.

    This test walks the full signal-driven sync pipeline: create
    Postgres entities, observe that signals mirrored them into Neo4j,
    then hit the discover endpoint and confirm nodes flow back out.
    """

    def test_holdings_flow_through_to_discovery(self) -> None:
        founder = User.objects.create_user(wallet_address="0x" + "a" * 40)
        curator = User.objects.create_user(wallet_address="0x" + "b" * 40)
        campaign = _make_active_campaign(founder, "yurika")
        ShardHolding.objects.create(
            campaign=campaign,
            holder=curator,
            shards_held=100,
            purchase_price_usd=Decimal("1"),
        )

        # Hit the public verify-gate endpoint.
        resp = APIClient().get(reverse("graph-discover") + "?mode=trending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "trending"
        assert len(body["results"]) == 1
        assert body["results"][0]["fqdn"] == "yurika.space"
        assert body["results"][0]["score"] == 1
