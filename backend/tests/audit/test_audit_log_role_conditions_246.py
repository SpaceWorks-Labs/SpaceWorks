"""Decision 246 (lane T4): per-role read access to the audit log (219(e), 219(e-1)).

Rows of several areas are written for two spaces; every built-in role then lists the log of its own
space. Expectations are derived from `apps.audit.areas` and `ROLE_CATALOG`:

* the Space Manager reads every area of the space and a superadmin everything;
* an area role reads only the rows of the areas its actions open (no `view_audit` needed, 219(e-1));
* the handout-only Handover role and roles with no reader action read nothing;
* rows of another space never appear, for any role.
"""
import pytest

from apps.audit import areas
from apps.audit import services as audit
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.r2_superadmin_local.helpers import api, space, superadmin

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/audit-logs"
SEEDED = {
    "lending": "request.accepted", "machines": "machine.created", "events": "event.created",
    "bookings": "booking.created", "shop": "shop.order_placed", "finance": "payment.recorded",
    "people": "member.updated", "platform": "settings.updated",
}
SLUGS = [role.slug for role in ROLE_CATALOG]


def seed(lab):
    for action in SEEDED.values():
        audit.record(None, action, makerspace=lab, meta={"seed": lab.slug})


def listed(client, lab=None):
    response = client.get(URL)
    if response.status_code != 200:
        return response.status_code, None
    rows = response.json()["results"]
    return 200, {(row["action"], row["makerspace"]) for row in rows}


def is_reader(slug):
    granted = ROLE_BY_SLUG[slug].granted_actions
    return "view_audit" in granted or bool(set(areas.READER_ACTIONS) & granted)


def open_areas(slug):
    return areas.areas_for_actions(set(ROLE_BY_SLUG[slug].granted_actions))


def expected_actions(slug):
    opened = open_areas(slug)
    return {action for action in SEEDED.values() if set(areas.areas_for_action(action)) & opened}


@pytest.mark.parametrize("slug", SLUGS)
def test_each_role_reads_only_the_areas_its_actions_open(slug):
    lab, other = space(f"aud-{slug}".replace("_", "-")), space(f"aud-other-{slug}".replace("_", "-"))
    client = api(staff_account(lab, f"aud-actor-{slug}", slug))  # actor first: seeded rows stay newest
    seed(lab)
    seed(other)
    status, rows = listed(client)
    if not is_reader(slug) or slug == "handover":
        assert status in (403, 404) or not rows, (slug, status, rows)
        return
    assert status == 200
    seen_actions = {action for action, space_ref in rows if action in SEEDED.values()}
    assert seen_actions <= expected_actions(slug), (slug, seen_actions - expected_actions(slug))
    # Positive direction only where the area has no per-type narrowing (machines).
    assert (expected_actions(slug) - {SEEDED["machines"]}) <= seen_actions
    other_refs = {space_ref for _action, space_ref in rows if space_ref == other.pk}
    assert not other_refs


def test_the_space_manager_reads_every_seeded_area():
    lab = space("aud-sm")
    client = api(staff_account(lab, "aud-sm-actor", "space_manager"))
    seed(lab)
    status, rows = listed(client)
    assert status == 200
    assert set(SEEDED.values()) <= {action for action, _ref in rows}


def test_handover_and_a_plain_member_read_no_audit_row():
    lab = space("aud-none")
    clients = {slug: api(staff_account(lab, f"aud-none-{slug}", slug)) for slug in ("handover", "member")}
    seed(lab)
    for slug, client in clients.items():
        status, rows = listed(client)
        assert status in (403, 404) or not [a for a, _r in rows if a in SEEDED.values()], slug


def test_an_area_role_without_view_audit_still_reads_its_own_area():
    lab = space("aud-event")
    client = api(staff_account(lab, "aud-event-mgr", "event_manager"))
    seed(lab)
    assert "view_audit" not in ROLE_BY_SLUG["event_manager"].granted_actions
    status, rows = listed(client)
    assert status == 200
    seen = {action for action, _r in rows if action in SEEDED.values()}
    assert seen == {SEEDED["events"]}


def test_the_superadmin_reads_every_space():
    one, two = space("aud-root-a"), space("aud-root-b")
    client = api(superadmin())
    seed(one)
    seed(two)
    status, rows = listed(client)
    assert status == 200
    assert len([1 for action, _r in rows if action == SEEDED["events"]]) >= 2


def test_anonymous_is_refused():
    assert api().get(URL).status_code in (401, 403)
