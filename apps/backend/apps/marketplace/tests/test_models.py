from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.domains.models import Domain
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
    d.status = "vaulted"
    d.save()
    return d


def _make_campaign(domain: Domain, **overrides) -> ShardCampaign:
    defaults = dict(
        domain=domain,
        title="Yurika seed",
        thesis="A vaulted domain marketplace.",
        total_shards=1_000,
        shards_available=1_000,
        price_per_shard_usd=Decimal("10.00"),
        funding_target_usd=Decimal("5000.00"),
    )
    defaults.update(overrides)
    return ShardCampaign.objects.create(**defaults)


@pytest.mark.django_db
class TestShardCampaignDefaults:
    def test_create_with_minimal_fields(self, vaulted_domain: Domain) -> None:
        c = _make_campaign(vaulted_domain)
        assert c.funding_raised_usd == Decimal("0.00")
        assert c.governance_enabled is True
        assert c.quorum_percentage == 51

    def test_one_campaign_per_domain(self, vaulted_domain: Domain) -> None:
        _make_campaign(vaulted_domain)
        with pytest.raises(IntegrityError), transaction.atomic():
            _make_campaign(vaulted_domain, title="duplicate")

    def test_funding_percentage_zero_when_no_raise(self, vaulted_domain: Domain) -> None:
        c = _make_campaign(vaulted_domain)
        assert c.funding_percentage == 0.0

    def test_funding_percentage_at_halfway(self, vaulted_domain: Domain) -> None:
        c = _make_campaign(vaulted_domain, funding_target_usd=Decimal("1000"))
        c.funding_raised_usd = Decimal("500")
        c.save()
        assert c.funding_percentage == 50.0


@pytest.mark.django_db
class TestShardCampaignValidation:
    def test_zero_total_shards_rejected(self, vaulted_domain: Domain) -> None:
        c = ShardCampaign(
            domain=vaulted_domain, title="t", thesis="t",
            total_shards=0, shards_available=0,
            price_per_shard_usd=Decimal("1"), funding_target_usd=Decimal("1"),
        )
        with pytest.raises(ValidationError):
            c.full_clean()

    def test_zero_price_rejected(self, vaulted_domain: Domain) -> None:
        c = ShardCampaign(
            domain=vaulted_domain, title="t", thesis="t",
            total_shards=10, shards_available=10,
            price_per_shard_usd=Decimal("0"), funding_target_usd=Decimal("1"),
        )
        with pytest.raises(ValidationError):
            c.full_clean()

    def test_target_exceeding_total_cap_rejected(self, vaulted_domain: Domain) -> None:
        """funding_target must be <= total_shards * price_per_shard."""
        c = ShardCampaign(
            domain=vaulted_domain, title="t", thesis="t",
            total_shards=100, shards_available=100,
            price_per_shard_usd=Decimal("1"),
            funding_target_usd=Decimal("999999"),
        )
        with pytest.raises(ValidationError):
            c.full_clean()

    def test_shards_available_cannot_exceed_total(self, vaulted_domain: Domain) -> None:
        c = ShardCampaign(
            domain=vaulted_domain, title="t", thesis="t",
            total_shards=100, shards_available=101,
            price_per_shard_usd=Decimal("1"), funding_target_usd=Decimal("100"),
        )
        with pytest.raises(ValidationError):
            c.full_clean()


@pytest.mark.django_db
class TestShardHolding:
    def test_unique_per_campaign_holder_pair(
        self, vaulted_domain: Domain, curator: User
    ) -> None:
        campaign = _make_campaign(vaulted_domain)
        ShardHolding.objects.create(
            campaign=campaign, holder=curator,
            shards_held=10, purchase_price_usd=Decimal("10"),
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            ShardHolding.objects.create(
                campaign=campaign, holder=curator,
                shards_held=5, purchase_price_usd=Decimal("10"),
            )

    def test_different_holders_can_hold_same_campaign(
        self, vaulted_domain: Domain, founder: User, curator: User
    ) -> None:
        campaign = _make_campaign(vaulted_domain)
        ShardHolding.objects.create(
            campaign=campaign, holder=founder,
            shards_held=10, purchase_price_usd=Decimal("10"),
        )
        ShardHolding.objects.create(
            campaign=campaign, holder=curator,
            shards_held=5, purchase_price_usd=Decimal("10"),
        )
        assert campaign.holdings.count() == 2
