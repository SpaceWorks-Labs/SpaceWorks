"""Inspect just the changed method contracts, without a per-test URL crawl."""
import importlib

import pytest
from rest_framework.test import APIRequestFactory

from apps.hardware_requests.exceptions import ErrorSerializer

pytestmark = [pytest.mark.area_api_contract, pytest.mark.area_inventory, pytest.mark.area_membership,
              pytest.mark.area_events, pytest.mark.area_machines]

VIEWS = [
    ("apps.admin_api.views_inventory_images", "InventoryProductImageView"),
    ("apps.admin_api.views_machine_image", "MachineImageView"),
    ("apps.admin_api.views_makerspace_images", "MakerspaceImageView"),
    ("apps.events.views_admin_image", "EventImageView"),
    ("apps.events.views_series_image", "EventSeriesImageView"),
    ("apps.makerspaces.member_card_views", "MemberCardPhotoView"),
    ("apps.card_designs.views_holder_photo", "MyCardPhotoView"),
    ("apps.card_designs.views_staff_photo", "MemberCardStaffPhotoView"),
    ("apps.card_designs.views_staff_photo", "ProgrammeCardStaffPhotoView"),
    ("apps.card_designs.views_staff_photo", "EventCardStaffPhotoView"),
    ("apps.shop.views_staff_images", "ShopProductImageView"),
    ("apps.payments.donations.views_sponsor_logo", "SponsorLogoView"),
    ("apps.makerspaces.profile_image_views", "AccountProfileImageView"),
]


@pytest.mark.parametrize("module,name", VIEWS)
@pytest.mark.parametrize("method", ["POST", "PUT"])
def test_changed_upload_contract_has_typed_headroom_reservation_and_class_refusals(module, name, method):
    view_class = getattr(importlib.import_module(module), name)
    # extend_schema stores the per-method schema on the handler; using the
    # unbound base schema would inspect none of that method's overrides.
    schema = getattr(view_class, method.lower()).kwargs["schema"]()
    view = view_class()
    view.args, view.kwargs = (), {}
    view.request = view.initialize_request(APIRequestFactory().generic(method, "/"))
    schema.view, schema.method = view, method
    responses = schema.get_response_serializers()
    assert responses[400].response is ErrorSerializer
    if not module.startswith("apps.events.") and not (
        module == "apps.makerspaces.profile_image_views" and method == "PUT"
    ):
        assert "upload_size_required" in responses[400].description
    assert "upload_limit" in responses[400].description
    assert "limit_reached" in responses[400].description
    assert responses[409].response is ErrorSerializer
    assert responses[409].description == "storage_public_images_bytes_quota_reached."
    if module in {"apps.makerspaces.profile_image_views", "apps.machines.views_type_setup"}:
        assert responses[503].response is ErrorSerializer


@pytest.mark.parametrize("module,name", [
    ("apps.admin_api.views_machine_documents", "MachineDocumentPresignView"),
    ("apps.admin_api.views_machine_documents", "MachineDocumentsView"),
    ("apps.procurement.views_receipts", "ToBuyReceiptPresignView"),
    ("apps.procurement.views_receipts", "ToBuyReceiptListCreateView"),
    ("apps.admin_api.views_machine_service_files", "MachineServiceFilePresignView"),
    ("apps.maintenance.views_documents", "MaintenanceLogDocumentPresignView"),
    ("apps.warranty.views_documents", "WarrantyDocumentPresignView"),
    ("apps.warranty.views_documents", "WarrantyDocumentCreateView"),
    ("apps.bookings.views_admin_space_detail", "BookableSpaceImagePresignView"),
    ("apps.bookings.views_gallery", "SpacePhotoPresignView"),
    ("apps.card_designs.views_assets", "CardAssetUploadView"),
    ("apps.card_designs.views_assets", "CardAssetFinalizeView"),
    ("apps.makerspaces.views_admission_changes", "MemberJoinPhotoView"),
    ("apps.machines.views_type_setup", "TypeDocumentPresignView"),
    ("apps.machines.views_type_setup", "TypeDocumentsView"),
    ("apps.id_programmes.views_public", "PublicProgrammeJoinPhotoView"),
    ("apps.machines.views_jobs", "PublicJobUploadView"),
    ("apps.machines.views_public_printer_service", "PublicPrinterUploadView"),
    ("apps.maintenance.repairs.views_staff", "IssuePhotoUploadView"),
    ("apps.maintenance.repairs.views_member", "MemberIssuePhotoUploadView"),
    ("apps.maintenance.repairs.views_public", "PublicIssuePhotoUploadView"),
])
def test_post_upload_contracts(module, name):
    test_changed_upload_contract_has_typed_headroom_reservation_and_class_refusals(module, name, "POST")
