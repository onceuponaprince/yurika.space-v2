"""Root URL configuration.

Subsystems 2+ register their own urls.py and include them here.
"""
from django.contrib import admin
from django.urls import include, path

from config.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/auth/", include("apps.users.urls")),
    # path("api/", include("apps.domains.urls")),          # subsystem 3
    # path("api/graph/", include("apps.graph.urls")),      # subsystem 5
]
