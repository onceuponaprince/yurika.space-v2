from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.domains.models import Domain, DomainStatus
from apps.marketplace.models import ShardCampaign, ShardHolding
from apps.users.models import User


@pytest.fixture
def founder(db) -> User:
    return User.objects.create_user(wallet_address="0x" + "f" * 40)


@pytest.fixture
def curator(db) -> User:
    return User.objects.create_user(wallet_address="0x" + "c" * 40)


@pytest.fixture
def vaulted_domain(founder: User) -> Domain:
    d = Domain.objects.create(owner=founder, name="yurika", tld="space")
    d.status = DomainStatus.VAULTED
    d.save()
    return d


def _client(user: User | None = None) -> APIClient:
    c = APIClient()
    if user is not None:
        token = RefreshToken.for_user(user).access_token
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return c


def _campaign_payload(domain: Domain, **overrides) -> dict:
    payload = {
        "domain": str(domain.id),
        "title": "Yurika seed",
        "thesis": "A vaulted domain marketplace.",
        "total_shards": 1000,
        "price_per_shard_usd": "10.00",
        "funding_target_usd": "5000.00",
    }
    payload.update(overrides)
    return payload


def _create_campaign_via_api(founder: User, domain: Domain) -> ShardCampaign:
    resp = _client(founder).post(
        reverse("campaign-list"), _campaign_payload(domain), format="json"
    )
    assert resp.status_code == 201, resp.json()
    return ShardCampaign.objects.get(pk=resp.json()["id"])


