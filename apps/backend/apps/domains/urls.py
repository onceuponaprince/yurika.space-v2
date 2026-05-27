from __future__ import annotations

from django.urls import path

from apps.domains.views import (
    DomainDetail,
    DomainListCreate,
    ProjectDetail,
    ProjectListCreate,
    vault_domain,
    verify_domain,
    verify_instructions,
)

urlpatterns = [
    path("domains/", DomainListCreate.as_view(), name="domain-list"),
    path("domains/<uuid:pk>/", DomainDetail.as_view(), name="domain-detail"),
    path("domains/<uuid:pk>/verify-instructions/", verify_instructions, name="domain-verify-instructions"),
    path("domains/<uuid:pk>/verify/", verify_domain, name="domain-verify"),
    path("domains/<uuid:pk>/vault/", vault_domain, name="domain-vault"),
    path("projects/", ProjectListCreate.as_view(), name="project-list"),
    path("projects/<uuid:pk>/", ProjectDetail.as_view(), name="project-detail"),
]
