"""MOD-1: public_inventory conditions (boundaries, input, leaks, ordering) on top of the existing cases.

The public list is the one anonymous surface of the product. These pin: the page-24 boundary and
last-page behaviour, hostile and non-English search text, hidden counts staying hidden in the whole
serialised body (not only in the named fields), and an item hidden/archived after the fact vanishing.
"""
import json

import pytest

from apps.boxes.models import QrCode
from apps.inventory.models import InventoryProduct, PublicAvailabilityMode
from tests.public_inventory_helpers import (  # noqa: F401  (fixtures)
    api_client,
    create_product,
    public_inventory_categories_url,
    public_inventory_url,
    public_makerspace,
)

pytestmark = pytest.mark.django_db


def _names(response):
    return [row["name"] for row in response.data["results"]]


@pytest.mark.parametrize("total,first,second", [(24, 24, None), (25, 24, 1), (48, 24, 24)])
def test_public_list_page_size_boundary_is_24(api_client, public_makerspace, total, first, second):
    for index in range(total):
        create_product(public_makerspace, name=f"Item {index:03d}")
    page_one = api_client.get(public_inventory_url(public_makerspace))
    assert page_one.status_code == 200
    assert page_one.data["count"] == total
    assert len(page_one.data["results"]) == first
    assert (page_one.data["next"] is not None) == (second is not None)
    if second is not None:
        page_two = api_client.get(public_inventory_url(public_makerspace), {"page": 2})
        assert len(page_two.data["results"]) == second
        assert page_two.data["next"] is None
        assert not set(_names(page_one)) & set(_names(page_two))  # no overlap between pages


def test_public_list_page_past_the_end_is_a_404_not_a_500(api_client, public_makerspace):
    create_product(public_makerspace, name="Only one")
    assert api_client.get(public_inventory_url(public_makerspace), {"page": 2}).status_code == 404
    assert api_client.get(public_inventory_url(public_makerspace), {"page": "abc"}).status_code == 404


def test_empty_public_list_is_a_well_formed_empty_page(api_client, public_makerspace):
    response = api_client.get(public_inventory_url(public_makerspace))
    assert response.status_code == 200
    assert response.data["count"] == 0 and response.data["results"] == []


@pytest.mark.parametrize("query", ["%", "_", "'; DROP TABLE inventory_inventoryproduct; --", "a" * 5000, "<script>"])
def test_hostile_search_text_never_errors_and_matches_nothing_it_should_not(api_client, public_makerspace, query):
    create_product(public_makerspace, name="Soldering Iron")
    response = api_client.get(public_inventory_url(public_makerspace), {"q": query})
    assert response.status_code == 200
    assert "Soldering Iron" not in _names(response)
    assert InventoryProduct.objects.filter(name="Soldering Iron").exists()


@pytest.mark.parametrize("name", ["مثقاب كهربائي", "ドリルプレス 🔧", "Zażółć gęślą jaźń", "<b>bold</b> & \"quoted\""])
def test_unicode_rtl_emoji_and_markup_names_round_trip_verbatim(api_client, public_makerspace, name):
    create_product(public_makerspace, name=name, description=name)
    listed = api_client.get(public_inventory_url(public_makerspace))
    assert _names(listed) == [name]  # returned as data, never altered or dropped
    found = api_client.get(public_inventory_url(public_makerspace), {"q": name.split()[0]})
    assert name in _names(found)


def test_hidden_mode_leaks_no_count_anywhere_in_the_serialised_body(api_client, public_makerspace):
    create_product(
        public_makerspace, name="Secret stock", total_quantity=7351, available_quantity=7349,
        reserved_quantity=1, issued_quantity=1, storage_location="Vault-Q9-Shelf",
        public_availability_mode=PublicAvailabilityMode.HIDDEN, show_public_count=True,
    )
    body = api_client.get(public_inventory_url(public_makerspace)).content.decode()
    assert "Secret stock" in body
    for forbidden in ("7351", "7349", "Vault-Q9-Shelf"):
        assert forbidden not in body
    assert json.loads(body)["results"][0]["availability"] is None


def test_qr_codes_and_box_ids_never_appear_in_list_detail_or_categories(api_client, public_makerspace):
    product = create_product(public_makerspace, name="Tracked saw")
    qr = QrCode.objects.create(
        makerspace=public_makerspace, target_type=QrCode.TargetType.PRODUCT, target_id=product.id,
        payload="SW-LEAK-CANARY-0042")
    urls = [
        public_inventory_url(public_makerspace),
        f"{public_inventory_url(public_makerspace)}{product.id}/",
        public_inventory_categories_url(public_makerspace),
    ]
    for url in urls:
        text = api_client.get(url).content.decode()
        assert qr.payload not in text, url
        assert "qr_code" not in text.lower() and "box" not in text.lower(), url


def test_item_made_private_or_archived_after_listing_disappears_from_list_and_detail(api_client, public_makerspace):
    product = create_product(public_makerspace, name="Fleeting")
    detail = f"{public_inventory_url(public_makerspace)}{product.id}/"
    assert api_client.get(detail).status_code == 200
    InventoryProduct.objects.filter(pk=product.pk).update(is_public=False)
    assert api_client.get(detail).status_code == 404
    assert "Fleeting" not in _names(api_client.get(public_inventory_url(public_makerspace)))
    InventoryProduct.objects.filter(pk=product.pk).update(is_public=True, is_archived=True)
    assert api_client.get(detail).status_code == 404
    InventoryProduct.objects.filter(pk=product.pk).update(is_archived=False)
    assert api_client.get(detail).status_code == 200  # restored with the same id


def test_public_list_is_read_only_for_anonymous_callers(api_client, public_makerspace):
    url = public_inventory_url(public_makerspace)
    for method in ("post", "put", "patch", "delete"):
        assert getattr(api_client, method)(url, {"name": "x"}, format="json").status_code == 405
    assert not InventoryProduct.objects.filter(name="x").exists()


def test_a_nul_byte_in_the_search_text_is_dropped_not_a_500(api_client, public_makerspace):
    # PostgreSQL cannot hold a NUL in a string literal; this used to raise ValueError -> 500.
    create_product(public_makerspace, name="Soldering Iron")
    response = api_client.get(public_inventory_url(public_makerspace), {"q": chr(0)})
    assert response.status_code == 200
    assert _names(response) == ["Soldering Iron"]  # a blank query after cleaning is the unfiltered list
    response = api_client.get(public_inventory_url(public_makerspace), {"q": "sol" + chr(0) + "der"})
    assert response.status_code == 200 and _names(response) == ["Soldering Iron"]
