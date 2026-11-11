"""Service transaction/audit regressions, split from the workflow tests."""
import pytest
from apps.bookings import services
from apps.bookings.models import BookableSpace, Booking
from tests.bookings.test_services import make_makerspace, make_actor, make_space, direct_booking, book

pytestmark = pytest.mark.django_db

@pytest.mark.parametrize('operation', [
    'create_space', 'update_space', 'deactivate_space', 'create_booking',
    'cancel_booking', 'complete_booking', 'mark_no_show',
])
def test_mocked_audit_failure_rolls_back_every_mutation(monkeypatch, operation):
    makerspace, actor = make_makerspace(), make_actor()
    space = make_space(makerspace, actor)
    row = direct_booking(space)
    before = (BookableSpace.objects.count(), Booking.objects.count())
    calls = {
        'create_space': lambda: make_space(makerspace, actor, name='New'),
        'update_space': lambda: services.update_space(space, actor=actor, name='Changed'),
        'deactivate_space': lambda: services.deactivate_space(space, actor=actor),
        'create_booking': lambda: book(space),
        'cancel_booking': lambda: services.cancel_booking(row, actor=actor),
        'complete_booking': lambda: services.complete_booking(row, actor=actor),
        'mark_no_show': lambda: services.mark_no_show(row, actor=actor),
    }
    monkeypatch.setattr(services.audit, 'record', lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    with pytest.raises(RuntimeError):
        calls[operation]()
    space.refresh_from_db(); row.refresh_from_db()
    assert (BookableSpace.objects.count(), Booking.objects.count()) == before
    assert (space.name, space.is_active, row.status) == (
        'Development Room', True, 'confirmed',
    )


def test_bookings_have_dedicated_quota_counter():
    from apps.makerspaces import limits
    assert all(
        'bookings' in mapping
        for mapping in (
            limits.KNOWN_LIMIT_KEYS,
            limits.RESOURCE_LABELS,
            limits._COUNTERS,
        )
    )
