"""Public pagination uses 24 rows and never pulls products from another tenant."""
import pytest

from .helpers import client, product, shop_manager, shop_space

pytestmark = pytest.mark.django_db


def test_public_products_have_24_rows_then_the_last_row_with_exact_page_errors():
    space = shop_space("cx7-pages", "shop.online")
    seller = shop_manager(space)
    expected = []
    for index in range(25):
        row, _ = product(space, seller, name=f"Part {index:02d}", stock=0)
        expected.append(row.pk)
    other = shop_space("cx7-pages-other", "shop.online")
    hidden, _ = product(other, shop_manager(other), name="Foreign part", stock=0)
    url = f"/api/v1/public/m/{space.slug}/shop/products/"
    first = client().get(url)
    assert first.status_code == 200
    assert first.json()["count"] == 25
    assert [row["id"] for row in first.json()["results"]] == expected[:24]
    assert first.json()["previous"] is None
    assert first.json()["next"] == f"http://testserver{url}?page=2"
    last = client().get(first.json()["next"])
    assert last.status_code == 200
    assert [row["id"] for row in last.json()["results"]] == expected[24:]
    assert last.json()["count"] == 25
    assert last.json()["next"] is None
    assert last.json()["previous"] == f"http://testserver{url}"
    assert hidden.pk not in expected
    invalid = client().get(url, {"page": 3})
    assert invalid.status_code == 404
    assert invalid.json()["code"] == "not_found"
