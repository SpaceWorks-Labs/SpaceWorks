"""The space artwork library, the brand kit and bulk cards from a CSV (decision 344(b)): scoping, refusals,
storage accounting and audit."""
import uuid

import pytest
from django.db.models import F
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.card_designs import asset_library, csv_merge, resolution
from apps.card_designs.models import CardDesign, CardDesignAsset, CardTemplate
from apps.makerspaces.models import Makerspace
from tests.l3_local.helpers import card_space, client, manager, member

pytestmark = pytest.mark.django_db


def _design(space, actor):
    design, _created = resolution.get_or_create(space, "member_cards", actor=actor)
    return design


def _asset(space, kind="background", size=1000):
    asset_id = uuid.uuid4()
    return CardDesignAsset.objects.create(asset_id=asset_id, makerspace=space, kind=kind, ready=True, size_bytes=size,
                                          object_key=f"card-assets/{space.pk}/{asset_id.hex}", content_type="image/png",
                                          width_px=10, height_px=10, mean_colour="#336699")


def test_the_library_lists_only_this_spaces_ready_assets():
    space, other = card_space("lib-a"), card_space("lib-b")
    sm = manager(space)
    design = _design(space, sm)
    mine, _theirs = _asset(space), _asset(other)
    CardDesignAsset.objects.filter(pk=_asset(space).pk).update(ready=False)
    rows = client(sm).get(reverse("admin-card-design-asset-library", args=[design.pk])).json()
    assert [row["asset_id"] for row in rows] == [str(mine.asset_id)]
    assert client(sm).get(reverse("admin-card-design-asset-library", args=[design.pk]), {"kind": "x"}).status_code == 400


def test_a_member_cannot_reach_the_library_or_the_brand_kit():
    space = card_space("lib-rbac")
    design = _design(space, manager(space))
    user, _membership = member(space)
    assert client(user).get(reverse("admin-card-design-asset-library", args=[design.pk])).status_code in (403, 404)
    assert client(user).get(reverse("admin-card-design-brand-kit", args=[design.pk])).status_code in (403, 404)


def test_deleting_an_unused_asset_frees_its_storage_and_is_audited(monkeypatch, django_capture_on_commit_callbacks):
    deleted = []
    monkeypatch.setattr(asset_library, "delete_quietly", deleted.append)
    space = card_space("lib-del")
    sm = manager(space)
    design = _design(space, sm)
    asset = _asset(space, size=5000)
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=F("storage_bytes_used") + 5000)
    before = Makerspace.objects.get(pk=space.pk).storage_bytes_used
    with django_capture_on_commit_callbacks(execute=True):
        response = client(sm).delete(reverse("admin-card-design-asset-library-delete", args=[design.pk, asset.asset_id]))
    assert response.status_code == 204
    assert not CardDesignAsset.objects.filter(pk=asset.pk).exists() and deleted == [asset.object_key]
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == before - 5000
    assert AuditLog.objects.filter(action="card_design.asset_deleted", makerspace=space).exists()


@pytest.mark.parametrize("where", ["draft", "template"])
def test_an_asset_in_use_is_never_deleted(where):
    space = card_space(f"lib-use-{where}")
    sm = manager(space)
    design = _design(space, sm)
    asset = _asset(space)
    document = {**design.document, "front": {**design.document["front"],
                                             "background": {"kind": "image", "asset_id": str(asset.asset_id),
                                                            "fit": "cover", "dim_pct": 0}}}
    if where == "draft":
        CardDesign.objects.filter(pk=design.pk).update(document=document)
    else:
        CardTemplate.objects.create(makerspace=space, name="T", kind="card", stock=design.document["stock"], document=document)
    response = client(sm).delete(reverse("admin-card-design-asset-library-delete", args=[design.pk, asset.asset_id]))
    assert response.status_code == 400 and CardDesignAsset.objects.filter(pk=asset.pk).exists()


def test_another_spaces_asset_cannot_be_deleted_through_my_design():
    space, other = card_space("lib-x1"), card_space("lib-x2")
    sm = manager(space)
    theirs = _asset(other)
    response = client(sm).delete(reverse("admin-card-design-asset-library-delete", args=[_design(space, sm).pk, theirs.asset_id]))
    assert response.status_code == 404 and CardDesignAsset.objects.filter(pk=theirs.pk).exists()


def test_the_brand_kit_offers_valid_space_colours_and_the_font_allow_list():
    space = card_space("brand-kit")
    space.theme_config = {**(space.theme_config or {}), "primary_color": "#0a7", "accent_color": "url(evil)"}
    space.save(update_fields=["theme_config"])
    sm = manager(space)
    body = client(sm).get(reverse("admin-card-design-brand-kit", args=[_design(space, sm).pk])).json()
    assert body["colours"] == [{"label": "Space colour", "hex": "#00AA77"}]
    assert "Outfit" in body["fonts"] and "Gilroy ExtraBold" in body["fonts"]
    assert {logo["source"] for logo in body["logos"]} >= {"space", "symbol"}


CSV = "name,role,shoe_size,blood_group\nAsha Rao,Volunteer,7,O+\nBen Ode,Crew,9,A-\n"


def test_csv_dry_run_reports_columns_and_drops_unknown_and_sensitive_ones():
    columns, unknown, rows = csv_merge.parse(CSV)
    assert columns == ["name", "role"] and unknown == ["shoe_size", "blood_group"]
    assert rows[0] == {"name": "Asha Rao", "role": "Volunteer"}


@pytest.mark.parametrize("bad", ["", "name\n", "name\n" + "x\n" * 201, "a,a\n1,2\n", "name\n" + ("x" * 300_000) + "\n"])
def test_csv_input_is_bounded(bad):
    from rest_framework.exceptions import ValidationError
    with pytest.raises(ValidationError):
        csv_merge.parse(bad)


def test_csv_values_are_cleaned_and_capped():
    _columns, _unknown, rows = csv_merge.parse("name\n\"Asha\x07  Rao\"\n")
    assert rows[0]["name"] == "Asha Rao"


def test_csv_merge_prints_the_published_design_and_audits_it():
    space = card_space("csv-run")
    sm = manager(space)
    design = _design(space, sm)
    CardDesign.objects.filter(pk=design.pk).update(published_document=design.document, published_revision=design.revision)
    url = reverse("admin-card-design-csv-merge", args=[design.pk])
    report = client(sm).post(url, {"csv": CSV}, format="json").json()
    assert report["rows"] == 2 and report["published"] is True and report["unknown_columns"] == ["shoe_size", "blood_group"]
    # Decision 345(e): the preview is the server's render of the PUBLISHED version, the same as the PDF.
    assert len(report["images"]) == 2 and all(image.startswith("data:image/png;base64,") for image in report["images"])
    response = client(sm).post(url, {"csv": CSV, "dry_run": False, "paper": "a4"}, format="json")
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    log = AuditLog.objects.get(action="card_design.csv_merged", makerspace=space)
    assert log.meta["rows"] == 2 and "blood_group" not in log.meta["columns"]


def test_csv_merge_refuses_an_unpublished_design():
    space = card_space("csv-draft")
    sm = manager(space)
    design = _design(space, sm)
    CardDesign.objects.filter(pk=design.pk).update(published_document=None)
    url = reverse("admin-card-design-csv-merge", args=[design.pk])
    assert client(sm).post(url, {"csv": CSV}, format="json").json()["images"] == []  # nothing published to preview
    response = client(sm).post(url, {"csv": CSV, "dry_run": False}, format="json")
    assert response.status_code == 400
