from __future__ import annotations

from django.core.cache import cache

from apps.users.nonce import NONCE_LENGTH, consume_nonce, mint_nonce


class TestNonceLifecycle:
    def setup_method(self) -> None:
        cache.clear()

    def test_mint_returns_alphanumeric_string_of_expected_length(self) -> None:
        nonce = mint_nonce("0x" + "a" * 40)
        assert len(nonce) == NONCE_LENGTH
        assert nonce.isalnum()

    def test_mint_then_consume_succeeds(self) -> None:
        addr = "0x" + "a" * 40
        nonce = mint_nonce(addr)
        assert consume_nonce(addr, nonce) is True

    def test_consume_twice_is_rejected(self) -> None:
        addr = "0x" + "a" * 40
        nonce = mint_nonce(addr)
        assert consume_nonce(addr, nonce) is True
        assert consume_nonce(addr, nonce) is False  # already consumed

    def test_wrong_nonce_rejected(self) -> None:
        addr = "0x" + "a" * 40
        mint_nonce(addr)
        assert consume_nonce(addr, "WRONG_NONCE_VALUE_X") is False

    def test_unminted_wallet_rejected(self) -> None:
        assert consume_nonce("0x" + "b" * 40, "anything") is False

    def test_mint_is_case_insensitive_on_address(self) -> None:
        lower = "0x" + "a" * 40
        upper = "0x" + "A" * 40
        nonce = mint_nonce(lower)
        assert consume_nonce(upper, nonce) is True

    def test_two_wallets_get_independent_nonces(self) -> None:
        a = "0x" + "a" * 40
        b = "0x" + "b" * 40
        nonce_a = mint_nonce(a)
        nonce_b = mint_nonce(b)
        assert nonce_a != nonce_b
        assert consume_nonce(a, nonce_b) is False
        assert consume_nonce(a, nonce_a) is True
