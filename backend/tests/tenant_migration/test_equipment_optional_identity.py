import pytest
from django.db import transaction

from apps.tenant_migration.identity_resolution import RequiredIdentitySet


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("order", [(False, True), (True, False)])
def test_optional_creator_never_weakens_a_required_identity(order):
    with transaction.atomic():
        required = RequiredIdentitySet()
        for mandatory in order:
            required.add("17", mandatory=mandatory)
        assert required.mandatory("17")
        assert required.count() == 1
        assert not required.was_resolved("17", 42)
        required.mark_resolved("17", 42)
        assert required.was_resolved("17", 42)
        assert not required.was_resolved("17", 43)


@pytest.mark.django_db(transaction=True)
def test_only_optional_creator_does_not_add_a_mandatory_identity():
    with transaction.atomic():
        required = RequiredIdentitySet()
        required.add("18", mandatory=False)
        assert required.contains("18")
        assert not required.mandatory("18")
        assert required.count() == 0
