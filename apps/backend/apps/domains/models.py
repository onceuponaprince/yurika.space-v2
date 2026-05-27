from __future__ import annotations

import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import BaseModel


class DomainStatus(models.TextChoices):
    PENDING = "pending", "Pending Verification"
    VERIFIED = "verified", "Verified"
    VAULTED = "vaulted", "Vaulted"
    SHARDING = "sharding", "Sharding in Progress"
    ACTIVE = "active", "Active Campaign"
    COMPLETED = "completed", "Funding Completed"
    WITHDRAWN = "withdrawn", "Withdrawn"


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    DomainStatus.PENDING: {DomainStatus.VERIFIED, DomainStatus.WITHDRAWN},
    DomainStatus.VERIFIED: {DomainStatus.VAULTED, DomainStatus.WITHDRAWN},
    DomainStatus.VAULTED: {DomainStatus.SHARDING, DomainStatus.WITHDRAWN},
    DomainStatus.SHARDING: {DomainStatus.ACTIVE, DomainStatus.WITHDRAWN},
    DomainStatus.ACTIVE: {DomainStatus.COMPLETED, DomainStatus.WITHDRAWN},
    DomainStatus.COMPLETED: set(),
    DomainStatus.WITHDRAWN: set(),
}


def _new_verification_nonce() -> str:
    return secrets.token_urlsafe(16)


class Domain(BaseModel):
    """Web domain submitted by a founder for vaulting + fractionalization.

    Root asset node of the Yurika ecosystem: a Domain is verified (DNS
    TXT proof of control), then vaulted (locked into a YurikaVault
    contract), then sharded (ShardToken minted), then made available on
    the marketplace, then either fully funded or withdrawn.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="domains",
    )
    name = models.CharField(max_length=255, unique=True)
    tld = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=DomainStatus.choices,
        default=DomainStatus.PENDING,
        db_index=True,
    )
    verification_nonce = models.CharField(
        max_length=32,
        default=_new_verification_nonce,
        editable=False,
        help_text="Founder must publish this value in a TXT record on _yurika-verify.<fqdn>.",
    )
    ownership_proof_url = models.URLField(blank=True)
    registrar = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    vault_contract_address = models.CharField(max_length=42, blank=True)
    shard_contract_address = models.CharField(max_length=42, blank=True)
    chain_id = models.IntegerField(default=8453)

    class Meta:
        db_table = "domains"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.fqdn

    @property
    def fqdn(self) -> str:
        return f"{self.name}.{self.tld}"

    @property
    def verification_record_name(self) -> str:
        return f"_yurika-verify.{self.fqdn}"

    def transition_to(self, new_status: str) -> None:
        """Mutate self.status with a transition guard.

        Raises ValidationError if the source -> target transition is
        not in _ALLOWED_TRANSITIONS. Callers MUST save() afterwards.
        """
        allowed = _ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"Cannot transition from {self.status} to {new_status}. "
                f"Allowed: {sorted(allowed) or 'terminal state'}"
            )
        self.status = new_status


class Project(BaseModel):
    """Founder's project — pitch deck, repo, narrative.

    Created by founders before a campaign launches. The FK to a
    ShardCampaign comes in subsystem 4; for now, Projects exist as
    standalone founder-side artifacts.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="projects",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    pitch_deck_url = models.URLField(blank=True)
    repository_url = models.URLField(blank=True)
    media_url = models.URLField(blank=True)

    class Meta:
        db_table = "projects"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
