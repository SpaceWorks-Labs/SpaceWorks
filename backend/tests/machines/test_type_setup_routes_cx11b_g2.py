"""Type setup/documents: actual fields, storage links and booking updates, both transports."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.machines import storage
from apps.machines.models_type_setup import MachineTypeDocument, MachineTypeSetup
from tests.machines.route_support_cx11b_g2 import command, personal, prove, world
from tests.rbac_f6_helpers import community_member

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines]
CASES = [("machine-type-setup", "get"), ("machine-type-setup", "patch"),
         ("machine-type-booking-defaults-apply", "post"), ("machine-type-documents", "get"),
         ("machine-type-documents", "post"), ("machine-type-document-presign", "post"),
         ("machine-type-document-detail", "get"), ("machine-type-document-detail", "delete"),
         ("member-machine-type-guide", "get"), ("member-machine-type-document-url", "get")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method,switch", [(name, method, "machines") for name, method in CASES] + [
    ("machine-type-booking-defaults-apply", "post", "bookings")])
def test_type_setup_and_document_effect_survives_machine_switch(native, name, method, switch, monkeypatch):
    w = world(native)
    member_route = name.startswith("member-")
    if member_route:
        user = community_member(w.space, "g2-guide-reader").user
        w.client = personal(user, w.space, native)
        w.foreign = personal(w.outsider, w.other, native)
    setup = MachineTypeSetup.objects.create(makerspace=w.space, machine_type=w.machine_type,
        training_notes="Retained safety notes", booking_slot_minutes=45)
    w.room.machine_type = w.machine_type
    w.room.min_booking_duration_minutes = 15
    w.room.save(update_fields=["machine_type", "min_booking_duration_minutes"])
    document = MachineTypeDocument.objects.create(makerspace=w.space, machine_type=w.machine_type,
        title="Retained manual", original_filename="guide.pdf", content_type="application/pdf", size_bytes=17,
        object_key=storage.machine_object_key(w.space.pk, "pdf"), member_visible=True)
    w.space.storage_bytes_used = 17
    w.space.save(update_fields=["storage_bytes_used"])
    key = storage.machine_object_key(w.space.pk, "pdf")
    upload = Mock(return_value={"url": "https://upload.example.test/manual"})
    download = Mock(return_value="https://download.example.test/manual")
    monkeypatch.setattr(storage, "presigned_upload", upload)
    monkeypatch.setattr(storage, "presigned_get_url", download)
    monkeypatch.setattr(storage, "finalize_upload", lambda *args: None)
    monkeypatch.setattr(storage, "validate_machine_object", lambda *args:
                        SimpleNamespace(size=23, content_type="application/pdf"))
    args = [w.space.pk, w.machine_type.pk]
    if name == "member-machine-type-document-url":
        args = [document.pk]
    elif name == "machine-type-document-detail":
        args.append(document.pk)
    body = {"training_notes": "Updated safety notes"} if method == "patch" else (
        {"filename": "new.pdf", "content_type": "application/pdf"} if name.endswith("presign") else
        {"object_key": key, "title": "New manual", "original_filename": "new.pdf"})
    audit = {("machine-type-setup", "patch"): ("machine_type_setup.updated",),
             ("machine-type-documents", "post"): ("machine_type_document.added",),
             ("machine-type-document-detail", "delete"): ("machine_type_document.removed",),
             ("machine-type-booking-defaults-apply", "post"): (
                 "booking.space_rules_updated", "machine_type_setup.booking_defaults_applied")}

    def check(response):
        if name == "machine-type-setup":
            expected = "Updated safety notes" if method == "patch" else "Retained safety notes"
            assert response.data["training_notes"] == expected
            assert MachineTypeSetup.objects.get(pk=setup.pk).training_notes == expected
        elif name.endswith("defaults-apply"):
            assert response.data == {"spaces": [w.room.pk]}
            w.room.refresh_from_db()
            assert w.room.min_booking_duration_minutes == 45
        elif name.endswith("presign"):
            assert response.data["upload"] == {"url": "https://upload.example.test/manual"}
            assert upload.call_args.args == (response.data["object_key"], "application/pdf")
        elif method == "delete":
            assert not MachineTypeDocument.objects.filter(pk=document.pk).exists()
            w.space.refresh_from_db()
            assert w.space.storage_bytes_used == 0
        elif method == "post":
            saved = MachineTypeDocument.objects.get(pk=response.data["id"])
            assert (saved.object_key, saved.machine_type_id, saved.title, saved.size_bytes) == (
                key, w.machine_type.pk, "New manual", 23)
            w.space.refresh_from_db()
            assert w.space.storage_bytes_used == 40
        elif name == "member-machine-type-guide":
            assert (response.data["machine_type_id"], response.data["training_notes"]) == (
                w.machine_type.pk, "Retained safety notes")
            assert response.data["documents"] == [{"id": document.pk, "title": "Retained manual",
                                                    "content_type": "application/pdf", "size_bytes": 17}]
        elif name == "machine-type-documents":
            assert [(r["id"], r["title"], r["size_bytes"]) for r in response.data] == [(document.pk, "Retained manual", 17)]
        else:
            assert response.data == {"url": "https://download.example.test/manual"}
            assert download.call_args.args == (document.object_key,)

    # Personal membership routes retain their explicit 403 (494/486 person surface).
    prove(w, switch, lambda c: command(c, name, method, args, body), check,
          status=204 if method == "delete" else 201 if method == "post" and not name.endswith("defaults-apply") else 200,
          audits=audit.get((name, method), ()), foreign=(403, "permission_denied") if member_route else (404, "not_found"),
          providers=(upload,) if name.endswith("presign") else (download,) if name in {
              "machine-type-document-detail", "member-machine-type-document-url"} and method == "get" else ())
