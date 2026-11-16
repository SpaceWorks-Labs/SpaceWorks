"""Card templates: gallery, save from a design, edit, duplicate, export/import, apply (keeping data fields), RBAC, limit."""
import pytest
from django.urls import reverse

from apps.card_designs import resolution
from apps.card_designs.models import CardDesign, CardTemplate
from tests.l3_local.helpers import card_space, client, manager, member

from .conftest import document, layer, png

pytestmark = pytest.mark.django_db


def _design(space, actor, doc=None):
    row, _created = resolution.get_or_create(space, "member_cards", actor=actor)
    if doc is not None:
        CardDesign.objects.filter(pk=row.pk).update(document=doc)
        row.refresh_from_db()
    return row


def _list(api, space, **query):
    return api.get(reverse("admin-card-templates", kwargs={"makerspace_id": space.pk}), query)


def _create(api, space, design, name="Mine"):
    return api.post(reverse("admin-card-templates", kwargs={"makerspace_id": space.pk}),
                    {"design_id": design.pk, "name": name, "description": "d"}, format="json")


def test_the_gallery_lists_builtins_and_space_templates_without_documents():
    space = card_space("tpl-gallery")
    owner = manager(space)
    api = client(owner)
    rows = _list(api, space).json()
    builtin = [row for row in rows if row["source"] == "builtin"]
    assert {"builtin:studio_lanyard:dark", "builtin:aurora:light"} <= {row["id"] for row in builtin}
    assert all("document" not in row for row in rows)
    assert _list(api, space, source="space").json() == []
    assert {row["orientation"] for row in builtin} == {"portrait", "landscape"}


def test_save_a_design_as_a_template_then_read_rename_duplicate_delete():
    space = card_space("tpl-crud")
    owner = manager(space)
    api = client(owner)
    design = _design(space, owner)
    created = _create(api, space, design)
    assert created.status_code == 201 and created.json()["document"]["version"] == 3
    pk = created.json()["id"]
    assert _create(api, space, design).status_code == 400                      # the name is unique per space
    assert _list(api, space, source="space").json()[0]["name"] == "Mine"
    detail = reverse("admin-card-template", kwargs={"pk": pk})
    assert api.get(detail).json()["document"]["stock"] == design.document["stock"]
    assert api.patch(detail, {"name": "Renamed"}, format="json").json()["name"] == "Renamed"
    copy = api.post(reverse("admin-card-template-duplicate", kwargs={"pk": pk}))
    assert copy.status_code == 201 and copy.json()["name"].startswith("Renamed copy")
    assert api.delete(detail).status_code == 204 and CardTemplate.objects.filter(pk=pk).count() == 0


def test_writes_are_audited():
    from apps.audit.models import AuditLog
    space = card_space("tpl-audit")
    owner = manager(space)
    api = client(owner)
    pk = _create(api, space, _design(space, owner)).json()["id"]
    api.delete(reverse("admin-card-template", kwargs={"pk": pk}))
    actions = set(AuditLog.objects.filter(makerspace=space).values_list("action", flat=True))
    assert {"card_template.created", "card_template.deleted"} <= actions


def test_another_space_and_a_plain_member_get_404():
    space, other = card_space("tpl-own"), card_space("tpl-other")
    owner = manager(space)
    pk = _create(client(owner), space, _design(space, owner)).json()["id"]
    outsider = client(manager(other, "outsider"))
    assert outsider.get(reverse("admin-card-template", kwargs={"pk": pk})).status_code == 404
    assert _list(outsider, space).status_code == 404
    user, _membership = member(space)
    plain = client(user)
    assert _list(plain, space).status_code == 404
    assert plain.get(reverse("admin-card-template", kwargs={"pk": pk})).status_code == 404


def test_the_card_templates_limit_refuses_a_new_template_when_set():
    space = card_space("tpl-limit")
    space.resource_limit_overrides = {"card_templates": 1}
    space.save(update_fields=["resource_limit_overrides"])
    owner = manager(space)
    api = client(owner)
    design = _design(space, owner)
    assert _create(api, space, design, "One").status_code == 201
    assert _create(api, space, design, "Two").status_code == 409


def test_apply_a_builtin_keeps_the_data_fields_the_template_lacks():
    space = card_space("tpl-apply")
    owner = manager(space)
    api = client(owner)
    bound = layer("data_field", 3, 5, 40, 6, field="blood_group", font_family="Outfit", font_weight=400, font_size_pt=9,
                  colour="#142C2A")
    design = _design(space, owner, document([bound], stock="cr80-landscape"))
    reply = api.post(reverse("admin-card-design-apply-template", kwargs={"pk": design.pk}),
                     {"template": "builtin:studio_lanyard:dark", "expected_revision": design.revision}, format="json")
    assert reply.status_code == 200, reply.content
    body = reply.json()
    assert body["unplaced_fields"] == ["blood_group"]
    saved = CardDesign.objects.get(pk=design.pk)
    assert saved.document["stock"] == "cr80-portrait" and saved.revision == design.revision + 1
    fields = [row.get("field") for row in saved.document["front"]["layers"]]
    assert "blood_group" in fields and any(row["name"] == "Background lettering" for row in saved.document["front"]["layers"])
    assert saved.document["front"]["layers"][0]["id"] != bound["id"]


