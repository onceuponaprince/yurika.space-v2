from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.domains.models import Domain, DomainStatus
from apps.users.models import User


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(wallet_address="0x" + "a" * 40)


@pytest.mark.django_db
class TestDomainDefaults:
    def test_default_status_is_pending(self, owner: User) -> None:
        d = Domain.objects.create(owner=owner, name="yurika", tld="space")
        assert d.status == DomainStatus.PENDING

    def test_verification_nonce_auto_generated(self, owner: User) -> None:
        d = Domain.objects.create(owner=owner, name="yurika", tld="space")
        assert d.verification_nonce
        assert len(d.verification_nonce) >= 16

    def test_two_domains_get_different_nonces(self, owner: User) -> None:
        a = Domain.objects.create(owner=owner, name="alpha", tld="com")
        b = Domain.objects.create(owner=owner, name="bravo", tld="com")
        assert a.verification_nonce != b.verification_nonce

    def test_fqdn_property(self, owner: User) -> None:
        d = Domain.objects.create(owner=owner, name="yurika", tld="space")
        assert d.fqdn == "yurika.space"
        assert d.verification_record_name == "_yurika-verify.yurika.space"

    def test_unique_name_constraint(self, owner: User) -> None:
        Domain.objects.create(owner=owner, name="yurika", tld="space")
        with pytest.raises(Exception):  # IntegrityError
            Domain.objects.create(owner=owner, name="yurika", tld="com")


@pytest.mark.django_db
class TestDomainTransitions:
    def test_pending_to_verified_allowed(self, owner: User) -> None:
        d = Domain.objects.create(owner=owner, name="yurika", tld="space")
        d.transition_to(DomainStatus.VERIFIED)
        assert d.status == DomainStatus.VERIFIED

    def test_verified_to_vaulted_allowed(self, owner: User) -> None:
        d = Domain.objects.create(owner=owner, name="yurika", tld="space")
        d.transition_to(DomainStatus.VERIFIED)
        d.transition_to(DomainStatus.VAULTED)
        assert d.status == DomainStatus.VAULTED

    def test_pending_to_vaulted_rejected(self, owner: User) -> None:
        d = Domain.objects.create(owner=owner, name="yurika", tld="space")
        with pytest.raises(ValidationError):
            d.transition_to(DomainStatus.VAULTED)

    def test_pending_to_completed_rejected(self, owner: User) -> None:
        d = Domain.objects.create(owner=owner, name="yurika", tld="space")
        with pytest.raises(ValidationError):
            d.transition_to(DomainStatus.COMPLETED)

    def test_withdrawn_is_terminal(self, owner: User) -> None:
        d = Domain.objects.create(owner=owner, name="yurika", tld="space")
        d.transition_to(DomainStatus.WITHDRAWN)
        with pytest.raises(ValidationError):
            d.transition_to(DomainStatus.PENDING)

    def test_completed_is_terminal(self, owner: User) -> None:
        d = Domain.objects.create(owner=owner, name="yurika", tld="space")
        for s in [DomainStatus.VERIFIED, DomainStatus.VAULTED,
                  DomainStatus.SHARDING, DomainStatus.ACTIVE, DomainStatus.COMPLETED]:
            d.transition_to(s)
        with pytest.raises(ValidationError):
            d.transition_to(DomainStatus.ACTIVE)

    def test_withdraw_allowed_from_any_non_terminal_state(self, owner: User) -> None:
        for source in [DomainStatus.PENDING, DomainStatus.VERIFIED,
                       DomainStatus.VAULTED, DomainStatus.SHARDING,
                       DomainStatus.ACTIVE]:
            d = Domain(owner=owner, name=f"d-{source}", tld="com", status=source)
            d.transition_to(DomainStatus.WITHDRAWN)
            assert d.status == DomainStatus.WITHDRAWN
