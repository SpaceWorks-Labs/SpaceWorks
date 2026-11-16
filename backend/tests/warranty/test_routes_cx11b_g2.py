"""Warranty routes: host-specific gates; object standing before switch disclosure (520)."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.warranty import storage
from apps.warranty.models import Warranty, WarrantyDocument
from tests.machines.route_support_cx11b_g2 import command, prove, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]
OPERATIONS = [("host", "get"), ("host", "put"), ("presign", "post"), ("documents", "get"),
              ("documents", "post"), ("url", "get"), ("delete", "delete")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("host,key", [("asset", "inventory.warranty"), ("machine", "machines.warranty"),
                                     ("machine", "machines"), ("asset", "loans.enabled")])
@pytest.mark.parametrize("operation,method", OPERATIONS)
def test_warranty_route_effect_and_standing_survive_independent_switches(native, host, key, operation, method,
                                                                      monkeypatch):
    w = world(native)
    if host == "asset":
        product = InventoryProduct.objects.create(makerspace=w.space, name="Warranty drill", tracking_mode="individual")
        subject = InventoryAsset.objects.create(makerspace=w.space, product=product, asset_tag="G2-WARRANTY")
    else:
        subject = w.machine
    warranty = Warranty.objects.create(makerspace=w.space, **{host: subject}, vendor_name="Retained supplier")
    document = WarrantyDocument.objects.create(warranty=warranty,
        object_key=f"warranty/{w.space.pk}/retained.pdf", original_filename="retained.pdf",
        content_type="application/pdf", size_bytes=17, uploaded_by=w.actor)
    new_key = storage.warranty_object_key(w.space.pk, "pdf")
    upload = Mock(return_value={"url": "https://upload.example.test/g2"})
    download = Mock(return_value="https://download.example.test/retained.pdf")
    monkeypatch.setattr(storage, "presigned_upload", upload)
    monkeypatch.setattr(storage, "presigned_get_url", download)
    monkeypatch.setattr(storage, "finalize_upload", lambda *args: None)
    monkeypatch.setattr(storage, "validate_warranty_object", lambda *args:
                        SimpleNamespace(content_type="application/pdf", size=23))
    names = {"host": f"admin-{host}-warranty", "presign": "admin-warranty-document-presign",
             "documents": "admin-warranty-documents", "url": "admin-warranty-document-url",
             "delete": "admin-warranty-document-detail"}
    pk = subject.pk if operation == "host" else document.pk if operation in {"url", "delete"} else warranty.pk
    body = {"vendor_name": "Updated supplier"} if operation == "host" else (
        {"filename": "invoice.pdf", "content_type": "application/pdf"} if operation == "presign" else
        {"object_key": new_key, "original_filename": "new.pdf"})
    audit = {("host", "put"): ("warranty.updated",), ("documents", "post"): ("warranty.document_added",),
             ("delete", "delete"): ("warranty.document_removed",)}.get((operation, method), ())

    def check(response):
        if operation == "host":
            warranty.refresh_from_db()
            assert (response.data["id"], response.data["host_id"], warranty.vendor_name) == (
                warranty.pk, subject.pk, "Updated supplier" if method == "put" else "Retained supplier")
            assert response.data["vendor_name"] == warranty.vendor_name
        elif operation == "presign":
            assert response.data["object_key"].startswith(f"warranty/{w.space.pk}/")
            assert response.data["upload"] == {"url": "https://upload.example.test/g2"}
            assert upload.call_args.args == (response.data["object_key"], "application/pdf")
        elif operation == "documents" and method == "post":
            saved = WarrantyDocument.objects.get(pk=response.data["id"])
            assert (saved.warranty_id, saved.object_key, saved.size_bytes, saved.uploaded_by_id) == (
                warranty.pk, new_key, 23, w.actor.pk)
            assert warranty.documents.count() == 2
        elif operation == "documents":
            assert [(row["id"], row["original_filename"], row["size_bytes"]) for row in response.data] == [
                (document.pk, "retained.pdf", 17)]
        elif operation == "url":
            assert response.data == {"url": "https://download.example.test/retained.pdf"}
            assert download.call_args.args == (document.object_key,)
        else:
            assert not WarrantyDocument.objects.filter(pk=document.pk).exists()
            assert Warranty.objects.filter(pk=warranty.pk).exists()

    prove(w, key, lambda c: command(c, names[operation], method, [pk], body), check,
          status=201 if method == "post" else 204 if method == "delete" else 200,
          audits=audit, off=(404, "capability_disabled"),
          providers=(upload,) if operation == "presign" else (download,) if operation == "url" else ())
