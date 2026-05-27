from __future__ import annotations

from rest_framework import serializers

from apps.domains.models import Domain, Project


class DomainSerializer(serializers.ModelSerializer):
    fqdn = serializers.CharField(read_only=True)
    verification_record_name = serializers.CharField(read_only=True)

    class Meta:
        model = Domain
        fields = [
            "id",
            "owner",
            "name",
            "tld",
            "fqdn",
            "description",
            "status",
            "registrar",
            "expiry_date",
            "ownership_proof_url",
            "vault_contract_address",
            "shard_contract_address",
            "chain_id",
            "verification_record_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "status",
            "vault_contract_address",
            "shard_contract_address",
            "verification_record_name",
            "created_at",
            "updated_at",
        ]


class DomainCreateSerializer(DomainSerializer):
    """Restricts the create surface to founder-controlled fields only."""

    class Meta(DomainSerializer.Meta):
        fields = [
            "id",
            "name",
            "tld",
            "description",
            "registrar",
            "expiry_date",
            "ownership_proof_url",
            "chain_id",
            "verification_record_name",
            "status",
        ]
        read_only_fields = ["id", "status", "verification_record_name"]


class VerifyInstructionsSerializer(serializers.Serializer):
    record_name = serializers.CharField()
    record_value = serializers.CharField()
    fqdn = serializers.CharField()


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "owner",
            "name",
            "description",
            "pitch_deck_url",
            "repository_url",
            "media_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]
