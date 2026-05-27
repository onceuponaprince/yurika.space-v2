from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import BaseModel


class ShardCampaign(BaseModel):
    """Fundraising campaign attached to a vaulted Domain.

    Sells fractional ownership (shards) at a fixed USD price until either
    the funding_target_usd is met (auto-COMPLETED) or shards run out.

    Lifecycle is stored on the parent Domain — VAULTED (pre-campaign) ->
    SHARDING (campaign created, founder may still edit) -> ACTIVE
    (listed on the marketplace, accepting purchases) -> COMPLETED
    (funding target reached). The campaign itself has no separate status
    field; it always reflects whatever the underlying Domain is in.
    """

    domain = models.OneToOneField(
        "domains.Domain",
        on_delete=models.PROTECT,
        related_name="campaign",
    )
    title = models.CharField(max_length=200)
    thesis = models.TextField()
    total_shards = models.BigIntegerField()
    shards_available = models.BigIntegerField()
    price_per_shard_usd = models.DecimalField(max_digits=18, decimal_places=6)
    funding_target_usd = models.DecimalField(max_digits=18, decimal_places=2)
    funding_raised_usd = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0")
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    governance_enabled = models.BooleanField(default=True)
    quorum_percentage = models.IntegerField(default=51)
    forge_stage = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "shard_campaigns"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.domain.fqdn} — {self.title}"

    @property
    def funding_percentage(self) -> float:
        if not self.funding_target_usd:
            return 0.0
        return float(self.funding_raised_usd / self.funding_target_usd * 100)

    @property
    def total_cap_usd(self) -> Decimal:
        return self.total_shards * self.price_per_shard_usd

    def clean(self) -> None:
        if self.total_shards is not None and self.total_shards <= 0:
            raise ValidationError({"total_shards": "Must be greater than zero."})
        if self.price_per_shard_usd is not None and self.price_per_shard_usd <= 0:
            raise ValidationError({"price_per_shard_usd": "Must be greater than zero."})
        if self.funding_target_usd is not None and self.funding_target_usd <= 0:
            raise ValidationError({"funding_target_usd": "Must be greater than zero."})
        if (
            self.total_shards is not None
            and self.price_per_shard_usd is not None
            and self.funding_target_usd is not None
            and self.funding_target_usd > self.total_cap_usd
        ):
            raise ValidationError(
                {"funding_target_usd": "Cannot exceed total_shards * price_per_shard_usd."}
            )
        if (
            self.shards_available is not None
            and self.total_shards is not None
            and self.shards_available > self.total_shards
        ):
            raise ValidationError({"shards_available": "Cannot exceed total_shards."})
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValidationError({"ends_at": "Must be after starts_at."})


class ShardHolding(BaseModel):
    """Records a curator's holding in a campaign.

    A holder may purchase multiple times; each purchase updates the same
    (campaign, holder) row by incrementing shards_held. The tx_hash
    records only the *most recent* purchase — full purchase history is
    out of scope for S4 and lives on-chain in S7.
    """

    campaign = models.ForeignKey(
        ShardCampaign, on_delete=models.PROTECT, related_name="holdings"
    )
    holder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shard_holdings",
    )
    shards_held = models.BigIntegerField()
    purchase_price_usd = models.DecimalField(max_digits=18, decimal_places=6)
    tx_hash = models.CharField(max_length=66, blank=True)

    class Meta:
        db_table = "shard_holdings"
        ordering = ["-created_at"]
        unique_together = [("campaign", "holder")]

    def __str__(self) -> str:
        return f"{self.holder} owns {self.shards_held} of {self.campaign}"
