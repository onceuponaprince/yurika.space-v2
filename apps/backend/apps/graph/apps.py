from __future__ import annotations

import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class GraphConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.graph"
    label = "graph"

    def ready(self) -> None:
        # Configure neomodel against the bolt URL Django already knows about.
        # Done here (not at module import time) so the env-var override
        # mechanism stays consistent with the rest of settings.
        try:
            from neomodel import get_config

            get_config().database_url = settings.NEO4J_BOLT_URL
        except ImportError:
            # neomodel <6.1 — fall back to legacy config API
            try:
                import neomodel

                neomodel.config.DATABASE_URL = settings.NEO4J_BOLT_URL
            except Exception as exc:
                logger.warning("neomodel config failed: %s", exc)
        except Exception as exc:
            logger.warning("neomodel config failed: %s", exc)

        # Wire post_save signals so Postgres writes mirror into Neo4j.
        from apps.graph import signals  # noqa: F401
