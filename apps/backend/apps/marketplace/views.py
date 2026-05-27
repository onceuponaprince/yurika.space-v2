from __future__ import annotations

import logging
import secrets
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.domains.models import Domain, DomainStatus
from apps.marketplace.models import ShardCampaign, ShardHolding
from apps.marketplace.permissions import IsCampaignDomainOwner
from apps.marketplace.serializers import (
    BuySharesRequestSerializer,
    ShardCampaignCreateSerializer,
    ShardCampaignSerializer,
    ShardHoldingSerializer,
)

logger = logging.getLogger(__name__)


def _mock_tx_hash() -> str:
    """Deterministically-shaped 32-byte hex hash for S4. Real on-chain
    tx hashes arrive in S7."""
    return "0x" + secrets.token_hex(32)


class CampaignListCreate(generics.ListCreateAPIView):
    """GET — public marketplace listing. POST — founder creates a campaign
    for their own VAULTED domain (auto-transitions domain to SHARDING)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = ShardCampaign.objects.select_related("domain", "domain__owner")
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(domain__status=status_param)
        return qs

    def get_serializer_class(self):
        return (
            ShardCampaignCreateSerializer
            if self.request.method == "POST"
            else ShardCampaignSerializer
        )

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        domain: Domain = serializer.validated_data["domain"]

        if domain.owner_id != request.user.id:
            return Response(
                {"detail": "You can only create a campaign for a domain you own."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if domain.status != DomainStatus.VAULTED:
            return Response(
                {
                    "detail": f"Domain must be in 'vaulted' status to start a campaign "
                    f"(currently '{domain.status}')."
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Initialize shards_available to total_shards
        campaign = serializer.save(
            shards_available=serializer.validated_data["total_shards"],
            funding_raised_usd=Decimal("0"),
        )

        # Move the domain to SHARDING
        try:
            domain.transition_to(DomainStatus.SHARDING)
            domain.save()
        except DjangoValidationError:
            campaign.delete()
            return Response(
                {"detail": "Domain status changed underneath us; please retry."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            ShardCampaignSerializer(campaign).data, status=status.HTTP_201_CREATED
        )


class CampaignDetail(generics.RetrieveUpdateAPIView):
    """Public read; owner-only update. Only editable while domain is in
    SHARDING (pre-activation)."""

    queryset = ShardCampaign.objects.select_related("domain", "domain__owner")
    serializer_class = ShardCampaignSerializer

    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT"):
            return [IsAuthenticated(), IsCampaignDomainOwner()]
        return [AllowAny()]

    def update(self, request: Request, *args, **kwargs) -> Response:
        campaign: ShardCampaign = self.get_object()
        if campaign.domain.status != DomainStatus.SHARDING:
            return Response(
                {
                    "detail": "Campaign is no longer editable "
                    f"(domain status is '{campaign.domain.status}')."
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsCampaignDomainOwner])
def activate_campaign(request: Request, pk) -> Response:
    campaign = generics.get_object_or_404(
        ShardCampaign.objects.select_related("domain"), pk=pk
    )
    if campaign.domain.owner_id != request.user.id:
        return Response(
            {"detail": "Only the domain owner can activate the campaign."},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        campaign.domain.transition_to(DomainStatus.ACTIVE)
        campaign.domain.save()
    except DjangoValidationError as exc:
        return Response(
            {"detail": str(exc.message if hasattr(exc, "message") else exc)},
            status=status.HTTP_409_CONFLICT,
        )
    return Response(ShardCampaignSerializer(campaign).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def buy_shards(request: Request, pk) -> Response:
    """Atomic shard purchase.

    Locks the campaign row for the duration of the transaction so two
    concurrent buyers can't oversell the campaign. Auto-transitions
    the parent Domain to COMPLETED when funding_target is hit.
    """
    payload = BuySharesRequestSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    requested: int = payload.validated_data["shards"]

    with transaction.atomic():
        campaign = (
            ShardCampaign.objects.select_for_update()
            .select_related("domain")
            .filter(pk=pk)
            .first()
        )
        if campaign is None:
            return Response(
                {"detail": "Campaign not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if campaign.domain.status != DomainStatus.ACTIVE:
            return Response(
                {
                    "detail": f"Campaign not open for purchase "
                    f"(domain status is '{campaign.domain.status}')."
                },
                status=status.HTTP_409_CONFLICT,
            )

        if requested > campaign.shards_available:
            return Response(
                {
                    "detail": "Requested shards exceed availability.",
                    "shards_available": campaign.shards_available,
                },
                status=status.HTTP_409_CONFLICT,
            )

        cost = Decimal(requested) * campaign.price_per_shard_usd

        campaign.shards_available -= requested
        campaign.funding_raised_usd = (
            (campaign.funding_raised_usd or Decimal("0")) + cost
        )

        holding, created = ShardHolding.objects.get_or_create(
            campaign=campaign,
            holder=request.user,
            defaults={
                "shards_held": requested,
                "purchase_price_usd": campaign.price_per_shard_usd,
                "tx_hash": _mock_tx_hash(),
            },
        )
        if not created:
            holding.shards_held += requested
            holding.tx_hash = _mock_tx_hash()
            holding.save()

        # Auto-complete if funding target reached
        if campaign.funding_raised_usd >= campaign.funding_target_usd:
            try:
                campaign.domain.transition_to(DomainStatus.COMPLETED)
                campaign.domain.save()
            except DjangoValidationError:
                logger.warning("Auto-COMPLETED failed for campaign %s", campaign.id)

        campaign.save()

    return Response(
        {
            "campaign": ShardCampaignSerializer(campaign).data,
            "holding": ShardHoldingSerializer(holding).data,
        },
        status=status.HTTP_200_OK,
    )


class MyHoldingsList(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ShardHoldingSerializer

    def get_queryset(self):
        return (
            ShardHolding.objects.filter(holder=self.request.user)
            .select_related("campaign", "campaign__domain")
        )
