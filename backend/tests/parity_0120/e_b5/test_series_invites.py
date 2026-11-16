"""B12/B14: a series allowlist admits an email to every occurrence, never consumed, off means removed."""
import pytest
from django.urls import reverse
from rest_framework.exceptions import NotFound

from apps.events import invites, series_invites
from apps.events.models import EventInvite
from tests.events.collab_helpers import client_for
from tests.parity_0120.e_b5.helpers import attach_series, verified_member, world
from apps.managed_hosting.extra_quotas import ExtraQuotaReached

pytestmark = pytest.mark.django_db
FEATURES = ("events.invites", "events.series_invites")


def test_allowlisted_email_resolves_for_an_occurrence_without_being_consumed():
    space, event, staff = world("si-a", *FEATURES)
    series = attach_series(event, space)
    guest = verified_member(space, "si-guest")
    rows, skipped = series_invites.add(series, actor=staff, emails=[guest.email, guest.email.upper()])
    assert len(rows) == 1 and skipped == 0
    for _ in range(2):
        invite = invites.resolve_for_account(event, guest, actor=guest)
        assert invite is not None and invite.series_id == series.pk
    assert EventInvite.objects.get(pk=invite.pk).uses == 0


def test_a_stranger_or_a_revoked_entry_is_not_admitted():
    space, event, staff = world("si-b", *FEATURES)
    series = attach_series(event, space)
    guest, stranger = verified_member(space, "si-g"), verified_member(space, "si-s")
    rows, _ = series_invites.add(series, actor=staff, emails=[guest.email])
    assert invites.resolve_for_account(event, stranger, actor=stranger) is None
    series_invites.revoke(rows[0], actor=staff)
    assert invites.resolve_for_account(event, guest, actor=guest) is None


def test_switch_off_removes_the_allowlist_everywhere():
    space, event, staff = world("si-c", "events.invites")
    series = attach_series(event, space)
    guest = verified_member(space, "si-off")
    EventInvite.objects.create(series=series, makerspace=space,
                               email_digest=invites.code_digest(guest.email, "email"))
    assert invites.resolve_for_account(event, guest, actor=guest) is None
    url = reverse("admin-event-series-invites", kwargs={"pk": series.pk})
    assert client_for(staff).get(url).status_code in (403, 404)


def test_routes_add_list_and_revoke_with_cross_tenant_404():
    space, event, staff = world("si-d", *FEATURES)
    series = attach_series(event, space)
    url = reverse("admin-event-series-invites", kwargs={"pk": series.pk})
    created = client_for(staff).post(url, {"emails": ["a@example.test", "b@example.test"]}, format="json")
    assert created.status_code == 201 and len(created.data["created"]) == 2
    assert "a@example.test" not in str(created.data)  # digests only
    assert client_for(staff).get(url).data["count"] == 2
    entry = created.data["created"][0]["id"]
    revoke = reverse("admin-event-series-invite-revoke", kwargs={"pk": entry})
    assert client_for(staff).post(revoke, {}, format="json").status_code == 200
    _s, _e, other_staff = world("si-e", *FEATURES)
    assert client_for(other_staff).get(url).status_code == 404


def test_series_invites_limit_refuses_new_entries_only():
    space, event, staff = world("si-f", *FEATURES)
    series = attach_series(event, space)
    space.resource_limit_overrides = {"series_invites": 1}
    space.save(update_fields=["resource_limit_overrides"])
    series_invites.add(series, actor=staff, emails=["one@example.test"])
    with pytest.raises(ExtraQuotaReached):
        series_invites.add(series, actor=staff, emails=["two@example.test"])