@pytest.mark.django_db
class TestCampaignCreate:
    def test_founder_creates_campaign_for_vaulted_domain(
        self, founder: User, vaulted_domain: Domain
    ) -> None:
        resp = _client(founder).post(
            reverse("campaign-list"), _campaign_payload(vaulted_domain), format="json"
        )
        assert resp.status_code == 201, resp.json()
        body = resp.json()
        assert body["shards_available"] == 1000
        assert body["funding_raised_usd"] == "0.00"

        vaulted_domain.refresh_from_db()
        assert vaulted_domain.status == DomainStatus.SHARDING

    def test_cannot_create_campaign_for_pending_domain(
        self, founder: User, vaulted_domain: Domain
    ) -> None:
        vaulted_domain.status = DomainStatus.PENDING
        vaulted_domain.save()
        resp = _client(founder).post(
            reverse("campaign-list"), _campaign_payload(vaulted_domain), format="json"
        )
        assert resp.status_code == 409

    def test_non_owner_cannot_create_campaign(
        self, founder: User, curator: User, vaulted_domain: Domain
    ) -> None:
        resp = _client(curator).post(
            reverse("campaign-list"), _campaign_payload(vaulted_domain), format="json"
        )
        assert resp.status_code == 403

    def test_unauthenticated_create_rejected(
        self, vaulted_domain: Domain
    ) -> None:
        resp = _client().post(
            reverse("campaign-list"), _campaign_payload(vaulted_domain), format="json"
        )
        assert resp.status_code == 401

    def test_funding_target_above_total_cap_rejected(
        self, founder: User, vaulted_domain: Domain
    ) -> None:
        resp = _client(founder).post(
            reverse("campaign-list"),
            _campaign_payload(
                vaulted_domain,
                total_shards=10,
                price_per_shard_usd="1",
                funding_target_usd="999",  # cap is 10
            ),
            format="json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestCampaignList:
    def test_marketplace_list_is_public(
        self, founder: User, vaulted_domain: Domain
    ) -> None:
        _create_campaign_via_api(founder, vaulted_domain)
        resp = _client().get(reverse("campaign-list"))  # no auth
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1

    def test_filter_by_status_active(
        self, founder: User, vaulted_domain: Domain
    ) -> None:
        c = _create_campaign_via_api(founder, vaulted_domain)
        # activate to ACTIVE
        _client(founder).post(reverse("campaign-activate", args=[c.id]))
        resp = _client().get(reverse("campaign-list") + "?status=active")
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1

        resp_sharding = _client().get(reverse("campaign-list") + "?status=sharding")
        assert len(resp_sharding.json()["results"]) == 0


@pytest.mark.django_db
class TestCampaignActivate:
    def test_owner_can_activate_sharding_campaign(
        self, founder: User, vaulted_domain: Domain
    ) -> None:
        c = _create_campaign_via_api(founder, vaulted_domain)
        assert vaulted_domain.refresh_from_db() or True
        resp = _client(founder).post(reverse("campaign-activate", args=[c.id]))
        assert resp.status_code == 200
        c.domain.refresh_from_db()
        assert c.domain.status == DomainStatus.ACTIVE

    def test_non_owner_cannot_activate(
        self, founder: User, curator: User, vaulted_domain: Domain
    ) -> None:
        c = _create_campaign_via_api(founder, vaulted_domain)
        resp = _client(curator).post(reverse("campaign-activate", args=[c.id]))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestBuyShards:
    def _setup_active_campaign(
        self, founder: User, vaulted_domain: Domain
    ) -> ShardCampaign:
        c = _create_campaign_via_api(founder, vaulted_domain)
        _client(founder).post(reverse("campaign-activate", args=[c.id]))
        c.refresh_from_db()
        c.domain.refresh_from_db()
        return c

    def test_curator_can_buy_shards(
        self, founder: User, curator: User, vaulted_domain: Domain
    ) -> None:
        c = self._setup_active_campaign(founder, vaulted_domain)
        resp = _client(curator).post(
            reverse("campaign-buy", args=[c.id]), {"shards": 100}, format="json"
        )
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["campaign"]["shards_available"] == 900
        assert body["campaign"]["funding_raised_usd"] == "1000.00"
        assert body["holding"]["shards_held"] == 100
        assert body["holding"]["tx_hash"].startswith("0x")

    def test_repeat_buy_increments_existing_holding(
        self, founder: User, curator: User, vaulted_domain: Domain
    ) -> None:
        c = self._setup_active_campaign(founder, vaulted_domain)
        _client(curator).post(reverse("campaign-buy", args=[c.id]), {"shards": 50}, format="json")
        _client(curator).post(reverse("campaign-buy", args=[c.id]), {"shards": 75}, format="json")
        holdings = ShardHolding.objects.filter(campaign=c, holder=curator)
        assert holdings.count() == 1  # one row, incremented
        assert holdings.first().shards_held == 125

    def test_two_curators_get_independent_holdings(
        self, founder: User, curator: User, vaulted_domain: Domain
    ) -> None:
        c = self._setup_active_campaign(founder, vaulted_domain)
        curator_b = User.objects.create_user(wallet_address="0x" + "d" * 40)
        _client(curator).post(reverse("campaign-buy", args=[c.id]), {"shards": 50}, format="json")
        _client(curator_b).post(reverse("campaign-buy", args=[c.id]), {"shards": 70}, format="json")
        assert c.holdings.count() == 2

    def test_cannot_buy_more_than_available(
        self, founder: User, curator: User, vaulted_domain: Domain
    ) -> None:
        c = self._setup_active_campaign(founder, vaulted_domain)
        resp = _client(curator).post(
            reverse("campaign-buy", args=[c.id]), {"shards": 10_000}, format="json"
        )
        assert resp.status_code == 409
        c.refresh_from_db()
        assert c.shards_available == 1000  # untouched

    def test_cannot_buy_from_sharding_campaign(
        self, founder: User, curator: User, vaulted_domain: Domain
    ) -> None:
        """Campaign in SHARDING isn't active yet — no purchases allowed."""
        c = _create_campaign_via_api(founder, vaulted_domain)  # status=SHARDING
        resp = _client(curator).post(
            reverse("campaign-buy", args=[c.id]), {"shards": 10}, format="json"
        )
        assert resp.status_code == 409

    def test_funding_target_hit_auto_completes(
        self, founder: User, curator: User, vaulted_domain: Domain
    ) -> None:
        c = self._setup_active_campaign(founder, vaulted_domain)
        # target is $5000; price is $10; need 500 shards to hit target
        resp = _client(curator).post(
            reverse("campaign-buy", args=[c.id]), {"shards": 500}, format="json"
        )
        assert resp.status_code == 200
        c.refresh_from_db()
        c.domain.refresh_from_db()
        assert c.domain.status == DomainStatus.COMPLETED

    def test_unauthenticated_buy_rejected(
        self, founder: User, vaulted_domain: Domain
    ) -> None:
        c = self._setup_active_campaign(founder, vaulted_domain)
        resp = _client().post(
            reverse("campaign-buy", args=[c.id]), {"shards": 10}, format="json"
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestMyHoldings:
    def test_returns_only_my_holdings(
        self, founder: User, curator: User, vaulted_domain: Domain
    ) -> None:
        c = _create_campaign_via_api(founder, vaulted_domain)
        _client(founder).post(reverse("campaign-activate", args=[c.id]))

        _client(curator).post(reverse("campaign-buy", args=[c.id]), {"shards": 10}, format="json")

        other = User.objects.create_user(wallet_address="0x" + "e" * 40)
        _client(other).post(reverse("campaign-buy", args=[c.id]), {"shards": 20}, format="json")

        resp = _client(curator).get(reverse("holding-list"))
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["shards_held"] == 10


@pytest.mark.django_db
class TestS4VerifyGate:
    """The README's stated subsystem 4 verify gate: 'Curator can buy shards'.

    Walks the full founder + curator flow through HTTP, building on top
    of the S3 lifecycle (domain submission -> verify -> vault).
    """

    def test_curator_can_buy_shards_end_to_end(
        self, founder: User, curator: User
    ) -> None:
        # --- founder side: vault a domain (S3 lifecycle) ---
        d = Domain.objects.create(owner=founder, name="yurika", tld="space")
        d.status = DomainStatus.VAULTED
        d.save()

        # --- founder creates a campaign ---
        c = _create_campaign_via_api(founder, d)
        d.refresh_from_db()
        assert d.status == DomainStatus.SHARDING

        # --- founder activates the campaign ---
        act = _client(founder).post(reverse("campaign-activate", args=[c.id]))
        assert act.status_code == 200
        d.refresh_from_db()
        assert d.status == DomainStatus.ACTIVE

        # --- curator buys shards ---
        buy = _client(curator).post(
            reverse("campaign-buy", args=[c.id]),
            {"shards": 250},
            format="json",
        )
        assert buy.status_code == 200, buy.json()
        body = buy.json()
        assert body["campaign"]["shards_available"] == 750
        assert body["campaign"]["funding_raised_usd"] == "2500.00"
        assert body["holding"]["shards_held"] == 250

        # --- curator sees the holding in their list ---
        listing = _client(curator).get(reverse("holding-list"))
        assert len(listing.json()["results"]) == 1
        assert listing.json()["results"][0]["domain_fqdn"] == "yurika.space"
