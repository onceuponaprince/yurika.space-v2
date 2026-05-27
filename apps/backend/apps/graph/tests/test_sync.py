"""Tests for the Postgres -> Neo4j sync layer.

Exercises the sync functions directly (not via signals) so failures
point at the right layer. Signal-driven sync gets its own test file.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.domains.models import Domain, DomainStatus, Project
from apps.graph import sync
from apps.graph.nodes import DomainNode, ProjectNode, UserNode
from apps.marketplace.models import ShardCampaign, ShardHolding
from apps.users.models import User


@pytest.fixture
def founder(db) -> User:
    return User.objects.create_user(wallet_address="0x" + "a" * 40)


@pytest.fixture
def curator(db) -> User:
    return User.objects.create_user(wallet_address="0x" + "b" * 40)


@pytest.fixture
def vaulted_domain(founder: User) -> Domain:
    domain = Domain.objects.create(owner=founder, name="yurika", tld="space")
    domain.transition_to(DomainStatus.VERIFIED)
    domain.transition_to(DomainStatus.VAULTED)
    domain.vault_contract_address = "0x" + "1" * 40
    domain.shard_contract_address = "0x" + "2" * 40
    domain.save()
    return domain


@pytest.fixture
def campaign(vaulted_domain: Domain) -> ShardCampaign:
    vaulted_domain.transition_to(DomainStatus.SHARDING)
    vaulted_domain.save()
    c = ShardCampaign.objects.create(
        domain=vaulted_domain,
        title="Test Campaign",
        thesis="Test thesis",
        total_shards=1000,
        shards_available=1000,
        price_per_shard_usd=Decimal("1.00"),
        funding_target_usd=Decimal("1000.00"),
    )
    vaulted_domain.transition_to(DomainStatus.ACTIVE)
    vaulted_domain.save()
    return c


@pytest.mark.django_db
class TestSyncUser:
    def test_creates_user_node(self, founder: User) -> None:
        node = sync.sync_user(founder)
        assert node is not None
        assert node.uid == str(founder.id)
        assert node.wallet_address == founder.wallet_address.lower()

    def test_idempotent_on_repeat(self, founder: User) -> None:
        sync.sync_user(founder)
        sync.sync_user(founder)
        sync.sync_user(founder)
        results = list(UserNode.nodes.filter(uid=str(founder.id)))
        assert len(results) == 1


@pytest.mark.django_db
class TestSyncDomain:
    def test_creates_domain_node_and_owns_edge(
        self, founder: User, vaulted_domain: Domain
    ) -> None:
        node = sync.sync_domain(vaulted_domain)
        assert node is not None
        assert node.fqdn == "yurika.space"
        assert node.status == DomainStatus.VAULTED

        owner_node = UserNode.nodes.get(uid=str(founder.id))
        assert owner_node.owns.is_connected(node)

    def test_idempotent_on_repeat(self, vaulted_domain: Domain) -> None:
        sync.sync_domain(vaulted_domain)
        sync.sync_domain(vaulted_domain)
        results = list(DomainNode.nodes.filter(uid=str(vaulted_domain.id)))
        assert len(results) == 1

    def test_updates_status_on_resync(self, vaulted_domain: Domain) -> None:
        sync.sync_domain(vaulted_domain)
        vaulted_domain.transition_to(DomainStatus.SHARDING)
        vaulted_domain.save()
        sync.sync_domain(vaulted_domain)
        node = DomainNode.nodes.get(uid=str(vaulted_domain.id))
        assert node.status == DomainStatus.SHARDING


@pytest.mark.django_db
class TestSyncProject:
    def test_creates_project_node_standalone(self, founder: User) -> None:
        project = Project.objects.create(owner=founder, name="my-project")
        node = sync.sync_project(project)
        assert node is not None
        assert node.name == "my-project"

    def test_wires_has_project_edge_when_linked_to_campaign(
        self, founder: User, campaign: ShardCampaign
    ) -> None:
        project = Project.objects.create(
            owner=founder, name="vault-project", campaign=campaign
        )
        node = sync.sync_project(project)
        domain_node = DomainNode.nodes.get(uid=str(campaign.domain.id))
        assert domain_node.has_project.is_connected(node)


@pytest.mark.django_db
class TestSyncHolding:
    def test_wires_holds_edge(
        self, curator: User, campaign: ShardCampaign
    ) -> None:
        holding = ShardHolding.objects.create(
            campaign=campaign,
            holder=curator,
            shards_held=50,
            purchase_price_usd=Decimal("1.00"),
        )
        sync.sync_holding(holding)

        curator_node = UserNode.nodes.get(uid=str(curator.id))
        domain_node = DomainNode.nodes.get(uid=str(campaign.domain.id))
        assert curator_node.holds.is_connected(domain_node)

    def test_repeat_purchase_does_not_create_duplicate_edge(
        self, curator: User, campaign: ShardCampaign
    ) -> None:
        holding = ShardHolding.objects.create(
            campaign=campaign,
            holder=curator,
            shards_held=50,
            purchase_price_usd=Decimal("1.00"),
        )
        sync.sync_holding(holding)
        sync.sync_holding(holding)
        sync.sync_holding(holding)

        # neomodel relationships allow multiple by default but our
        # is_connected guard prevents duplicate connect() calls.
        curator_node = UserNode.nodes.get(uid=str(curator.id))
        domain_node = DomainNode.nodes.get(uid=str(campaign.domain.id))
        rels = curator_node.holds.all_relationships(domain_node)
        assert len(rels) == 1


@pytest.mark.django_db
class TestSyncFailsSilently:
    def test_neo4j_unreachable_does_not_raise(
        self, founder: User, monkeypatch
    ) -> None:
        """If Neo4j is unreachable, sync must log a warning but not raise.

        Otherwise a Neo4j outage would break user-facing requests that
        happen to trigger a sync. We simulate the outage by patching
        UserNode.save() to raise — that's the call that actually round-
        trips to the server.
        """
        from apps.graph.nodes import UserNode as RealUserNode

        def boom(self):
            raise RuntimeError("simulated Neo4j outage")

        monkeypatch.setattr(RealUserNode, "save", boom)

        # Must not raise. Sync returns None on failure.
        result = sync.sync_user(founder)
        assert result is None
