"""Library capture/clone helpers for Studio (v3) certificates, and the locale that picks `translations`."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from apps.card_designs.layout import normalize_document
from apps.card_designs.rendering import RenderContext, draw_side
from apps.events.certificates.shared_render import locale_for
from apps.events.certificates.studio_assets import image_ids, remap

from .helpers import certificate, layer, signature, uid
from .recording import Recorder


def _pictured():
    a, b, c = uid(), uid(), uid()
    document = certificate([layer("image", 10, 10, 30, 30, asset_id=a), signature(1),
                            layer("signature_row", 20, 120, 200, 30, slots=[2, 3])],
                           watermark={"kind": "image", "asset_id": c, "opacity_pct": 10, "angle_deg": 0, "colour": "#006E63"})
    document["front"]["background"] = {"kind": "image", "asset_id": b, "fallback": "#FFFFFF"}
    return normalize_document(document, check_contrast=False), (a, b, c)


def test_every_v3_image_reference_is_found_and_remapped_and_signatory_slots_are_untouched():
    document, (a, b, c) = _pictured()
    assert image_ids(document) == {a, b, c}
    mapping = {a: uid(), b: uid(), c: uid()}
    copy = remap(deepcopy(document), mapping)
    assert image_ids(copy) == set(mapping.values())
    slots = lambda doc: [(row["kind"], row.get("signatory_slot"), row.get("slots")) for row in doc["front"]["layers"] if row["kind"].startswith("signature")]
    assert slots(copy) == slots(document)  # no approval or signatory id travels with a copy


def test_v2_documents_still_use_resource_ids():
    rid = uid()
    document = {"version": 2, "layers": [{"type": "image", "resource_id": rid}, {"type": "text"}]}
    assert image_ids(document) == {rid}
    new = uid()
    assert remap(document, {rid: new})["layers"][0]["resource_id"] == new


def _translated():
    row = layer("text", 20, 40, 150, 12, text="Certificate", translations={"ml": "Malayalam text"})
    return normalize_document(certificate([row]))


def _member(locale):
    return SimpleNamespace(preferred_locale=locale)


def _cert(member_locale="", space_locale="en"):
    return SimpleNamespace(recipient_member=_member(member_locale),
                           event=SimpleNamespace(makerspace=SimpleNamespace(default_locale=space_locale)))


@pytest.mark.parametrize("member,space,expected", [("ml", "en", "ml"), ("ml-IN", "en", "ml"), ("", "ml", "ml"),
                                                   ("hi", "en", ""), ("", "en", "")])
def test_locale_is_the_recipients_then_the_spaces_and_only_if_translated(member, space, expected):
    assert locale_for(_cert(member, space), _translated()) == expected


def test_a_translated_field_prints_in_the_locale_and_falls_back_to_the_base_text():
    document = _translated()
    for locale, text in (("ml", "Malayalam text"), ("", "Certificate")):
        recorder = Recorder()
        draw_side(recorder, document, "front", RenderContext(locale=locale))
        assert "".join(op[4] for op in recorder.ops if op[0] == "text") == text