def test_apply_is_compare_and_swap_and_can_skip_the_data_field_carry_over():
    space = card_space("tpl-cas")
    owner = manager(space)
    api = client(owner)
    bound = layer("data_field", 3, 5, 40, 6, field="certifications", font_family="Outfit", font_weight=400, font_size_pt=9,
                  colour="#142C2A")
    design = _design(space, owner, document([bound], stock="cr80-landscape"))
    url = reverse("admin-card-design-apply-template", kwargs={"pk": design.pk})
    assert api.post(url, {"template": "builtin:aurora:light", "expected_revision": design.revision + 5}, format="json").status_code == 409
    ok = api.post(url, {"template": "builtin:aurora:light", "expected_revision": design.revision, "keep_fields": False},
                  format="json")
    assert ok.status_code == 200 and ok.json()["unplaced_fields"] == []


def test_apply_a_saved_template_and_refuse_one_from_another_space():
    space, other = card_space("tpl-saved"), card_space("tpl-foreign")
    owner, stranger = manager(space), manager(other, "stranger")
    api = client(owner)
    design = _design(space, owner)
    pk = _create(api, space, design, "Saved").json()["id"]
    foreign = _design(other, stranger)
    foreign_pk = _create(client(stranger), other, foreign, "Foreign").json()["id"]
    url = reverse("admin-card-design-apply-template", kwargs={"pk": design.pk})
    assert api.post(url, {"template": pk, "expected_revision": design.revision}, format="json").status_code == 200
    design.refresh_from_db()
    assert api.post(url, {"template": foreign_pk, "expected_revision": design.revision}, format="json").status_code == 404


def test_export_and_import_carry_the_images_and_refuse_newer_formats(store):
    space = card_space("tpl-file")
    owner = manager(space)
    api = client(owner)
    from apps.card_designs import templates_files
    asset_id = templates_files._create_asset(owner, space, "image", png((30, 30)))
    doc = document([layer("image", 5, 5, 20, 20, asset_id=asset_id, fit="cover")], stock="cr80-portrait")
    design = _design(space, owner, doc)
    pk = _create(api, space, design, "With image").json()["id"]
    exported = api.get(reverse("admin-card-template-export", kwargs={"pk": pk})).json()
    assert exported["format"] == "spaceworks.card-template" and exported["format_version"] == 1
    assert exported["document"]["front"]["layers"][0]["asset_id"] == "ref:1" and len(exported["assets"]) == 1
    target = card_space("tpl-file-target")
    importer = manager(target, "importer")
    imported = client(importer).post(reverse("admin-card-template-import", kwargs={"makerspace_id": target.pk}),
                                     {"file": exported}, format="json")
    assert imported.status_code == 201, imported.content
    new_asset = imported.json()["document"]["front"]["layers"][0]["asset_id"]
    assert new_asset != asset_id and not new_asset.startswith("ref:")
    from apps.card_designs.models import CardDesignAsset
    assert CardDesignAsset.objects.filter(makerspace=target, asset_id=new_asset, ready=True).exists()
    newer = {**exported, "format_version": 2}
    refused = client(importer).post(reverse("admin-card-template-import", kwargs={"makerspace_id": target.pk}),
                                    {"file": newer}, format="json")
    assert refused.status_code == 400
    junk = client(importer).post(reverse("admin-card-template-import", kwargs={"makerspace_id": target.pk}),
                                 {"file": {"format": "other"}}, format="json")
    assert junk.status_code == 400


def test_import_refuses_a_document_that_names_an_image_the_file_lacks():
    space = card_space("tpl-missing")
    api = client(manager(space))
    doc = document([layer("image", 5, 5, 20, 20, asset_id="ref:9", fit="cover")])
    reply = api.post(reverse("admin-card-template-import", kwargs={"makerspace_id": space.pk}),
                     {"file": {"format": "spaceworks.card-template", "format_version": 1, "name": "x", "document": doc,
                               "assets": []}}, format="json")
    assert reply.status_code == 400


def test_the_openapi_schema_documents_every_template_route():
    from drf_spectacular.generators import SchemaGenerator
    paths = SchemaGenerator().get_schema(request=None, public=True)["paths"]
    wanted = ("/card-templates", "/card-templates/import", "/card-templates/{id}", "/card-templates/{id}/duplicate",
              "/card-templates/{id}/export", "/apply-template")
    for suffix in wanted:
        assert any(path.endswith(suffix) for path in paths), suffix
