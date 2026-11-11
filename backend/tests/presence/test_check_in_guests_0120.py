"""Release 0.12.0 U1: staff check-in search for live guest-pass holders (minimal fields)."""
import pytest
from django.urls import reverse

from apps.makerspaces import guest_pass_issue
from apps.makerspaces.models import MakerspaceWaiver
from tests.makerspaces.test_guest_passes import _space as pass_space
from tests.makerspaces.test_membership_j1 import manager, user
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)


def _url(space):
    return reverse("admin-presence-check-in-guests", kwargs={"makerspace_id": space.pk})


def test_search_returns_only_live_holders_with_minimal_fields():
    space = pass_space("ci-guests")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"presence"})
    space.save(update_fields=["enabled_modules"])
    MakerspaceWaiver.objects.create(makerspace=space, version="v1", body="Sign", is_active=True)
    desk = manager(space, "ci-desk")
    holder = user("ci-holder")
    holder.display_name = "Gina Guest"
    holder.save(update_fields=["display_name"])
    expired = user("ci-expired")
    expired.display_name = "Gina Expired"
    expired.save(update_fields=["display_name"])
    guest_pass_issue.issue_staff_pass(desk, space, holder)
    old, _ = guest_pass_issue.issue_staff_pass(desk, space, expired)
    type(old).objects.filter(pk=old.pk).update(status="expired")
    client = authenticated_client(desk)
    rows = client.get(_url(space), {"q": "Gin"}).json()["results"]
    assert [row["display_name"] for row in rows] == ["Gina Guest"]
    assert set(rows[0]) == {"id", "display_name", "pass_valid_until", "waiver_on_file"}
    assert rows[0]["waiver_on_file"] is False
    assert client.get(_url(space), {"q": "G"}).status_code == 400


def test_other_spaces_staff_and_plain_members_are_refused():
    space = pass_space("ci-guests2")
    stranger = manager(pass_space("ci-guests3"), "ci-stranger")
    assert authenticated_client(stranger).get(_url(space), {"q": "ab"}).status_code in (403, 404)
    assert authenticated_client(user("ci-plain")).get(_url(space), {"q": "ab"}).status_code in (403, 404)
