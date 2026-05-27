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


@require_GET
def dev_panel(request) -> HttpResponse:
    if not settings.DEBUG:
        raise Http404()
    return HttpResponse(_PANEL_HTML_PATH.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")
