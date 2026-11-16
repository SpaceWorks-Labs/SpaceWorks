"""Owner decision 220(c): designers get a real `Outfit` family; stored card designs move off the
legacy "Gilroy" token, and "Gilroy" still reads as Outfit everywhere a design is loaded."""
import importlib

import pytest
from django.apps import apps as global_apps

from apps.card_designs import fonts
from apps.card_designs.models import CardDesign, CardDesignRevision
from apps.events.certificates import fonts as certificate_fonts
from apps.events.certificates.layout import normalize_document as normalize_certificate
from apps.events.certificates.serializers_layout import CertificateLayerSerializer
from tests.l3_local.helpers import card_space

migration = importlib.import_module("apps.card_designs.migrations.0005_outfit_font_family")


def _layer(family, weight=700):
    return {"id": "8f5b8c2e-62a1-4b9e-9d64-0f3b1f0d2a11", "kind": "text", "text": "Hi", "font_family": family,
            "font_weight": weight}


def _document(*layers):
    return {"version": 2, "stock": "cr80-landscape", "front": {"layers": list(layers)}, "back": {"layers": []}}


@pytest.mark.django_db
def test_migration_moves_drafts_and_published_copies_and_reverses_only_the_legacy_weights():
    space = card_space("font220c")
    design = CardDesign.objects.create(
        makerspace=space, domain="member_cards", document=_document(_layer("Gilroy"), _layer("Outfit", 900)),
        published_document=_document(_layer("Gilroy", 400)), published_revision=1)
    other = CardDesign.objects.create(makerspace=card_space("font220d"), domain="member_cards",
                                      document=_document(_layer("Unbounded")))
    revision = CardDesignRevision.objects.create(design=design, revision=1, document=_document(_layer("Gilroy")))

    migration.forwards(global_apps, None)
    design.refresh_from_db()
    assert [row["font_family"] for row in design.document["front"]["layers"]] == ["Outfit", "Outfit"]
    assert design.published_document["front"]["layers"][0]["font_family"] == "Outfit"
    other.refresh_from_db()
    assert other.document["front"]["layers"][0]["font_family"] == "Unbounded"
    revision.refresh_from_db()
    assert revision.document["front"]["layers"][0]["font_family"] == "Gilroy"  # append-only history

    migration.backwards(global_apps, None)
    design.refresh_from_db()
    # Outfit 900 was a catalogue choice the old token never carried; it stays Outfit.
    assert [row["font_family"] for row in design.document["front"]["layers"]] == ["Gilroy", "Outfit"]
    assert design.published_document["front"]["layers"][0]["font_family"] == "Gilroy"


def test_legacy_token_reads_as_outfit_in_the_card_library():
    assert fonts.canonical("Gilroy") == "Outfit" and fonts.canonical("Lato") == "Lato"
    assert fonts.bundled_path("Gilroy", 700) == fonts.bundled_path("Outfit", 700)
    assert fonts.describe("Gilroy")["family"] == "Outfit"


def test_certificate_and_badge_designs_save_legacy_gilroy_as_outfit():
    document = {"version": 2, "page_width_mm": 297, "page_height_mm": 210, "layers": [
        {"id": "8f5b8c2e-62a1-4b9e-9d64-0f3b1f0d2a11", "order": 0, "type": "text", "x_mm": 10, "y_mm": 10,
         "width_mm": 100, "height_mm": 20, "text": "{{name}}", "font_family": "Gilroy", "font_weight": 700}]}
    assert normalize_certificate(document)["layers"][0]["font_family"] == "Outfit"
    document["layers"][0]["font_family"] = "Outfit"
    assert normalize_certificate(document)["layers"][0]["font_family"] == "Outfit"
    assert certificate_fonts.canonical("Gilroy") == "Outfit"
    field = CertificateLayerSerializer().fields["font_family"]
    assert field.to_internal_value("Gilroy") == "Outfit"
    assert set(field.choices) == {"Outfit", "Unbounded"}
