from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.http import Http404

from apps.events.programme_sections import providers


@pytest.mark.parametrize("options", [{"unknown": True}, {"ids": [1, 1]}, {"ids": [True]},
                                     {"limit": 101}, {"layout": "foreign-product"}, {"ids": ["1"]}, {"ids": [{}]}])
def test_section_documents_only_accept_stable_ids_and_bounded_presentation(options):
    with pytest.raises(ValueError):
        providers.validate_options(options)


def test_sections_are_inert_until_pages_installs_the_adapter(monkeypatch):
    monkeypatch.setattr(providers, "_pages", None)
    with pytest.raises(Http404):
        providers.project_public(event_id=42, section_id=1, request_context=object())


def test_expired_or_unreleased_page_never_uses_independent_gallery_gate(monkeypatch):
    adapter = Mock()
    adapter.require_released_section.side_effect = Http404
    monkeypatch.setattr(providers, "_pages", adapter)
    gate = Mock()
    monkeypatch.setattr(providers, "public_event", gate)
    with pytest.raises(Http404):
        providers.project_public(event_id=42, section_id=1, request_context=object())
    gate.assert_not_called()
