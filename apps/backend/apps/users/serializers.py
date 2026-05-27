from __future__ import annotations

from rest_framework import serializers

from apps.users.models import WALLET_ADDRESS_RE


class WalletAddressField(serializers.CharField):
    """Accepts checksum or lowercase 0x address, stores normalized lowercase."""

    def to_internal_value(self, data: str) -> str:
        value = super().to_internal_value(data).lower()
        if not WALLET_ADDRESS_RE.fullmatch(value):
            raise serializers.ValidationError(
                "Must be a 0x-prefixed 40-character hex address."
            )
        return value


class NonceRequestSerializer(serializers.Serializer):
    address = WalletAddressField()


class NonceResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    nonce = serializers.CharField()


class VerifyRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    signature = serializers.CharField()


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    wallet_address = serializers.CharField()
