"""Decision 246: the personal inbox (module switch, anonymous, validation, per-user and per-space isolation)."""
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.makerspaces.role_catalog import ROLE_CATALOG
from apps.notifications.models_inbox import NotificationInboxRow
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]


def _space(slug, notifications=True):
    space = make_space(slug)
    modules = set(space.enabled_modules or [])
    space.enabled_modules = sorted(modules | {"notifications"} if notifications else modules - {"notifications"})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"notifications.member_inbox"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    return space


def _row(space, user, title="Hello"):
    return NotificationInboxRow.objects.create(
        makerspace=space, user=user, feature="hardware_requests", event="issued", event_key=uuid4(),
        audience="staff", title=title, summary="")


def _url(space, tail=""):
    return f"/api/v1/notifications/inbox/{space.pk}{tail}"


def test_anonymous_is_refused_on_every_inbox_route():
    space = _space("inb-anon")
    anon = APIClient()
    assert anon.get(_url(space)).status_code in (401, 403)
    assert anon.get(_url(space, "/unread-count")).status_code in (401, 403)
    assert anon.post(_url(space, "/read-all"), {}, format="json").status_code in (401, 403)


@pytest.mark.parametrize("slug", SLUGS)
def test_a_person_only_ever_sees_their_own_rows_whatever_their_role(slug):
    space = _space(f"inb-own-{slug}".replace("_", "-"))
    me = staff_account(space, f"inb-me-{slug}", slug)
    other = staff_account(space, f"inb-other-{slug}", "space_manager")
    _row(space, me, "mine")
    _row(space, other, "theirs")
    response = authenticated_client(me).get(_url(space))
    if response.status_code == 200:
        titles = [row["title"] for row in response.json()["results"]]
        assert "theirs" not in titles
    else:
        assert response.status_code in (403, 404)


def test_the_module_switch_removes_the_inbox():
    space = _space("inb-off", notifications=False)
    boss = staff_account(space, "inb-off-boss", "space_manager")
    _row(space, boss)
    assert authenticated_client(boss).get(_url(space)).status_code in (403, 404)


def test_filter_validation_and_another_spaces_inbox_are_refused():
    mine, theirs = _space("inb-iso-a"), _space("inb-iso-b")
    boss = staff_account(mine, "inb-iso-boss", "space_manager")
    client = authenticated_client(boss)
    assert client.get(_url(mine), {"feature": "not-a-feature"}).status_code == 400
    assert client.get(_url(theirs)).status_code in (403, 404)
    assert client.get(_url(theirs, "/unread-count")).status_code in (403, 404)


def test_read_all_marks_only_my_rows_in_this_space_and_is_repeatable():
    mine, theirs = _space("inb-read-a"), _space("inb-read-b")
    me = staff_account(mine, "inb-read-me", "space_manager")
    other = staff_account(mine, "inb-read-other", "space_manager")
    _row(mine, me)
    _row(mine, other)
    _row(theirs, me)
    client = authenticated_client(me)
    assert client.post(_url(mine, "/read-all"), {}, format="json").status_code == 200
    assert client.post(_url(mine, "/read-all"), {}, format="json").status_code == 200
    assert NotificationInboxRow.objects.filter(user=me, makerspace=mine, read_at__isnull=False).count() == 1
    assert NotificationInboxRow.objects.filter(user=other, read_at__isnull=False).count() == 0
    assert NotificationInboxRow.objects.filter(makerspace=theirs, read_at__isnull=False).count() == 0
