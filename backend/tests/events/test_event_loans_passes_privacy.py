"""An event's loans and guest passes never show contact details, and mask holders for a windowless superadmin.

The Event Manager reading `events/<pk>/loans/` holds no loan or member-contact authority, so the borrower
label must never fall back to an email or phone number (Codex arch-1 #2). A platform superadmin without an
open PII window sees the holder masked, like every peer staff endpoint (#111 Q12).
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.pii_presentation import MASK
from apps.events.models import Event
from apps.events.models_loan_context import EventLoanContext
from apps.hardware_requests.display import account_name_label, requester_name_label
from apps.makerspaces.models import GuestPass
from tests.accounts.account_factories import make_staff
from tests.test_request_workflow import authenticated_client, make_hardware_request, make_product, make_user


# --- the label itself: pure, no database ---------------------------------------------------------

def _account(username="", display_name="", first="", last=""):
    return SimpleNamespace(username=username, display_name=display_name,
                           get_full_name=lambda: f"{first} {last}".strip())


def test_label_prefers_the_captured_name_then_the_account_name():
    row = SimpleNamespace(requester_name="Asha K", requester=_account("asha", "Asha"), requester_username="asha")
    assert requester_name_label(row) == "Asha K"
    row.requester_name = ""
    assert requester_name_label(row) == "Asha"


@pytest.mark.parametrize("username", ["asha@example.test", "+91 98765 43210", "9876543210",
                                      "checkin_" + "a" * 64])
def test_label_never_falls_back_to_contact_details_or_the_checkin_hash(username):
    row = SimpleNamespace(requester_name="", requester=_account(username), requester_username=username,
                          requester_contact_email="asha@example.test", requester_contact_phone="+15550101010")
    assert requester_name_label(row, fallback="Member") == "Member"


def test_a_plain_username_is_still_a_label():
    assert account_name_label(_account("maker_asha")) == "maker_asha"
    assert account_name_label(None, fallback="Guest") == "Guest"


# --- over HTTP -----------------------------------------------------------------------------------

def _space_with_event(slug):
    from tests.test_request_workflow import make_space
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"events", "request_workflow", "membership"})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled", "membership.guest_passes"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    ends = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=space, title="Robotics night", starts_at=ends - timedelta(hours=3),
                                 ends_at=ends, status=Event.Status.PUBLISHED)
    return space, event


def _loan(space, event, borrower):
    request = make_hardware_request(space, make_product(space), requester=borrower,
                                    contact_email="borrower@example.test")
    EventLoanContext.objects.create(makerspace=space, request=request, event=event, active=True)
    return request


@pytest.mark.django_db
def test_event_loans_show_no_email_when_the_borrower_has_no_name():
    space, event = _space_with_event("ev-loans-noemail")
    borrower = make_user("borrower@example.test", display_name="", first_name="", last_name="")
    _loan(space, event, borrower)
    manager = make_staff(space, username="ev-loans-manager")
    body = authenticated_client(manager).get(reverse("admin-event-loans", args=[event.pk])).json()
    holders = [row["holder"] for row in body["results"]]
    assert holders == ["Member"]
    assert "@" not in str(body)


@pytest.mark.django_db
def test_event_loans_show_the_borrower_name_normally():
    space, event = _space_with_event("ev-loans-name")
    _loan(space, event, make_user("ev-borrower", display_name="Asha"))
    manager = make_staff(space, username="ev-loans-manager2")
    body = authenticated_client(manager).get(reverse("admin-event-loans", args=[event.pk])).json()
    assert [row["holder"] for row in body["results"]] == ["Asha"]


@pytest.mark.django_db
def test_holders_are_masked_without_a_pii_window(monkeypatch):
    space, event = _space_with_event("ev-loans-mask")
    guest = make_user("ev-guest", display_name="Guest Person")
    _loan(space, event, make_user("ev-borrower2", display_name="Asha"))
    now = timezone.now()
    GuestPass.objects.create(makerspace=space, holder=guest, kind=GuestPass.Kind.EVENT,
                             operation_id=f"event-{event.pk}-reg-1", valid_from=now - timedelta(hours=1),
                             valid_until=now + timedelta(days=1), pass_date=timezone.localdate())
    api = authenticated_client(make_staff(space, username="ev-loans-manager3"))
    shown = api.get(reverse("admin-event-guest-passes", args=[event.pk])).json()["results"]
    assert [row["holder"] for row in shown] == ["Guest Person"]
    monkeypatch.setattr("apps.events.views_event_loans_passes.pii_visible", lambda viewer, space_id: False)
    loans = api.get(reverse("admin-event-loans", args=[event.pk])).json()["results"]
    passes = api.get(reverse("admin-event-guest-passes", args=[event.pk])).json()["results"]
    assert [row["holder"] for row in loans] == [MASK]
    assert [row["holder"] for row in passes] == [MASK]
