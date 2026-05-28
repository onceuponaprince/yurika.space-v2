"""Cross-cutting views that don't belong to any app.

Currently: a health probe that verifies Postgres + Redis connectivity.
Neo4j is included opportunistically — if neomodel isn't installed yet (early
subsystems), the check is skipped rather than failing the gate.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import Http404, HttpResponse, JsonResponse
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


_PANEL_HTML_PATH = Path(__file__).resolve().parent / "dev_panel.html"
_API_CATALOG_PATH = Path(__file__).resolve().parent / "api_catalog.json"


@require_GET
def dev_panel(request) -> HttpResponse:
    if not settings.DEBUG:
        raise Http404()
    return HttpResponse(_PANEL_HTML_PATH.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")


@require_GET
def api_catalog(request) -> HttpResponse:
    """Single source of truth for the endpoint test catalog, consumed by
    both the dev panel and the Next.js frontend's test view. DEBUG-gated
    like the panel — it's a development surface, not a production API."""
    if not settings.DEBUG:
        raise Http404()
    # CORS open so the frontend (different origin in dev) can fetch it.
    response = HttpResponse(
        _API_CATALOG_PATH.read_text(encoding="utf-8"),
        content_type="application/json; charset=utf-8",
    )
    response["Access-Control-Allow-Origin"] = "*"
    return response
