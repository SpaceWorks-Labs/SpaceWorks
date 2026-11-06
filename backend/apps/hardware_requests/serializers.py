from django.utils.translation import gettext
from rest_framework import serializers

from apps.hardware_requests.display import requester_label
from apps.inventory.models import TrackingMode


class RequestItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class RequestSubmitSerializer(serializers.Serializer):
    """A signed-in borrow request. Identity is always account-derived, so any stray
    contact fields an old client still sends are ignored as unknown keys."""

    website = serializers.CharField(required=False, allow_blank=True, write_only=True)
    requested_for = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=500,
    )
    items = serializers.ListField(
        child=RequestItemInputSerializer(),
        allow_empty=False,
        max_length=20,
    )
    # Lane L12 (loans.reservations / loans.waitlist).
    pickup_from = serializers.DateTimeField(required=False, allow_null=True, default=None)
    pickup_until = serializers.DateTimeField(required=False, allow_null=True, default=None)
    waitlist_entry_id = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=1)

    def validate(self, attrs):
        attrs["website"] = attrs.get("website", "")
        product_ids = [item["product_id"] for item in attrs["items"]]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                {"items": gettext("Duplicate product_id values are not allowed.")}
            )
        return attrs


class ContactRequestSubmitSerializer(RequestSubmitSerializer):
    """A borrow request with no account, for a space without member accounts (#80).

    All three contact fields are required; the email must carry the one-time code sent to
    it. The name is the borrower's public name; phone and email are staff-only and stored
    encrypted on the request.
    """

    contact_name = serializers.CharField(max_length=200, trim_whitespace=True)
    contact_email = serializers.EmailField(max_length=254)
    contact_phone = serializers.CharField(max_length=32, trim_whitespace=True)
    email_code = serializers.RegexField(r"^\d{6}$", write_only=True)

    def validate_contact_email(self, value):
        return value.strip().lower()


class PublicRequestSubmitSchemaSerializer(RequestSubmitSerializer):
    """OpenAPI shape only: the contact fields are required where `request_access` is
    `contact`, and ignored on the signed-in path."""

    contact_name = serializers.CharField(max_length=200, required=False)
    contact_email = serializers.EmailField(max_length=254, required=False)
    contact_phone = serializers.CharField(max_length=32, required=False)
    email_code = serializers.RegexField(r"^\d{6}$", required=False, write_only=True)


class ContactCodeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)


class RequestSubmitResponseSerializer(serializers.Serializer):
    public_token = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)


class PublicRequestItemStatusSerializer(serializers.Serializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    requested_quantity = serializers.IntegerField(read_only=True)


class PublicRequestStatusSerializer(serializers.Serializer):
    # Public + token-addressable: deliberately omits requester_username. The check-in
    # identity may be a name / email / badge / student id (PII), and the requester does
    # not need their own identity echoed back to learn a request's status.
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    items = PublicRequestItemStatusSerializer(many=True, read_only=True)


class IssuedAssetSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField(read_only=True, source="asset.id")
    asset_tag = serializers.CharField(read_only=True, source="asset.asset_tag")
    serial_number = serializers.CharField(read_only=True, source="asset.serial_number")


class AdminRequestItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    product_id = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    # Free-text shelf/storage location so staff know where to physically fetch (issue) or
    # return each item during handover. Same prefetched product row as product_name (no N+1).
    storage_location = serializers.CharField(
        source="product.storage_location", read_only=True, allow_blank=True
    )
    # Exposed so the staff issue UI knows which accepted units require a scanned asset QR.
    # individual-mode products must be issued with one AVAILABLE asset QR per accepted unit
    # (handover_issue_helpers.issue_individual_assets), so the modal must collect scans for them.
    tracking_mode = serializers.CharField(source="product.tracking_mode", read_only=True)
    requires_asset_qr = serializers.SerializerMethodField()
    requested_quantity = serializers.IntegerField(read_only=True)
    accepted_quantity = serializers.IntegerField(read_only=True)
    issued_quantity = serializers.IntegerField(read_only=True)
    returned_quantity = serializers.IntegerField(read_only=True)
    damaged_quantity = serializers.IntegerField(read_only=True)
    missing_quantity = serializers.IntegerField(read_only=True)
    needs_fix_quantity = serializers.IntegerField(read_only=True)
    issued_assets = serializers.SerializerMethodField()

    def get_requires_asset_qr(self, obj) -> bool:
        return obj.product.tracking_mode == TrackingMode.INDIVIDUAL

    def get_issued_assets(self, obj) -> list:
        if obj.product.tracking_mode != TrackingMode.INDIVIDUAL:
            return []
        links = obj.asset_links.select_related("asset").filter(outcome="issued").order_by("asset_id")
        return IssuedAssetSerializer(links, many=True).data


class AdminRequestActorSerializer(serializers.Serializer):
    username = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)


