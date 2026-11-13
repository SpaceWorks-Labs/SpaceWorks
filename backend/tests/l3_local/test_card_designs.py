"""L3 card designs: CAS saves, the four-level approval switch (#128 C-28, #136), publish, API."""
import pytest

from apps.audit.models import AuditLog
from apps.card_designs import approval, designs, resolution
from apps.card_designs.default_templates import build
from apps.card_designs.models import CardApprovalSetting, CardDesign
from tests.l3_local.helpers import card_event, card_space, client, custom_staff, manager

pytestmark = pytest.mark.django_db


def _design(space, actor):
    row, _ = resolution.get_or_create(space, "member_cards", actor=actor)
    return row


def test_space_default_is_seeded_from_classic_and_renders_template_until_published():
    space = card_space("cd-seed")
    sm = manager(space)
    design = _design(space, sm)
    assert design.revision == 1 and design.published_document is None
    document, row = resolution.resolve(space.pk, "member_cards")
    assert row is None and document["stock"] == "cr80-landscape"


def test_save_is_compare_and_swap():
    space = card_space("cd-cas")
    sm = manager(space)
    design = _design(space, sm)
    saved = designs.save(sm, design, build("bold", "member_cards"), expected_revision=1)
    assert saved.revision == 2
    with pytest.raises(designs.DesignConflict):
        designs.save(sm, saved, build("minimal", "member_cards"), expected_revision=1)


def test_a_draft_saves_unreadable_text_but_publish_refuses_it():
    from rest_framework.exceptions import ValidationError
    space = card_space("cd-contrast")
    sm = manager(space)
    design = _design(space, sm)
    document = build("classic", "member_cards")
    document["front"]["background"] = {"kind": "colour", "colour": "#FFFFFF"}
    for layer in document["front"]["layers"]:
        if layer["kind"] in ("text", "data_field"):
            layer["colour"] = "#F4F4F4"
    saved = designs.save(sm, design, document, expected_revision=1)
    assert saved.revision == 2
    with pytest.raises(ValidationError) as refused:
        designs.publish(sm, saved)
    assert "contrast" in refused.value.detail


def _event_design(space, sm):
    event = card_event(space)
    row, _ = resolution.get_or_create(space, "event_card", actor=sm, event=event)
    return event, row


def test_non_approver_edit_needs_approval_and_cards_keep_the_published_version():
    space = card_space("cd-approve", features=("events.id_cards",))
    sm = manager(space)
    editor = custom_staff(space, ["event_manager"], "cardeditor")
    approval.set_level(sm, space, "event", True)
    event, design = _event_design(space, sm)
    designs.publish(sm, design)
    published = CardDesign.objects.get(pk=design.pk).published_document
    design = designs.save(editor, CardDesign.objects.get(pk=design.pk), build("bold", "event_card"),
                          expected_revision=design.revision)
    assert approval.needs_approval(editor, design)
    with pytest.raises(Exception):
        designs.publish(editor, design)
    designs.submit(editor, design)
    design.refresh_from_db()
    assert design.status == "pending_approval"
    assert resolution.resolve(space.pk, "event_card", event_id=event.pk)[0] == published
    designs.decide(sm, design, approve=True)
    design.refresh_from_db()
    assert design.status == "published" and design.published_revision == design.revision
    assert resolution.resolve(space.pk, "event_card", event_id=event.pk)[0] == design.published_document
    assert AuditLog.objects.filter(action__in=["card_design.submitted", "card_design.approved",
                                               "card_design.published"]).count() == 4


def test_switch_off_lets_editors_publish_directly():
    space = card_space("cd-switch", features=("events.id_cards",))
    sm = manager(space)
    editor = custom_staff(space, ["event_manager"], "cardeditor2")
    _event, design = _event_design(space, sm)
    assert not approval.needs_approval(editor, design)
    designs.publish(editor, design)
    assert CardDesign.objects.get(pk=design.pk).status == "published"


