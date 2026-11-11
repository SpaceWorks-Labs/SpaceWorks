"""Public registration binds the appropriate identity guard without presence."""

import pytest

from apps.presence.guard import require_active_account, require_active_member
from tests.events.collab_helpers import make_member
from tests.events.ticketing_helpers import account, event_space, open_event, signup

pytestmark = pytest.mark.django_db


def test_advance_bookings_bind_account_and_existing_member_waiver_guards():
    from apps.bookings import access, views_public
    from apps.presence.guard import require_active_account

    # Booking ahead needs an account, and existing members still owe their waiver.
    assert views_public.require_booking_account is access.require_booking_account
    assert access.require_active_account is require_active_account
    assert access.require_active_member is require_active_member
    assert not hasattr(access, "require_active_member_presence")


@pytest.mark.parametrize(
    "module_path",
    [
        "apps.machines.views_public_service",
        "apps.machines.views_public_printer_service",
    ],
)
def test_machine_request_surfaces_bind_the_membership_aware_guard(module_path):
    """Machine-service and printer aliases bind the same public intake authority."""
    import importlib

    from apps.machines.views_public_service import require_public_machine_requester

    module = importlib.import_module(module_path)

    assert getattr(module, "require_public_machine_requester", None) is (
        require_public_machine_requester
    )
    assert not hasattr(module, "require_active_member")


@pytest.mark.django_db
def test_machine_intake_refuses_unavailable_membership():
    from rest_framework.exceptions import NotFound
    from apps.machines.public_intake_access import require_public_intake_available
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.module_registry import core_module_keys

    space = Makerspace.objects.create(name="guard-membership-off", slug="guard-membership-off",
                                      enabled_modules=sorted(core_module_keys()))
    with pytest.raises(NotFound) as error:
        require_public_intake_available(space)
    assert error.value.detail["code"] == "machine_intake_unavailable"


@pytest.mark.parametrize("audience,identity,expected", [
    ("members", "member", 201),
    ("members", "account", 403),
    ("accounts", "account", 201),
    ("accounts", "suspended", 403),
])
def test_event_registration_binds_the_audience_guard(monkeypatch, audience, identity, expected):
    from apps.events import registration_access
    from apps.events.models import EventRegistration
    from apps.makerspaces.models import MakerspaceMembership

    assert registration_access.require_active_member is require_active_member
    assert registration_access.require_active_account is require_active_account
    assert not hasattr(registration_access, "require_active_member_presence")
    space = event_space("audience-guard", membership=audience == "members")
    event = open_event(space, audience)
    user = make_member(space) if identity == "member" else account()
    if identity == "suspended":
        user.access_status = "suspended"
        user.save(update_fields=["access_status"])
    before_memberships = MakerspaceMembership.objects.filter(makerspace=space).count()
    calls = []

    def member_guard(user, space):
        calls.append("members")
        return require_active_member(user, space)

    def account_guard(user, space):
        calls.append("accounts")
        return require_active_account(user, space)

    monkeypatch.setattr(registration_access, "require_active_member", member_guard)
    monkeypatch.setattr(registration_access, "require_active_account", account_guard)
    response = signup(event, user)
    assert response.status_code == expected, response.data
    # Both the public view and the locked service recheck admission on success.
    assert calls == [audience] * (2 if expected == 201 else 1)
    assert EventRegistration.objects.filter(event=event, member=user).exists() is (expected == 201)
    assert MakerspaceMembership.objects.filter(makerspace=space).count() == before_memberships
