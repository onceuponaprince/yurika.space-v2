"""Cross-cutting views that don't belong to any app.

Currently: a health probe that verifies Postgres + Redis connectivity.
Neo4j is included opportunistically — if neomodel isn't installed yet (early
subsystems), the check is skipped rather than failing the gate.
"""
from __future__ import annotations

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request) -> JsonResponse:
    checks: dict[str, str] = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc.__class__.__name__}"

    try:
        from django.core.cache import cache

        cache.set("health-check", "ok", timeout=5)
        checks["redis"] = "ok" if cache.get("health-check") == "ok" else "stale"
    except Exception as exc:
        checks["redis"] = f"error: {exc.__class__.__name__}"

    status_ok = all(v == "ok" for v in checks.values())
    return JsonResponse(
        {"status": "ok" if status_ok else "degraded", "checks": checks},
        status=200 if status_ok else 503,
    )
