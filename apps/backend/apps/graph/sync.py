"""Postgres -> Neo4j sync layer.

Every function is idempotent (upserts on `uid`) and swallows Neo4j
failures: if the graph database is down or unreachable, the request
that triggered the sync still succeeds. We log a warning instead of
breaking the user-facing flow. The graph is a derived view of
Postgres truth, so a missed sync can always be reconciled later.
"""
from __future__ import annotations

import logging

from apps.graph.nodes import DomainNode, ProjectNode, UserNode

logger = logging.getLogger(__name__)


def _upsert_user(user) -> UserNode | None:
    try:
        node = UserNode.nodes.get_or_none(uid=str(user.id))
        if node is None:
            node = UserNode(
                uid=str(user.id),
                wallet_address=user.wallet_address.lower(),
            )
        else:
            node.wallet_address = user.wallet_address.lower()
        node.save()
        return node
    except Exception as exc:
        logger.warning("graph sync failed for User %s: %s", user.id, exc)
        return None


def _upsert_domain(domain) -> DomainNode | None:
    try:
        node = DomainNode.nodes.get_or_none(uid=str(domain.id))
        if node is None:
            node = DomainNode(uid=str(domain.id))
        node.name = domain.name
        node.tld = domain.tld
        node.fqdn = domain.fqdn
        node.status = domain.status
        node.save()

        owner_node = _upsert_user(domain.owner)
        if owner_node is not None and not owner_node.owns.is_connected(node):
            owner_node.owns.connect(node)

        return node
    except Exception as exc:
        logger.warning("graph sync failed for Domain %s: %s", domain.id, exc)
        return None


def _upsert_project(project) -> ProjectNode | None:
    try:
        node = ProjectNode.nodes.get_or_none(uid=str(project.id))
        if node is None:
            node = ProjectNode(uid=str(project.id))
        node.name = project.name
        node.save()

        # Wire HAS_PROJECT edge if the project is linked to a campaign
        # (Project -> Campaign -> Domain).
        campaign = project.campaign
        if campaign is not None:
            domain_node = _upsert_domain(campaign.domain)
            if domain_node is not None and not domain_node.has_project.is_connected(node):
                domain_node.has_project.connect(node)

        return node
    except Exception as exc:
        logger.warning("graph sync failed for Project %s: %s", project.id, exc)
        return None


def _upsert_holding(holding) -> None:
    """Sync a ShardHolding as a (User)-[:HOLDS]->(Domain) edge.

    The HOLDS relationship is binary (either you hold shards or you
    don't) — quantity changes don't require edge updates. Repeat
    purchases hit the same row in Postgres and the same edge here.
    """
    try:
        user_node = _upsert_user(holding.holder)
        domain_node = _upsert_domain(holding.campaign.domain)
        if (
            user_node is not None
            and domain_node is not None
            and not user_node.holds.is_connected(domain_node)
        ):
            user_node.holds.connect(domain_node)
    except Exception as exc:
        logger.warning("graph sync failed for ShardHolding %s: %s", holding.id, exc)


# Public sync API — what signals call.
sync_user = _upsert_user
sync_domain = _upsert_domain
sync_project = _upsert_project
sync_holding = _upsert_holding
