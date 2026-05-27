from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from siwe import SiweMessage, VerificationError

from apps.users.auth_flow import AuthFailure, resolve_signed_in_user
from apps.users.nonce import mint_nonce
from apps.users.serializers import (
    NonceRequestSerializer,
    NonceResponseSerializer,
    TokenPairSerializer,
    VerifyRequestSerializer,
)
from apps.users.siwe_message import build_message

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def nonce_view(request: Request) -> Response:
    payload = NonceRequestSerializer(data=request.query_params)
    payload.is_valid(raise_exception=True)
    address: str = payload.validated_data["address"]

    nonce = mint_nonce(address)
    message = build_message(
        domain=request.get_host(),
        uri=request.build_absolute_uri("/"),
        address=address,
        nonce=nonce,
    )
    return Response(
        NonceResponseSerializer({"message": message, "nonce": nonce}).data,
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_view(request: Request) -> Response:
    payload = VerifyRequestSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    message_str: str = payload.validated_data["message"]
    signature: str = payload.validated_data["signature"]

    try:
        siwe_msg = SiweMessage.from_message(message_str)
    except Exception:
        return Response({"detail": "Invalid SIWE message"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        siwe_msg.verify(signature)
    except VerificationError:
        return Response({"detail": "Signature verification failed"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        result = resolve_signed_in_user(
            verified_address=siwe_msg.address.lower(),
            submitted_nonce=siwe_msg.nonce,
        )
    except AuthFailure as exc:
        logger.warning("siwe auth rejected: %s", exc.reason)
        return Response({"detail": "Authentication failed"}, status=status.HTTP_401_UNAUTHORIZED)

    refresh = RefreshToken.for_user(result.user)
    body = TokenPairSerializer(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "wallet_address": result.user.wallet_address,
        }
    ).data
    return Response(body, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def whoami_view(request: Request) -> Response:
    return Response(
        {
            "id": request.user.id,
            "wallet_address": request.user.wallet_address,
        },
        status=status.HTTP_200_OK,
    )
