"""Wire post_save signals so Postgres writes mirror into Neo4j.

Connected from apps.graph.apps.GraphConfig.ready() so we know the
target apps (users, domains, marketplace) have already been loaded.
"""
from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.domains.models import Domain, Project
from apps.graph import sync
from apps.marketplace.models import ShardHolding
from apps.users.models import User


@receiver(post_save, sender=User)
def _sync_user_to_graph(sender, instance: User, **kwargs) -> None:
    sync.sync_user(instance)


@receiver(post_save, sender=Domain)
def _sync_domain_to_graph(sender, instance: Domain, **kwargs) -> None:
    sync.sync_domain(instance)


@receiver(post_save, sender=Project)
def _sync_project_to_graph(sender, instance: Project, **kwargs) -> None:
    sync.sync_project(instance)


@receiver(post_save, sender=ShardHolding)
def _sync_holding_to_graph(sender, instance: ShardHolding, **kwargs) -> None:
    sync.sync_holding(instance)
