"""Events glue: a Studio (v3) certificate design saves, issues, passes the approval gate and renders; v2 stays as it was."""
import pytest

from apps.events.certificate_rendering import render_certificate_pdf
from apps.events.certificates.shared_render import uses_shared
from apps.events.certificates.signatories import require_render_released
from apps.events.certificates.signatory_commands import approve, pending_for, save_signatory, set_approval_required
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.services_certificate_templates import save_template
from tests.events.checkin_helpers import make_member, make_staff, register
from tests.events.programme.certificates.test_layers import document as v2_document
from tests.idcards_best.certs.helpers import ended_event, issue

from .helpers import certificate, layer, signature

pytestmark = pytest.mark.django_db(transaction=True)


def studio_document():
    return certificate([
        layer("text", 20, 60, 200, 20, text="{{recipient}} - {{event}} - {{achievement}} {{hours}}", font_size_pt=24),
        signature(1, x=200, y=150, w=70, h=40)])


def _world(slug):
    space, event = ended_event(slug)
    space.enabled_features = [*space.enabled_features, "events.certificate_designer"]
    space.save(update_fields=("enabled_features",))
    staff = make_staff(space)
    director = make_member(space, "director", display_name="Dr Director")
    return space, event, staff, director


def _attend(event, space, name):
    return register(event, make_member(space, name), status="attended").pk


def test_a_studio_design_saves_issues_freezes_its_signatory_and_renders_the_same_bytes_twice():
    space, event, staff, director = _world("cert-studio-flow")
    save_signatory(event, actor=staff, slot=1, name="Dr Director", title="Director")
    revision = save_template(event, actor=staff, parameters=studio_document())
    assert revision.parameters["version"] == 3 and revision.parameters["kind"] == "certificate"
    row = issue(event, "registration", _attend(event, space, "studio-a"), activate=False)
    snapshot = row.layout_snapshot
    assert snapshot["version"] == 3 and (snapshot["page_width_mm"], snapshot["page_height_mm"]) == (297.0, 210.0)
    assert snapshot["signatures"]["1"]["name"] == "Dr Director"
    assert {item["kind"] for item in snapshot["front"]["layers"]} >= {"verify_qr", "certificate_id"}  # added at issuance
    assert uses_shared(snapshot)
    first = render_certificate_pdf(row)
    assert first.startswith(b"%PDF") and render_certificate_pdf(row) == first


def test_the_approval_gate_is_unchanged_for_a_studio_design():
    space, event, staff, director = _world("cert-studio-gate")
    save_signatory(event, actor=staff, slot=1, name="Dr Director", title="Director", member_id=director.pk)
    set_approval_required(event, actor=staff, required=True)
    revision = save_template(event, actor=staff, parameters=studio_document())
    row = issue(event, "registration", _attend(event, space, "gate-a"), activate=False)
    with pytest.raises(ProgrammeConflict):
        require_render_released(row)
    waiting = pending_for(director, space.pk)
    assert [(item["template_revision_id"], item["approved"]) for item in waiting] == [(revision.pk, False)]
    approve(event.pk, actor=director, signatory_id=waiting[0]["signatory_id"], template_revision_id=revision.pk)
    require_render_released(row)
    assert render_certificate_pdf(row).startswith(b"%PDF")


def test_a_studio_design_needs_its_signatory_like_a_v2_one():
    from rest_framework.exceptions import ValidationError
    _space, event, staff, _director = _world("cert-studio-needs")
    with pytest.raises(ValidationError):
        save_template(event, actor=staff, parameters=studio_document())


def test_bulk_issuance_renders_every_recipient_through_the_shared_renderer():
    space, event, staff, _director = _world("cert-studio-bulk")
    save_signatory(event, actor=staff, slot=1, name="Dr Director", title="Director")
    save_template(event, actor=staff, parameters=studio_document())
    rows = [issue(event, "registration", _attend(event, space, f"bulk-{n}"), activate=False) for n in range(3)]
    pdfs = [render_certificate_pdf(row) for row in rows]
    assert all(uses_shared(row.layout_snapshot) for row in rows)
    assert all(pdf.startswith(b"%PDF") for pdf in pdfs) and len(set(pdfs)) == 3  # each has its own name and serial


def test_a_v2_design_keeps_the_old_renderer_while_the_switch_is_off(settings):
    settings.CERTIFICATE_SHARED_RENDERER = False
    space, event, staff, _director = _world("cert-v2-off")
    save_template(event, actor=staff, parameters=v2_document())
    row = issue(event, "registration", _attend(event, space, "v2-off"), activate=False)
    assert row.layout_snapshot["version"] == 2 and "renderer" not in row.layout_snapshot and not uses_shared(row.layout_snapshot)
    assert render_certificate_pdf(row).startswith(b"%PDF")


def test_the_switch_pins_the_shared_renderer_into_new_v2_snapshots_only(settings):
    settings.CERTIFICATE_SHARED_RENDERER = True
    space, event, staff, _director = _world("cert-v2-on")
    save_template(event, actor=staff, parameters=v2_document())
    row = issue(event, "registration", _attend(event, space, "v2-on"), activate=False)
    assert row.layout_snapshot["renderer"] == "shared" and uses_shared(row.layout_snapshot)
    first = render_certificate_pdf(row)
    settings.CERTIFICATE_SHARED_RENDERER = False  # the choice is frozen per certificate
    assert uses_shared(row.layout_snapshot) and render_certificate_pdf(row) == first
