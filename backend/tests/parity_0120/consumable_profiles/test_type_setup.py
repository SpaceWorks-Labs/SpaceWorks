"""Per-type booking defaults, training notes and documents (decision 343 follow-up)."""
import pytest
from django.urls import reverse
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.models import AuditLog
from apps.machines import type_documents, type_setup
from apps.machines.models_type_setup import MachineTypeDocument
from apps.machines.storage import MachineObjectValidationResult
from tests.machines.eta_helpers import enable, owner

from .helpers import client, manager, world

pytestmark = pytest.mark.django_db


def booking_world(slug):
    w = world(slug)
    enable(w.space, "bookings")
    return w


def new_space(w, name="Laser time", **kwargs):
    from apps.bookings import services
    return services.create_space(makerspace=w.space, actor=w.staff, name=name, kind="bench", description="",
                                 capacity=1, location="", is_public=False, machine_type=w.kind.pk, **kwargs)


def test_setup_saves_partially_and_audits_changed_fields():
    w = world("set-save")
    row = type_setup.update(w.staff, w.space, w.kind, {"booking_slot_minutes": 30, "training_notes": "Goggles on."})
    assert (row.booking_slot_minutes, row.training_notes, row.notes_at_job_request) == (30, "Goggles on.", True)
    type_setup.update(w.staff, w.space, w.kind, {"booking_slot_minutes": 30})
    assert AuditLog.objects.filter(action="machine_type_setup.updated", makerspace=w.space).count() == 1
    with pytest.raises(ValidationError):
        type_setup.update(w.staff, w.space, w.kind, {"training_notes": "x" * 10001})


def test_a_new_bookable_space_of_the_type_takes_its_booking_defaults():
    w = booking_world("set-new")
    plain = new_space(w, "Before defaults")
    type_setup.update(w.staff, w.space, w.kind, {"booking_slot_minutes": 45, "booking_buffer_before_minutes": 5,
                                                 "booking_buffer_after_minutes": 10, "booking_approval_mode": "approve"})
    seeded = new_space(w)
    assert (seeded.min_booking_duration_minutes, seeded.buffer_before_minutes, seeded.buffer_after_minutes,
            seeded.approval_mode) == (45, 5, 10, "approve")
    assert plain.approval_mode == "instant"  # spaces made before the defaults are untouched until applied
    explicit = new_space(w, "Explicit", approval_mode="instant")
    assert explicit.approval_mode == "instant" and explicit.min_booking_duration_minutes == 45


def test_apply_to_existing_goes_through_the_bookings_rule_service():
    w = booking_world("set-apply")
    first, second = new_space(w, "A"), new_space(w, "B")
    with pytest.raises(ValidationError):
        type_setup.apply_booking_defaults(w.staff, w.space, w.kind)  # nothing to apply yet
    type_setup.update(w.staff, w.space, w.kind, {"booking_slot_minutes": 60, "booking_approval_mode": "approve"})
    url = reverse("machine-type-booking-defaults-apply", kwargs={"makerspace_id": w.space.pk, "type_id": w.kind.pk})
    response = client(w.staff).post(url)
    assert response.status_code == 200 and sorted(response.data["spaces"]) == sorted([first.pk, second.pk])
    first.refresh_from_db()
    assert first.min_booking_duration_minutes == 60 and first.approval_mode == "approve"
    assert AuditLog.objects.filter(action="machine_type_setup.booking_defaults_applied").count() == 1


def test_setup_api_follows_the_per_type_rule():
    w = world("set-api")
    url = reverse("machine-type-setup", kwargs={"makerspace_id": w.space.pk, "type_id": w.kind.pk})
    assert client(w.staff).patch(url, {"booking_slot_minutes": 0}, format="json").status_code == 400
    assert client(w.staff).patch(url, {"training_notes": "Read the SOP"}, format="json").status_code == 200
    assert client(manager(w, w.kind)).get(url).data["training_notes"] == "Read the SOP"
    from apps.machines.models import MachineType
    other = MachineType.objects.create(makerspace=w.space, slug=f"{w.space.slug}-x", name="X")
    other_url = reverse("machine-type-setup", kwargs={"makerspace_id": w.space.pk, "type_id": other.pk})
    assert client(manager(w, w.kind)).patch(other_url, {"training_notes": "no"}, format="json").status_code == 403


