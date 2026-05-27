from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.marketplace.models import ShardCampaign


class IsCampaignDomainOwner(BasePermission):
    """Only the owner of the underlying Domain can mutate the campaign."""

    def has_object_permission(self, request, view, obj: ShardCampaign) -> bool:
        return obj.domain.owner_id == request.user.id
