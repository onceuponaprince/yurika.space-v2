from __future__ import annotations

from django.urls import path

from apps.users.views import nonce_view, verify_view, whoami_view

urlpatterns = [
    path("wallet/nonce/", nonce_view, name="wallet-nonce"),
    path("wallet/verify/", verify_view, name="wallet-verify"),
    path("whoami/", whoami_view, name="whoami"),
]
