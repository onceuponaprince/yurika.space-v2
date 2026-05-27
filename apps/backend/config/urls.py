"""Root URL configuration.

Subsystems 2+ register their own urls.py and include them here.
"""
from django.contrib import admin
from django.urls import include, path

from config.views import dev_panel, health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("dev/panel/", dev_panel, name="dev-panel"),
    path("api/auth/", include("apps.users.urls")),
    # path("api/", include("apps.domains.urls")),          # subsystem 3
    # path("api/graph/", include("apps.graph.urls")),      # subsystem 5
]
