from copy import deepcopy
from uuid import uuid4
from pathlib import Path
import json
import pytest
from rest_framework.exceptions import ValidationError
from apps.makerspaces.public_page_contract import empty_document, normalize_document
from apps.makerspaces.public_page_markdown import validate_markdown, rendering_policy, public_url


@pytest.mark.parametrize("text", ["Hello 世界", "**Bold**\n\n- one\n- two", "[Build](https://example.test/a_(b))",
                                      "literal *italic* and # heading", "[an incomplete link("])
def test_supported_markdown_and_harmless_literal_text(text):
    assert validate_markdown(text) == text


@pytest.mark.parametrize("text", ["<script>alert(1)</script>", "<iframe src='https://a.test'>", "![photo](https://a.test/a)",
    "[bad](javascript:alert(1))", "[bad](java%73cript:alert(1))", "[bad](https://user:password@a.test)",
    "[bad](https://a.test/%0afoo)", "[bad](data:text/html,a)", "[bad](http://a.test)", "bad\x00text"])
def test_new_markdown_rejects_active_or_obfuscated_content(text):
    with pytest.raises(ValidationError):
        validate_markdown(text)


def test_legacy_http_and_literal_policy_are_server_decisions():
    assert validate_markdown("[Old](http://example.test)", legacy_http=True)
    assert rendering_policy("<b>Old prose</b>") == "legacy_literal_v1"
    assert rendering_policy("**Old prose**") == "restricted_v1"
    assert validate_markdown("a\r\nb\rc") == "a\nb\nc"


@pytest.mark.parametrize("url", ["https://a.test:invalid", "https://a.test\\@b.test", "https://%75ser@a.test", "https://a.test/\u200b"])
def test_urls_fail_closed(url):
    with pytest.raises(ValidationError):
        public_url(url)


def test_required_groups_and_unknown_fields():
    doc = empty_document("makerspace")
    assert normalize_document(doc, kind="makerspace") == doc
    for change in (lambda d: d["sections"].clear(), lambda d: d.update(private_count=1),
                   lambda d: d["sections"][0].update(enabled=False),
                   lambda d: d["sections"][0].update(id=str(uuid4()))):
        altered = deepcopy(doc)
        change(altered)
        with pytest.raises(ValidationError):
            normalize_document(altered, kind="makerspace")


def test_owner_specific_payloads_and_unique_rows():
    doc = empty_document("event")
    doc["sections"] = [{"id": str(uuid4()), "type": "stats", "enabled": True,
                        "payload": {"title": "", "show_public_inventory_units": False,
                                    "show_published_event_count": False, "publish_public_member_count": True}}]
    with pytest.raises(ValidationError):
        normalize_document(doc, kind="event")
    doc["sections"] = [{"id": str(uuid4()), "type": "about", "enabled": True,
                        "payload": {"title": "", "markdown": "界" * 10001}}]
    with pytest.raises(ValidationError):
        normalize_document(doc, kind="event")


def test_builder_never_accepts_storage_keys_or_geofence_fields():
    doc = empty_document("organization")
    doc["cover_mode"], doc["cover_asset_id"] = "asset", 3
    doc["sections"].append({"id": str(uuid4()), "type": "gallery", "enabled": True,
                            "payload": {"title": "", "items": [{"asset_id": 3, "caption": "", "object_key": "private"}]}})
    with pytest.raises(ValidationError):
        normalize_document(doc, kind="organization")


def test_shared_markdown_corpus():
    corpus = json.loads((Path(__file__).parent / "fixtures" / "markdown-v1.json").read_text(encoding="utf-8"))
    for row in corpus:
        for legacy in (False, True):
            allowed = row["legacy_valid" if legacy else "builder_valid"]
            if allowed:
                validate_markdown(row["text"], legacy_http=legacy)
            else:
                with pytest.raises(ValidationError):
                    validate_markdown(row["text"], legacy_http=legacy)


def test_http_editor_examples_match_the_frozen_document_contract():
    fixtures = json.loads((Path(__file__).parent / "fixtures" / "http-v1.json").read_text(encoding="utf-8"))
    for kind in ("makerspace", "organization"):
        normalize_document(fixtures[kind + "_editor"]["document"], kind=kind)
