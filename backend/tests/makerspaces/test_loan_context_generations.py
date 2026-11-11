"""Generation contract: no runtime claim until admitted isolated tests run."""
import pytest
from django.core.exceptions import ValidationError
from apps.makerspaces.loan_context_generations import new_generations, validate_generations


def test_generation_defaults_are_distinct_across_domains_and_tenants():
    first, second = new_generations(), new_generations()
    validate_generations(first)
    validate_generations(second)
    assert len(set(first.values()) | set(second.values())) == 4


@pytest.mark.parametrize("value", [None, {}, {"events": "not-a-uuid", "bookings": "not-a-uuid"},
    {"events": "00000000-0000-4000-8000-000000000000", "bookings": "00000000-0000-4000-8000-000000000000"}])
def test_malformed_generations_refuse(value):
    with pytest.raises(ValidationError):
        validate_generations(value)

@pytest.mark.django_db(transaction=True)
def test_generation_rotation_is_domain_scoped_and_rollback_safe():
    from django.db import transaction
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.loan_context_generations import rotate
    space = Makerspace.objects.create(name="Generation test", slug="generation-test")
    before = dict(space.loan_context_generations)
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            row = Makerspace.objects.select_for_update().get(pk=space.pk)
            rotate(row, {"events"})
            assert row.loan_context_generations["events"] != before["events"]
            assert row.loan_context_generations["bookings"] == before["bookings"]
            raise RuntimeError("rollback")
    space.refresh_from_db()
    assert space.loan_context_generations == before