class AdminRequestSerializer(serializers.Serializer):
    has_kit_checklist = serializers.SerializerMethodField()

    def get_has_kit_checklist(self, obj) -> bool:
        return bool(obj.box_issue_checklist or any(item.issue_checklist for item in obj.items.all()))

    id = serializers.IntegerField(read_only=True)
    makerspace_id = serializers.IntegerField(read_only=True)
    requester_username = serializers.CharField(read_only=True)
    requester_name = serializers.CharField(read_only=True)
    # Readable staff-facing label (Check-In email/phone), never the internal
    # checkin_<hash>. Additive - requester_username stays for the existing contract.
    requester_display = serializers.SerializerMethodField()
    requester_contact_email = serializers.EmailField(read_only=True)
    requester_contact_phone = serializers.CharField(read_only=True)
    requester_contact_verified = serializers.BooleanField(read_only=True)
    status = serializers.CharField(read_only=True)
    requested_for = serializers.CharField(read_only=True)
    rejection_reason = serializers.CharField(read_only=True)
    assigned_box_label = serializers.CharField(
        source="assigned_box.label",
        read_only=True,
        allow_null=True,
    )
    accepted_by = AdminRequestActorSerializer(read_only=True, allow_null=True)
    issued_by = AdminRequestActorSerializer(read_only=True, allow_null=True)
    accepted_at = serializers.DateTimeField(read_only=True)
    issued_at = serializers.DateTimeField(read_only=True)
    return_due_at = serializers.DateTimeField(read_only=True)
    return_reminder_sent_at = serializers.DateTimeField(read_only=True)
    renewal_count = serializers.IntegerField(read_only=True)
    pickup_from = serializers.DateTimeField(read_only=True, allow_null=True)
    pickup_until = serializers.DateTimeField(read_only=True, allow_null=True)
    closed_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    # Evidence-photo ids so the staff console can fetch signed view URLs (GET /admin/evidence/<id>)
    # and SHOW the issue/return photos - without these ids React had no way to view captured
    # evidence (only the Django admin could). issue_evidence is a direct FK; return photos hang
    # off the immutable ReturnEvent rows for this request.
    issue_evidence_id = serializers.IntegerField(read_only=True, allow_null=True)
    return_evidence_ids = serializers.SerializerMethodField()
    items = AdminRequestItemSerializer(many=True, read_only=True)

    def get_return_evidence_ids(self, obj) -> list:
        return [event.evidence_id for event in obj.returnevent_set.all() if event.evidence_id]

    def get_requester_display(self, obj) -> str:
        return requester_label(obj)


from .serializers_handover import (
    AcceptQuantitySerializer,
    AcceptRequestSerializer,
    RejectRequestSerializer,
    AssignBoxSerializer,
    IssueRejectSerializer,
    IssueRequestSerializer,
    ReturnDueSerializer,
    ReturnAssetResolutionSerializer,
    ReturnItemResolutionSerializer,
    ReturnRequestSerializer,
)
