"""Graph discovery endpoint — /api/graph/discover/.

Mode dispatch:
    ?mode=personalized  → 1-hop peer-curator traversal (auth required)
    ?mode=trending      → most-held domains (public)
    ?mode=stats         → coarse graph counts (public, dev/debug)

If `mode` is omitted, default to `personalized` for authenticated users
and `trending` for anonymous ones.
"""
from __future__ import annotations

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.graph import discovery

logger = logging.getLogger(__name__)


VALID_MODES = {"personalized", "trending", "stats"}


def _resolve_mode(request: Request) -> str:
    requested = request.query_params.get("mode")
    if requested in VALID_MODES:
        return requested
    if requested is not None:
        # Caller asked for something we don't support — fall through to default
        # rather than 400, since the default is always safe.
        logger.info("graph discover: unknown mode %r, falling back to default", requested)
    return "personalized" if request.user.is_authenticated else "trending"


@api_view(["GET"])
@permission_classes([AllowAny])
def discover(request: Request) -> Response:
    mode = _resolve_mode(request)
    try:
        limit = max(1, min(int(request.query_params.get("limit", "10")), 50))
    except ValueError:
        limit = 10

    if mode == "stats":
        return Response({"mode": "stats", "stats": discovery.graph_stats()})

    if mode == "personalized":
        if not request.user.is_authenticated:
            return Response(
                {"detail": "personalized mode requires authentication"},
                status=401,
            )
        try:
            results = discovery.personalized_discovery(
                str(request.user.id), limit=limit
            )
        except NotImplementedError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "hint": "fill in apps/graph/discovery.py:personalized_discovery",
                },
                status=501,
            )
        return Response({"mode": "personalized", "results": results})

    # trending (default for anonymous)
    results = discovery.trending_domains(limit=limit)
    return Response({"mode": "trending", "results": results})
