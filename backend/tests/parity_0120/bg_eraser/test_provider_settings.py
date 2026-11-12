"""D314c provider settings: platform (superadmin, encrypted, write-only), per-space override, resolution, test button."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.card_designs.image_adapter import provider
from apps.card_designs.models import MakerspaceImageAdapter, PlatformImageAdapter
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.l3_local.helpers import card_space, client, manager, member

pytestmark = pytest.mark.django_db
SECRET = "a-very-long-shared-secret-1234"


def _root():
    user = User.objects.create_user(username="eraser-root", password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)
    api = APIClient()
    force_recent_authenticate(api, user)
    return api


def test_platform_settings_are_superadmin_only_encrypted_and_write_only():
    sm = manager(card_space("ps-plat", features=("cards.photo_cutout",)))
    url = reverse("admin-platform-image-adapter")
    assert client(sm).get(url).status_code in (401, 403)
    api = _root()
    response = api.patch(url, {"provider_url": "http://bg-eraser:8080/", "secret": SECRET}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True and body["provider_url"] == "http://bg-eraser:8080" and "secret" not in body
    assert SECRET not in str(api.get(url).json())
    row = PlatformImageAdapter.objects.get(pk=1)
    assert row.secret.startswith("fernet:") and SECRET not in row.secret and row.get_secret() == SECRET
    audit = AuditLog.objects.get(action="image_adapter.saved")
    assert audit.meta["scope"] == "platform" and SECRET not in str(audit.meta)


def test_save_rotate_and_remove_are_each_audited():
    api = _root()
    url = reverse("admin-platform-image-adapter")
    api.patch(url, {"provider_url": "https://eraser.example.org", "secret": SECRET}, format="json")
    api.patch(url, {"secret": SECRET + "-rotated"}, format="json")
    api.patch(url, {"clear": True}, format="json")
    actions = list(AuditLog.objects.filter(action__startswith="image_adapter.").values_list("action", flat=True))
    assert actions.count("image_adapter.saved") == 1 and "image_adapter.rotated" in actions
    assert "image_adapter.removed" in actions and not PlatformImageAdapter.objects.get(pk=1).complete


def test_a_short_secret_or_missing_secret_is_refused():
    api = _root()
    url = reverse("admin-platform-image-adapter")
    assert api.patch(url, {"provider_url": "https://e.example.org", "secret": "short"}, format="json").status_code == 400
    assert api.patch(url, {"provider_url": "https://e.example.org"}, format="json").status_code == 400


def test_the_space_route_needs_the_switch_and_a_manager():
    space = card_space("ps-space", features=("cards.photo_cutout",))
    other = card_space("ps-other", features=("cards.photo_cutout",))
    sm = manager(space)
    url = reverse("admin-image-adapter", args=[space.pk])
    assert client(manager(other, "o")).get(url).status_code in (403, 404)
    assert client(member(space)[0]).get(url).status_code in (403, 404)
    assert client(sm).get(url).status_code == 200
    space.enabled_features = []
    space.save(update_fields=["enabled_features"])
    assert client(sm).get(url).status_code == 404


def test_a_space_provider_must_be_public_https():
    space = card_space("ps-url", features=("cards.photo_cutout",))
    url = reverse("admin-image-adapter", args=[space.pk])
    api = client(manager(space))
    for bad in ("http://eraser.example.org", "https://10.0.0.5", "https://localhost:9000"):
        assert api.patch(url, {"provider_url": bad, "secret": SECRET}, format="json").status_code == 400
    assert not MakerspaceImageAdapter.objects.filter(makerspace=space).exists()


def test_resolution_prefers_the_space_then_the_platform_unless_opted_out(monkeypatch):
    space = card_space("ps-resolve", features=("cards.photo_cutout",))
    assert provider.resolve(space) is None
    shared = PlatformImageAdapter()
    shared.provider_url = "https://platform.example.org"
    shared.set_secret(SECRET)
    shared.save()
    assert provider.resolve(space).scope == "platform"
    own = MakerspaceImageAdapter(makerspace=space, provider_url="https://own.example.org")
    own.set_secret(SECRET + "x")
    own.save()
    assert provider.resolve(space).url == "https://own.example.org" and provider.resolve(space).scope == "space"
    own.clear()
    own.use_platform_provider = False
    own.save()
    assert provider.resolve(space) is None  # the space opted out of the platform fallback


def test_test_connection_records_the_outcome_and_audits_it(monkeypatch):
    api = _root()
    url = reverse("admin-platform-image-adapter")
    api.patch(url, {"provider_url": "https://eraser.example.org", "secret": SECRET}, format="json")
    from apps.card_designs.image_adapter import client as adapter_client
    from apps.card_designs.image_adapter.errors import AdapterError
    test_url = reverse("admin-platform-image-adapter-test")
    monkeypatch.setattr(adapter_client, "test_connection", lambda config: {"ok": True})
    assert api.post(test_url).json()["ok"] is True
    monkeypatch.setattr(adapter_client, "test_connection",
                        lambda config: (_ for _ in ()).throw(AdapterError("invalid_signature")))
    result = api.post(test_url).json()
    assert result == {**result, "ok": False, "error": "invalid_signature"}
    row = PlatformImageAdapter.objects.get(pk=1)
    assert row.last_test_ok is False and row.last_test_error == "invalid_signature"
    outcomes = list(AuditLog.objects.filter(action="image_adapter.tested").order_by("pk").values_list("meta__outcome", flat=True))
    assert outcomes == ["ok", "invalid_signature"]
