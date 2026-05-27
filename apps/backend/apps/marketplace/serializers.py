from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.marketplace.models import ShardCampaign, ShardHolding


class ShardCampaignSerializer(serializers.ModelSerializer):
    funding_percentage = serializers.FloatField(read_only=True)
    domain_fqdn = serializers.SerializerMethodField()
    domain_status = serializers.CharField(source="domain.status", read_only=True)

    class Meta:
        model = ShardCampaign
        fields = [
            "id",
            "domain",
            "domain_fqdn",
            "domain_status",
            "title",
            "thesis",
            "total_shards",
            "shards_available",
            "price_per_shard_usd",
            "funding_target_usd",
            "funding_raised_usd",
            "funding_percentage",
            "starts_at",
            "ends_at",
            "governance_enabled",
            "quorum_percentage",
            "forge_stage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "shards_available",
            "funding_raised_usd",
            "funding_percentage",
            "domain_fqdn",
            "domain_status",
            "created_at",
            "updated_at",
        ]

    def get_domain_fqdn(self, obj: ShardCampaign) -> str:
        return obj.domain.fqdn


class ShardCampaignCreateSerializer(ShardCampaignSerializer):
    """Founder-facing create surface — domain field accepted, shards_available
    is computed server-side as total_shards on create."""

    def validate(self, attrs):
        total = attrs.get("total_shards")
        price = attrs.get("price_per_shard_usd")
        target = attrs.get("funding_target_usd")
        if total is not None and total <= 0:
            raise serializers.ValidationError({"total_shards": "Must be > 0."})
        if price is not None and price <= 0:
            raise serializers.ValidationError({"price_per_shard_usd": "Must be > 0."})
        if target is not None and target <= 0:
            raise serializers.ValidationError({"funding_target_usd": "Must be > 0."})
        if total and price and target and target > total * price:
            raise serializers.ValidationError(
                {"funding_target_usd": "Cannot exceed total_shards * price_per_shard_usd."}
            )
        return attrs


class BuySharesRequestSerializer(serializers.Serializer):
    shards = serializers.IntegerField(min_value=1)


class ShardHoldingSerializer(serializers.ModelSerializer):
    campaign_title = serializers.CharField(source="campaign.title", read_only=True)
    domain_fqdn = serializers.SerializerMethodField()

    class Meta:
        model = ShardHolding
        fields = [
            "id",
            "campaign",
            "campaign_title",
            "domain_fqdn",
            "shards_held",
            "purchase_price_usd",
            "tx_hash",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_domain_fqdn(self, obj: ShardHolding) -> str:
        return obj.campaign.domain.fqdn
