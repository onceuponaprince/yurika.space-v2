from __future__ import annotations

import re

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models

WALLET_ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")


def validate_wallet_address(value: str) -> None:
    if not WALLET_ADDRESS_RE.fullmatch(value):
        raise ValidationError("wallet_address must match 0x[0-9a-f]{40} (lowercase)")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, wallet_address: str, **extra_fields) -> "User":
        wallet_address = wallet_address.lower()
        validate_wallet_address(wallet_address)
        user = self.model(wallet_address=wallet_address, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, wallet_address: str, **extra_fields) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(wallet_address, **extra_fields)


class User(AbstractUser):
    username = None  # type: ignore[assignment]
    email = models.EmailField(blank=True, null=True)
    wallet_address = models.CharField(
        max_length=42,
        unique=True,
        validators=[validate_wallet_address],
    )

    USERNAME_FIELD = "wallet_address"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def __str__(self) -> str:
        return self.wallet_address
