from __future__ import annotations

import uuid

from django.db import models


class BaseModel(models.Model):
    """Abstract base — UUID primary key, created_at, updated_at.

    Every domain-layer model inherits from this rather than Django's
    default auto-incrementing integer PKs because the on-chain side
    (vault contracts, shard tokens) references entities by UUID, not
    by sequential ID.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
