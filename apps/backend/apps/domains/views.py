from __future__ import annotations

import logging
import secrets

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.domains import dns
from apps.domains.models import Domain, DomainStatus, Project
from apps.domains.permissions import IsOwner
from apps.domains.serializers import (
    DomainCreateSerializer,
    DomainSerializer,
    ProjectSerializer,
    VerifyInstructionsSerializer,
)

logger = logging.getLogger(__name__)


class DomainListCreate(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        return DomainCreateSerializer if self.request.method == "POST" else DomainSerializer

    def perform_create(self, serializer) -> None:
        serializer.save(owner=self.request.user)


class DomainDetail(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/PUT — only mutable fields are described in DomainSerializer's
    read_only_fields. DELETE transitions the domain to WITHDRAWN rather than
    hard-deleting; hard deletes require admin (not exposed here)."""

    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = DomainSerializer

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        instance = self.get_object()
        try:
            instance.transition_to(DomainStatus.WITHDRAWN)
        except DjangoValidationError as exc:
            return Response(
                {"detail": str(exc.message if hasattr(exc, "message") else exc)},
                status=status.HTTP_409_CONFLICT,
            )
        instance.save()
        return Response(DomainSerializer(instance).data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsOwner])
def verify_instructions(request: Request, pk) -> Response:
    domain = generics.get_object_or_404(Domain, pk=pk, owner=request.user)
    body = VerifyInstructionsSerializer(
        {
            "record_name": domain.verification_record_name,
            "record_value": domain.verification_nonce,
            "fqdn": domain.fqdn,
        }
    ).data
    return Response(body, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsOwner])
def verify_domain(request: Request, pk) -> Response:
    domain = generics.get_object_or_404(Domain, pk=pk, owner=request.user)

    if domain.status != DomainStatus.PENDING:
        return Response(
            {"detail": f"Domain is in status '{domain.status}', not 'pending'."},
            status=status.HTTP_409_CONFLICT,
        )

    try:
        txt_values = dns.lookup_txt(domain.verification_record_name)
    except dns.DNSLookupError as exc:
        logger.warning("dns lookup failed for %s: %s", domain.verification_record_name, exc)
        return Response(
            {"detail": "DNS lookup failed — try again in a few minutes."},
            status=status.HTTP_424_FAILED_DEPENDENCY,
        )

    if domain.verification_nonce not in txt_values:
        return Response(
            {
                "detail": "Verification nonce not found in TXT records.",
                "expected_record": domain.verification_record_name,
                "expected_value": domain.verification_nonce,
                "got_values": txt_values,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    domain.transition_to(DomainStatus.VERIFIED)
    domain.save()
    return Response(DomainSerializer(domain).data, status=status.HTTP_200_OK)


def _mock_address() -> str:
    return "0x" + secrets.token_hex(20)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsOwner])
def vault_domain(request: Request, pk) -> Response:
    """Lock a verified domain into a (mocked) on-chain vault.

    Real contract deployment lands in subsystem 7. For now we write
    deterministic mock addresses so the rest of the pipeline can be
    exercised end-to-end without an L2 connection.
    """
    domain = generics.get_object_or_404(Domain, pk=pk, owner=request.user)

    try:
        domain.transition_to(DomainStatus.VAULTED)
    except DjangoValidationError as exc:
        return Response(
            {"detail": str(exc.message if hasattr(exc, "message") else exc)},
            status=status.HTTP_409_CONFLICT,
        )

    domain.vault_contract_address = _mock_address()
    domain.shard_contract_address = _mock_address()
    domain.save()
    return Response(DomainSerializer(domain).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsOwner])
def dev_force_vault(request: Request, pk) -> Response:
    """DEV-ONLY: skip DNS verification and jump a domain straight to VAULTED.

    Exists so the dev panel can exercise the full PENDING -> ... -> COMPLETED
    pipeline without needing to publish real DNS TXT records. 404s when
    DEBUG=False so this can never run in production.
    """
    from django.conf import settings as _settings
    from django.http import Http404

    if not _settings.DEBUG:
        raise Http404()

    domain = generics.get_object_or_404(Domain, pk=pk, owner=request.user)
    domain.status = DomainStatus.VAULTED
    domain.vault_contract_address = _mock_address()
    domain.shard_contract_address = _mock_address()
    domain.save()
    return Response(DomainSerializer(domain).data, status=status.HTTP_200_OK)


class ProjectListCreate(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)

    def perform_create(self, serializer) -> None:
        serializer.save(owner=self.request.user)


class ProjectDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)