def test_most_specific_level_wins_for_events():
    space = card_space("cd-levels", features=("events.id_cards",))
    from apps.events.models import Event
    from django.utils import timezone
    event = Event.objects.create(makerspace=space, title="Night", starts_at=timezone.now(),
                                 ends_at=timezone.now() + timezone.timedelta(hours=2))
    row, _ = resolution.get_or_create(space, "event_card", event=event)
    assert approval.required_for(row) is False
    approval.set_level(None, space, "event", True)
    assert approval.required_for(row) is True
    approval.set_level(None, space, "event", False, event=event)
    assert approval.required_for(row) is False
    assert CardApprovalSetting.objects.filter(makerspace=space).count() == 2


def test_rejecting_keeps_published_and_editing_withdraws_a_pending_request():
    space = card_space("cd-reject", features=("events.id_cards",))
    sm = manager(space)
    editor = custom_staff(space, ["event_manager"], "cardeditor3")
    approval.set_level(sm, space, "event", True)
    _event, design = _event_design(space, sm)
    designs.submit(editor, design)
    designs.decide(sm, design, approve=False, note="Logo too small")
    design.refresh_from_db()
    assert design.status == "draft"
    designs.submit(editor, design)
    designs.save(editor, CardDesign.objects.get(pk=design.pk), build("bold", "event_card"),
                 expected_revision=design.revision)
    assert not design.approvals.filter(decision="pending").exists()


def test_api_list_save_publish_and_export_import():
    space = card_space("cd-api")
    sm = manager(space)
    api = client(sm)
    listed = api.get(f"/api/v1/admin/makerspaces/{space.pk}/card-designs")
    assert listed.status_code == 200, listed.content
    design_id = listed.json()[0]["id"]
    saved = api.put(f"/api/v1/admin/card-designs/{design_id}", {"document": build("bold", "member_cards"),
                                                               "revision": 1}, format="json")
    assert saved.status_code == 200, saved.content
    conflict = api.put(f"/api/v1/admin/card-designs/{design_id}", {"document": build("minimal", "member_cards"),
                                                                  "revision": 1}, format="json")
    assert conflict.status_code == 409
    assert api.post(f"/api/v1/admin/card-designs/{design_id}/publish").status_code == 200
    exported = api.get(f"/api/v1/admin/card-designs/{design_id}/export").json()
    assert exported["kind"] == "spaceworks-card-design"
    imported = api.post(f"/api/v1/admin/card-designs/{design_id}/import", {"file": exported}, format="json")
    assert imported.status_code == 200, imported.content
    preview = api.post(f"/api/v1/admin/card-designs/{design_id}/preview",
                       {"document": build("classic", "member_cards"), "format": "png"}, format="json")
    assert preview.status_code == 200 and preview["Content-Type"] == "image/png"
    from apps.card_designs.default_templates import LABELS, THEMES
    # decision 314: the Card Studio gallery grew; the count is every built-in template in every theme
    assert len(api.get(f"/api/v1/admin/card-designs/{design_id}/templates").json()) == len(LABELS) * len(THEMES)


def test_api_plan_override_and_outsiders_get_404():
    from apps.makerspaces.models import MembershipPlan
    space = card_space("cd-plan")
    other = card_space("cd-other")
    sm = manager(space)
    plan = MembershipPlan.objects.create(makerspace=space, name="Monthly")
    created = client(sm).post(f"/api/v1/admin/makerspaces/{space.pk}/card-designs", {"plan_id": plan.pk},
                              format="json")
    assert created.status_code == 201, created.content
    outsider = manager(other, "outsider")
    assert client(outsider).get(f"/api/v1/admin/card-designs/{created.json()['id']}").status_code == 404


def test_module_off_hides_designs():
    space = card_space("cd-off")
    sm = manager(space)
    design = _design(space, sm)
    space.enabled_modules = [key for key in space.enabled_modules if key != "membership"]
    space.save(update_fields=["enabled_modules"])
    assert client(sm).get(f"/api/v1/admin/card-designs/{design.pk}").status_code == 404
