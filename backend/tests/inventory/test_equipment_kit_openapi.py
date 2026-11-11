from django.urls import path
from drf_spectacular.generators import SchemaGenerator

from apps.inventory.equipment_kit_views import KitTemplateListView


def test_kit_list_documents_page_and_archived_edit_requirement():
    schema = SchemaGenerator(patterns=[path(
        "api/v1/admin/makerspace/<int:makerspace_id>/equipment-kits",
        KitTemplateListView.as_view(), name="kit-schema-list",
    )]).get_schema(public=True)
    operation = schema["paths"]["/api/v1/admin/makerspace/{makerspace_id}/equipment-kits"]["get"]
    params = {item["name"]: item for item in operation["parameters"]}
    assert {"page", "include_archived"} <= set(params)
    assert "EDIT_INVENTORY" in params["include_archived"]["description"]
