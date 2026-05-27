from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.users.models import User, validate_wallet_address


class TestWalletAddressValidator:
    def test_accepts_canonical_lowercase(self) -> None:
        validate_wallet_address("0x" + "a" * 40)

    @pytest.mark.parametrize(
        "bad",
        [
            "0x" + "A" * 40,           # uppercase rejected — caller normalizes
            "0x" + "a" * 39,           # too short
            "0x" + "a" * 41,           # too long
            "a" * 42,                  # missing 0x
            "0x" + "g" * 40,           # non-hex char
            "",                        # empty
        ],
    )
    def test_rejects_malformed(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            validate_wallet_address(bad)


@pytest.mark.django_db
class TestUserManager:
    def test_create_user_lowercases_address(self) -> None:
        addr = "0x" + "A" * 40
        user = User.objects.create_user(wallet_address=addr)
        assert user.wallet_address == addr.lower()
        assert not user.has_usable_password()

    def test_create_user_rejects_bad_address(self) -> None:
        with pytest.raises(ValidationError):
            User.objects.create_user(wallet_address="not-a-wallet")
