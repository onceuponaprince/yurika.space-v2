from __future__ import annotations

from django.urls import path

from apps.graph.views import discover

urlpatterns = [
    path("discover/", discover, name="graph-discover"),
]
