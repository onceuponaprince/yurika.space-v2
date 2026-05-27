"""Tests that post_save signals correctly drive graph sync.

These tests verify the wiring (signals.py) rather than the sync
functions themselves — those have their own coverage in test_sync.py.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.domains.models import Domain, DomainStatus
from apps.graph.nodes import DomainNode, UserNode
from apps.marketplace.models import ShardCampaign, ShardHolding
from apps.users.models import User


@pytest.mark.django_db
class TestSignals:
    def test_creating_user_creates_user_node(self) -> None:
        user = User.objects.create_user(wallet_address="0x" + "c" * 40)
        node = UserNode.nodes.get_or_none(uid=str(user.id))
        assert node is not None
        assert node.wallet_address == user.wallet_address.lower()

    def test_creating_domain_creates_domain_node_and_owns_edge(self) -> None:
        user = User.objects.create_user(wallet_address="0x" + "d" * 40)
        domain = Domain.objects.create(owner=user, name="example", tld="com")

        domain_node = DomainNode.nodes.get_or_none(uid=str(domain.id))
        user_node = UserNode.nodes.get_or_none(uid=str(user.id))
        assert domain_node is not None
        assert user_node is not None
        assert user_node.owns.is_connected(domain_node)

    def test_buying_shards_creates_holds_edge(self) -> None:
        founder = User.objects.create_user(wallet_address="0x" + "e" * 40)
        curator = User.objects.create_user(wallet_address="0x" + "f" * 40)
        domain = Domain.objects.create(owner=founder, name="bigvault", tld="io")
        domain.transition_to(DomainStatus.VERIFIED)
        domain.transition_to(DomainStatus.VAULTED)
        domain.save()
        domain.transition_to(DomainStatus.SHARDING)
        domain.save()
        campaign = ShardCampaign.objects.create(
            domain=domain,
            title="x",
            thesis="x",
            total_shards=100,
            shards_available=100,
            price_per_shard_usd=Decimal("1"),
            funding_target_usd=Decimal("100"),
        )
        ShardHolding.objects.create(
            campaign=campaign,
            holder=curator,
            shards_held=10,
            purchase_price_usd=Decimal("1"),
        )

        curator_node = UserNode.nodes.get(uid=str(curator.id))
        domain_node = DomainNode.nodes.get(uid=str(domain.id))
        assert curator_node.holds.is_connected(domain_node)
