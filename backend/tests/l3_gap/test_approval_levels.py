"""#136 / M8: the organisation level of the card-design approval switch is written and enforced,
the space level covers both groups, and the programme and event levels can be cleared."""
import pytest

from apps.audit.models import AuditLog
from apps.card_designs import approval, resolution
from apps.card_designs.models import CardApprovalSetting
from apps.events.organizer_models import EventOrganizer
from tests.l3_gap.helpers import live_event, owned_space, programme
from tests.l3_local.helpers import client, custom_staff, manager

pytestmark = pytest.mark.django_db


def _url(space):
    return f"/api/v1/admin/makerspaces/{space.pk}/card-approval-levels"


def test_space_manager_reads_both_groups_and_linked_organisations():
    space, org = owned_space("gap-al-read", features=("membership.id_programmes", "events.id_cards"))
    body = client(manager(space)).get(_url(space)).json()
    groups = {row["group"]: row for row in body["groups"]}
    assert groups["membership"] == {"group": "membership", "available": True, "default": True, "space": None}
    assert groups["event"]["default"] is False and groups["event"]["available"] is True
    assert body["organisations"] == [{"id": org.pk, "name": org.name, "membership": None, "event": None}]


def test_organisation_level_is_written_audited_and_wins_over_the_space():
    space, org, sm, row = programme("gap-al-org")
    design, _ = resolution.get_or_create(space, "id_programme", programme=row)
    api = client(sm)
    assert approval.required_for(design) is True
    response = api.put(_url(space), {"group": "membership", "organization_id": org.pk, "required": False},
                       format="json")
    assert response.status_code == 200, response.content
    assert CardApprovalSetting.objects.get(makerspace=space, organization=org, group="membership").required is False
    assert approval.required_for(design) is False
    assert AuditLog.objects.filter(action="card_design.approval_setting_changed",
                                   meta__level="organisation").exists()
    api.put(_url(space), {"group": "membership", "required": True}, format="json")
    assert approval.required_for(design) is False  # the organisation is more specific than the space


def test_clearing_a_level_makes_it_inherit_again():
    space, org, sm, row = programme("gap-al-clear")
    design, _ = resolution.get_or_create(space, "id_programme", programme=row)
    api = client(sm)
    api.put(_url(space), {"group": "membership", "organization_id": org.pk, "required": False}, format="json")
    cleared = api.put(_url(space), {"group": "membership", "organization_id": org.pk, "required": None},
                      format="json")
    assert cleared.status_code == 200
    assert not CardApprovalSetting.objects.filter(organization=org).exists()
    assert approval.required_for(design) is True
    assert cleared.json()["organisations"][0]["membership"] is None


def test_space_level_for_event_cards_is_writable():
    space, event = live_event("gap-al-event")
    sm = manager(space)
    design, _ = resolution.get_or_create(space, "event_card", event=event)
    assert approval.required_for(design) is False
    response = client(sm).put(_url(space), {"group": "event", "required": True}, format="json")
    assert response.status_code == 200, response.content
    assert approval.required_for(design) is True


def test_event_organiser_organisation_is_listed_and_enforced():
    from apps.organizations.models import Organization
    space, event = live_event("gap-al-eorg")
    sm = manager(space)
    org = Organization.objects.create(name="Co-host", slug="gap-al-cohost")
    EventOrganizer.objects.create(event=event, organization=org)
    design, _ = resolution.get_or_create(space, "event_card", event=event)
    body = client(sm).get(_url(space)).json()
    assert [row["id"] for row in body["organisations"]] == [org.pk]
    client(sm).put(_url(space), {"group": "event", "organization_id": org.pk, "required": True}, format="json")
    assert approval.required_for(design) is True


def test_unlinked_organisation_and_switched_off_group_are_refused():
    from apps.organizations.models import Organization
    space, _org = owned_space("gap-al-refuse")
    stranger = Organization.objects.create(name="Elsewhere", slug="gap-al-elsewhere")
    api = client(manager(space))
    response = api.put(_url(space), {"group": "membership", "organization_id": stranger.pk, "required": True},
                       format="json")
    assert response.status_code == 400
    assert api.put(_url(space), {"group": "event", "required": True}, format="json").status_code == 400


def test_writes_need_the_settings_authority_and_strangers_see_nothing():
    space, org = owned_space("gap-al-authority")
    staff = custom_staff(space, ["event_manager"], "gap-al-staff")
    response = client(staff).put(_url(space), {"group": "membership", "required": False}, format="json")
    assert response.status_code in (403, 404)
    other, _o = owned_space("gap-al-other")
    assert client(manager(other)).get(_url(space)).status_code == 404


def test_programme_level_reads_and_clears_with_inherited_value():
    space, org, sm, row = programme("gap-al-prog")
    api = client(sm)
    url = f"/api/v1/admin/id-programmes/{row.pk}/approval"
    assert api.get(url).json() == {"required": None, "inherited": True}
    assert api.put(url, {"required": False}, format="json").json() == {"required": False, "inherited": True}
    approval.set_level(sm, space, "membership", False, organization=org)
    assert api.put(url, {"required": None}, format="json").json() == {"required": None, "inherited": False}
    assert api.put(url, {}, format="json").status_code == 400


def test_event_level_null_clears_and_reports_the_inherited_value():
    space, event = live_event("gap-al-evlevel")
    sm = manager(space)
    api = client(sm)
    url = f"/api/v1/admin/events/{event.pk}/card-settings"
    body = api.put(url, {"design_approval_required": True}, format="json").json()
    assert body["design_approval_required"] is True and body["design_approval_inherited"] is False
    body = api.put(url, {"design_approval_required": None}, format="json").json()
    assert body["design_approval_required"] is None
    assert not CardApprovalSetting.objects.filter(event=event).exists()
    # Leaving the key out changes nothing.
    api.put(url, {"design_approval_required": True}, format="json")
    api.put(url, {"extras_visible_to_organizers": False}, format="json")
    assert CardApprovalSetting.objects.get(event=event).required is True
