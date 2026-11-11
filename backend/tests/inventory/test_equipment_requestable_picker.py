import pytest
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

from apps.inventory.equipment_picker import product_page
from tests.return_helpers import make_product, make_space


@pytest.mark.django_db
def test_picker_only_projects_public_nonarchived_returnable_products():
    maker = make_space("equipment-picker")
    other = make_space("equipment-picker-other")
    visible = make_product(maker, name="Public", is_public=True)
    make_product(maker, name="Hidden", is_public=False)
    make_product(maker, name="Archived", is_public=True, is_archived=True)
    make_product(maker, name="Consumable", is_public=True, is_consumable=True)
    make_product(other, name="Other", is_public=True)
    request = Request(APIRequestFactory().get("/picker"))
    response = product_page(request, maker)
    assert [row["id"] for row in response.data["results"]] == [visible.pk]
    assert set(response.data["results"][0]) == {"id", "name", "image_url", "event_only"}  # 221b: the picker marks event-only gear
