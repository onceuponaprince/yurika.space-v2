from __future__ import annotations

from rest_framework.permissions import BasePermission

class IsOwner(BasePermission):
    """Object-level permission: only the entity's owner can read/mutate.

    Combined with a queryset that pre-filters by `owner=request.user`,
    this provides defense in depth — even if the queryset filter is
    bypassed, has_object_permission() will still reject the request.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        return getattr(obj, "owner_id", None) == request.user.id
