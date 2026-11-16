"""Decision 246 (lane F8): module-off and idempotency conditions for limited helper delegation (221i)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events import event_authority, services_staff_grants as services
from apps.events.contributions.models_roles import EventGrantEntitlement
from apps.makerspaces.models import Makerspace
from tests.events.test_decision15_coorganizer_journeys import REFUSED, person, world  # noqa: F401
from tests.events.test_helper_window_221i import limited

pytestmark = pytest.mark.django_db


def _events_off(space):
    Makerspace.objects.filter(pk=space.pk).update(
        enabled_modules=sorted(set(space.enabled_modules or []) - {"events"}))


def test_a_limited_helpers_authority_disappears_when_the_events_module_is_off_and_returns_when_on():
    w = world("f8-221i-off")
    end = timezone.now() + timedelta(hours=2)
    boxed = limited(w, track_ids=[7], valid_until=end)
    _invite, token = services.create_invite(w.event, actor=boxed, permissions=["judge"], track_ids=[7])
    helper = person("f8-off-helper")
    services.redeem_invite(token, actor=helper)
    assert event_authority.can(helper, w.event, "judge", track_id=7)
    original = list(w.space.enabled_modules)
    _events_off(w.space)
    assert not event_authority.can(helper, w.event, "judge", track_id=7)
    assert not event_authority.can(boxed, w.event, "judge", track_id=7)
    Makerspace.objects.filter(pk=w.space.pk).update(enabled_modules=original)
    assert event_authority.can(helper, w.event, "judge", track_id=7)


def test_redeeming_a_limited_invite_twice_creates_one_limited_entitlement():
    w = world("f8-221i-idem")
    end = timezone.now() + timedelta(hours=2)
    boxed = limited(w, track_ids=[7], valid_until=end)
    _invite, token = services.create_invite(w.event, actor=boxed, permissions=["judge"], track_ids=[7])
    helper = person("f8-idem-helper")
    grant = services.redeem_invite(token, actor=helper)
    with pytest.raises(REFUSED):
        services.redeem_invite(token, actor=person("f8-idem-second"))
    with pytest.raises(REFUSED):
        services.redeem_invite(token, actor=helper)
    rows = EventGrantEntitlement.objects.filter(grant=grant, source_kind="manual", revoked_at__isnull=True)
    assert rows.count() == 1
    entitlement = rows.get()
    assert (entitlement.track_ids, entitlement.valid_until) == ([7], end)


def test_creating_the_same_limited_invite_twice_never_widens_the_second_one():
    w = world("f8-221i-twice")
    end = timezone.now() + timedelta(hours=2)
    boxed = limited(w, track_ids=[7], valid_until=end)
    first, _ = services.create_invite(w.event, actor=boxed, permissions=["judge"], track_ids=[7])
    second, _ = services.create_invite(w.event, actor=boxed, permissions=["judge"], track_ids=[7])
    assert (first.track_ids, first.valid_until) == (second.track_ids, second.valid_until) == ([7], end)
