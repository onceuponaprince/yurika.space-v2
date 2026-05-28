"""Root URL configuration.

Subsystems 2+ register their own urls.py and include them here.
"""
from django.contrib import admin
from django.urls import include, path

from config.views import api_catalog, dev_panel, health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("dev/panel/", dev_panel, name="dev-panel"),
    path("dev/api-catalog.json", api_catalog, name="dev-api-catalog"),
    path("api/auth/", include("apps.users.urls")),
    path("api/", include("apps.domains.urls")),
    path("api/", include("apps.marketplace.urls")),
    path("api/graph/", include("apps.graph.urls")),
]
