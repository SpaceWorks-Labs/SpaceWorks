"""Saved-template group rows survive a save (name, lock, hide), and the certificate looks keep the keys the studio reads."""
import pytest
from django.urls import reverse

from apps.card_designs import resolution
from apps.card_designs.models import CardDesign
from tests.l3_local.helpers import card_space, client, manager

from .conftest import document, layer, uid

pytestmark = pytest.mark.django_db

CERT_KEYS = {"cert_laurel", "cert_ribbon", "cert_spotlight"}


def test_a_saved_template_keeps_the_group_rows_with_name_lock_and_hide():
    space = card_space("tpl-groups")
    owner = manager(space)
    api = client(owner)
    group = uid()
    layers = [layer("shape", 0, 0, 20, 10, fill="#006E63", group=group), layer("shape", 0, 12, 20, 10, fill="#006E63", group=group)]
    doc = document(layers)
    doc["front"]["groups"] = [{"id": group, "name": "Header", "locked": True, "hidden": True}]
    design, _created = resolution.get_or_create(space, "member_cards", actor=owner)
    CardDesign.objects.filter(pk=design.pk).update(document=doc)
    created = api.post(reverse("admin-card-templates", kwargs={"makerspace_id": space.pk}),
                       {"design_id": design.pk, "name": "Grouped"}, format="json")
    assert created.status_code == 201, created.content
    stored = api.get(reverse("admin-card-template", kwargs={"pk": created.json()["id"]})).json()["document"]["front"]
    assert stored["groups"] == [{"id": group, "name": "Header", "locked": True, "hidden": True}]
    assert {row["group"] for row in stored["layers"]} == {group}


def test_the_certificate_gallery_rows_use_the_keys_the_studio_reads():
    space = card_space("tpl-cert-keys")
    api = client(manager(space))
    rows = api.get(reverse("admin-card-templates", kwargs={"makerspace_id": space.pk}), {"kind": "certificate"}).json()
    builtin = [row for row in rows if row["source"] == "builtin"]
    assert {row["key"] for row in builtin} == CERT_KEYS and {row["kind"] for row in builtin} == {"certificate"}
    assert {row["theme"] for row in builtin} == {"light", "dark"} and all(row["name"] for row in builtin)
    for key in CERT_KEYS:
        detail = api.get(reverse("admin-card-template-builtin", kwargs={"makerspace_id": space.pk, "key": key, "theme": "light"}))
        assert detail.status_code == 200 and detail.json()["document"]["kind"] == "certificate"
