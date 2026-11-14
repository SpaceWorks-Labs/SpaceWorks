"""Profile and tenant branding writers retain the same byte cap under contention."""
import pytest
from django.db import connection

from apps.makerspaces.models import Makerspace
from tests.makerspaces import test_public_upload_routes_cx7_p4a as writers

pytestmark = [pytest.mark.django_db, pytest.mark.area_member_accounts, pytest.mark.area_inventory]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", ["profile", "logo", "cover"])
@pytest.mark.parametrize("key,status,code", writers.KEYS[1:])
def test_profile_and_brand_writers_admit_one_last_object(kind, surface, key, status, code, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, pair, sizes, _ = writers.world(key, surface, settings, monkeypatch)
    owners = [writers.setup(space, pair[index], kind, index) for index in range(2)]
    sizes.update({object_key: 10 for _, _, _, object_key in owners})
    results = writers.race(pair, [("put", url, {"object_key": object_key}, 200)
                                 for _, _, url, object_key in owners])
    assert sorted(actual for actual, _ in results) == [200, status]
    assert [body["code"] for actual, body in results if actual == status] == [code]
    winner = next(i for i, (actual, _) in enumerate(results) if actual == 200)
    row, field, _, object_key = owners[winner]
    row.refresh_from_db()
    assert getattr(row, field) == object_key
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10
