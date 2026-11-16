"""PROFILE-FIX fixtures: reuse the PROFILE-2 helpers (spaces, accounts, authenticated clients)."""
import pytest

from tests.parity_0120.profile_2.conftest import client_for, make_person, make_space  # noqa: F401


@pytest.fixture(autouse=True)
def platform_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}


@pytest.fixture
def storage(monkeypatch):
    """Fake the public-image bucket: presign, finalize, sniff, size, delete."""
    from apps.inventory import public_image_storage as pis

    deleted, sizes = [], {}
    monkeypatch.setattr(pis, "presigned_upload", lambda key, ct: {"url": "https://s.test/u", "method": "PUT", "headers": {}})
    monkeypatch.setattr(pis, "finalize_upload", lambda key: pis.FinalizeResult("ok", 10))
    monkeypatch.setattr(pis, "sniff_is_valid_image", lambda key: True)
    monkeypatch.setattr(pis, "object_size", lambda key: sizes.get(key, 10))
    monkeypatch.setattr(pis, "delete_object", lambda key: deleted.append(key) or True)
    monkeypatch.setattr(pis, "release_public_image_on_commit", lambda space, key, storage=None: deleted.append(key))
    return deleted