def _fake_storage(monkeypatch, size=2048):
    deleted = []
    monkeypatch.setattr("apps.machines.storage.finalize_upload", lambda key, max_bytes: size)
    monkeypatch.setattr("apps.machines.storage.validate_machine_object",
                        lambda key: MachineObjectValidationResult(size=size, content_type="application/pdf"))
    monkeypatch.setattr("apps.machines.storage.presigned_upload", lambda key, content_type: {"url": "https://u"})
    monkeypatch.setattr("apps.machines.storage.presigned_get_url", lambda key: f"https://get/{key}")
    monkeypatch.setattr("apps.machines.storage.delete_object", lambda key: deleted.append(key))
    return deleted


def test_documents_charge_and_free_storage_and_stay_in_the_space(monkeypatch, django_capture_on_commit_callbacks):
    deleted = _fake_storage(monkeypatch)
    w = world("set-doc")
    key, _upload = type_documents.presign(w.space, "application/pdf", "sop.pdf")
    before = type(w.space).objects.get(pk=w.space.pk).storage_bytes_used
    row = type_documents.attach(w.staff, w.space, w.kind, object_key=key, title="", original_filename="sop.pdf")
    assert row.title == "sop.pdf" and row.size_bytes == 2048
    assert type(w.space).objects.get(pk=w.space.pk).storage_bytes_used == before + 2048
    with pytest.raises(ValidationError):
        type_documents.attach(w.staff, w.space, w.kind, object_key=key, title="again", original_filename="x.pdf")
    other = world("set-doc-other")
    foreign, _ = type_documents.presign(other.space, "application/pdf", "x.pdf")
    with pytest.raises(Exception):
        type_documents.attach(w.staff, w.space, w.kind, object_key=foreign, title="t", original_filename="x.pdf")
    with django_capture_on_commit_callbacks(execute=True):
        type_documents.remove(w.staff, row)
    assert deleted == [key] and type(w.space).objects.get(pk=w.space.pk).storage_bytes_used == before
    assert AuditLog.objects.filter(action__startswith="machine_type_document.", makerspace=w.space).count() == 2


def test_members_read_notes_and_visible_documents_only(monkeypatch):
    _fake_storage(monkeypatch)
    w = world("set-member")
    type_setup.update(w.staff, w.space, w.kind, {"training_notes": "Lid closed.", "notes_at_session_start": False})
    shown = MachineTypeDocument.objects.create(makerspace=w.space, machine_type=w.kind, title="SOP",
                                               object_key=f"machines/{w.space.pk}/a.pdf", original_filename="a.pdf",
                                               content_type="application/pdf", size_bytes=1)
    MachineTypeDocument.objects.create(makerspace=w.space, machine_type=w.kind, title="Staff only", member_visible=False,
                                       object_key=f"machines/{w.space.pk}/b.pdf", original_filename="b.pdf",
                                       content_type="application/pdf", size_bytes=1)
    from tests.machines.certification_helpers import _member
    member, _ = _member(w.space, "set-member-m")
    url = reverse("member-machine-type-guide", kwargs={"makerspace_id": w.space.pk, "type_id": w.kind.pk})
    data = client(member).get(url).data
    assert data["training_notes"] == "Lid closed." and data["notes_at_session_start"] is False
    assert [doc["title"] for doc in data["documents"]] == ["SOP"]
    link = reverse("member-machine-type-document-url", kwargs={"pk": shown.pk})
    assert client(member).get(link).data["url"].startswith("https://get/")
    outsider = owner("set-member-outsider")
    assert client(outsider).get(url).status_code == 403 and client(outsider).get(link).status_code == 403


def test_a_member_cannot_edit_setup():
    w = world("set-deny")
    from apps.machines.consumable_profile_services import space_and_type
    with pytest.raises(NotFound):
        space_and_type(owner("set-deny-m"), w.space.pk, w.kind.pk, write=True)
    url = reverse("machine-type-setup", kwargs={"makerspace_id": w.space.pk, "type_id": w.kind.pk})
    assert client(owner("set-deny-n")).patch(url, {"training_notes": "x"}, format="json").status_code in (403, 404)
