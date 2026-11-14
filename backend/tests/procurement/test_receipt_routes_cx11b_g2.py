"""Receipt routes: resolve the scoped stream first (481/494/520); real storage boundary only is mocked."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.procurement import storage
from apps.procurement.models import ToBuyItem, ToBuyReceipt
from tests.machines.route_support_cx11b_g2 import command, prove, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]
CASES = [("to-buy-receipt-presign", "post"), ("to-buy-receipt-list", "get"),
         ("to-buy-receipt-list", "post"), ("to-buy-receipt-url", "get"), ("to-buy-receipt-detail", "delete")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("kind,key", [("hardware", "inventory.tobuy"), ("printing", "machines.tobuy"),
                                     ("printing", "machines"), ("hardware", "loans.enabled")])
@pytest.mark.parametrize("name,method", CASES)
def test_receipts_restore_same_attachment_and_authority(native, kind, key, name, method, monkeypatch):
    w = world(native)
    item = ToBuyItem.objects.create(makerspace=w.space, name="Receipt purchase", kind=kind,
                                   machine_type=w.machine_type if kind == "printing" else None)
    receipt = ToBuyReceipt.objects.create(to_buy_item=item,
        object_key=storage.receipt_object_key(w.space.pk, "pdf"), uploaded_by=w.actor)
    new_key = storage.receipt_object_key(w.space.pk, "pdf")
    upload = Mock(return_value={"url": "https://upload.example.test/receipt"})
    download = Mock(return_value="https://download.example.test/receipt")
    finalized = Mock(return_value=SimpleNamespace(size=19, content_type="application/pdf"))
    monkeypatch.setattr(storage, "presigned_upload", upload)
    monkeypatch.setattr(storage, "presigned_get_url", download)
    monkeypatch.setattr(storage, "finalize_receipt_upload", finalized)
    pk = receipt.pk if name in {"to-buy-receipt-url", "to-buy-receipt-detail"} else item.pk
    body = {"filename": "receipt.pdf", "content_type": "application/pdf"} if name.endswith("presign") else {
        "object_key": new_key}

    def check(response):
        if name.endswith("presign"):
            assert response.data["object_key"].startswith(f"procurement/{w.space.pk}/")
            assert response.data["upload"] == {"url": "https://upload.example.test/receipt"}
            assert upload.call_args.args == (response.data["object_key"], "application/pdf")
        elif name.endswith("url"):
            assert response.data == {"url": "https://download.example.test/receipt"}
            assert download.call_args.args == (receipt.object_key,)
        elif method == "delete":
            assert not ToBuyReceipt.objects.filter(pk=receipt.pk).exists()
            assert ToBuyItem.objects.filter(pk=item.pk).exists()
        elif method == "post":
            saved = ToBuyReceipt.objects.get(pk=response.data["id"])
            assert (saved.to_buy_item_id, saved.object_key, saved.uploaded_by_id) == (item.pk, new_key, w.actor.pk)
            assert item.receipts.count() == 2
            w.space.refresh_from_db()
            assert w.space.storage_bytes_used == 19
            assert finalized.call_args.args[1] == new_key
        else:
            assert [(r["id"], r["uploaded_by"]) for r in response.data] == [(receipt.pk, w.actor.pk)]

    prove(w, key, lambda c: command(c, f"procurement:{name}", method, [pk], body), check,
          status=201 if method == "post" else 204 if method == "delete" else 200,
          audits=("procurement.receipt_added",) if name.endswith("list") and method == "post" else
          ("procurement.receipt_removed",) if method == "delete" else (), off=(404, "not_found"),
          providers=(upload,) if name.endswith("presign") else (download,) if name.endswith("url") else
          (finalized,) if method == "post" else ())
