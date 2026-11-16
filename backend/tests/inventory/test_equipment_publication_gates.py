from types import SimpleNamespace

import pytest
from django.http import Http404

from apps.events import views_equipment_picker as event_views
from apps.inventory import equipment_public_kit_views as member_views


@pytest.mark.parametrize(("site", "catalogue"), [(False, True), (True, False)])
def test_member_kits_refuse_private_publication(monkeypatch, site, catalogue):
    maker = SimpleNamespace(public_site_enabled=site, public_inventory_enabled=catalogue)
    monkeypatch.setattr(member_views, "get_public_makerspace", lambda _: maker)
    with pytest.raises(Http404):
        member_views._maker(SimpleNamespace(user=object()), "space")


def test_member_kits_require_public_inventory_module(monkeypatch):
    maker = SimpleNamespace(public_site_enabled=True, public_inventory_enabled=True)
    monkeypatch.setattr(member_views, "get_public_makerspace", lambda _: maker)
    monkeypatch.setattr(member_views, "require_module_for_servable",
                        lambda *_: (_ for _ in ()).throw(Http404()))
    with pytest.raises(Http404):
        member_views._maker(SimpleNamespace(user=object()), "space")


def test_domain_staff_picker_does_not_require_public_site(monkeypatch):
    maker = SimpleNamespace(public_site_enabled=False, public_inventory_enabled=False)
    event = SimpleNamespace(makerspace=maker, status="scheduled")
    monkeypatch.setattr(event_views, "get_object_or_404", lambda *_args, **_kwargs: event)
    monkeypatch.setattr(event_views.event_authority, "can", lambda *_: True)
    monkeypatch.setattr(event_views, "require_module", lambda *_: None)
    monkeypatch.setattr(event_views, "kit_page", lambda _request, selected: selected)
    assert event_views.EventEquipmentKitsView().get(SimpleNamespace(user=object()), 1, 2) is maker
