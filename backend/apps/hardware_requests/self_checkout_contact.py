"""Account-less self-checkout for a space without member accounts (owner decision #91).

There, accounts are staff-only, so EVERY self-checkout -- signed in or not -- names the
borrower by name, phone and an email confirmed with a one-time code (the same identity as
a borrow request, `contact_identity`). The evidence rules are unchanged: an issue or
return still needs an uploaded photo and a scanned QR, and a return still needs a remark.
Uploads belong to the space's inert principal, so each one carries a signed grant bound
to the borrower's address, and a return must come from the address the checkout used.
"""

from django.utils.translation import gettext
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.audit import services as audit
from apps.evidence.models import EvidencePhoto
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable, evidence_object_key, presigned_upload
from apps.hardware_requests.contact_identity import confirm_contact, evidence_grant, grant_matches
from apps.hardware_requests.contact_verification import email_key
from apps.hardware_requests.self_checkout_serializers import PublicToolEvidenceUrlResponseSerializer
from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester
from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.request_access import uses_contact_path


CONTACT_SWITCH = "inventory.contact_self_checkout"


def contact_mode(request, makerspace, *, taking=False):
    """True for a space without member accounts; otherwise a signed-in account is needed.

    Taking a tool account-less needs its own switch (#95); returning one never does, so a
    tool checked out before the switch went off can always come back.
    """
    if uses_contact_path(request, makerspace):
        if taking and not feature_enabled(makerspace, CONTACT_SWITCH):
            raise PermissionDenied(gettext("Self-checkout without an account is turned off for this makerspace."))
        return True
    if not request.user.is_authenticated:
        raise NotAuthenticated()
    return False


def confirmed_identity(makerspace, data):
    """Check the evidence grant against the typed address, then consume the email code."""
    key = email_key(makerspace, data["contact_email"])
    if not grant_matches(makerspace, data["evidence_grant"], data["evidence_id"], key):
        raise ValidationError({"evidence_grant": gettext("This photo was not uploaded for this email.")})
    return confirm_contact(makerspace, data)


def issue_upload(makerspace, data, *, uploader, actor, contact_email=None):
    """Create the evidence row and its presigned upload URL (both paths share this)."""
    if data["content_type"] not in settings.EVIDENCE_ALLOWED_MIME:
        raise ValidationError({"content_type": gettext("Unsupported evidence content type.")})
    object_key = evidence_object_key(makerspace.id, data["evidence_type"])
    try:
        upload = presigned_upload(object_key, data["content_type"])
    except StorageUnavailable:
        return storage_unavailable_response()
    photo = EvidencePhoto.objects.create(
        makerspace=makerspace,
        evidence_type=data["evidence_type"],
        object_key=object_key,
        content_type=data["content_type"],
        size_bytes=data.get("size_bytes"),
        uploaded_by=uploader,
        consumption_state=EvidencePhoto.ConsumptionState.UNCONSUMED,
    )
    audit.record(
        actor,
        "evidence.upload_url_issued",
        makerspace=makerspace,
        target=photo,
        meta={"surface": "public_self_checkout", "type": data["evidence_type"]},
    )
    response = {
        "evidence_id": photo.pk,
        "upload_url": upload["url"],
        "fields": upload.get("fields", {}),
        "object_key": object_key,
    }
    if upload.get("method"):
        response["method"] = upload["method"]
        response["headers"] = upload.get("headers", {})
    if contact_email is not None:
        response["evidence_grant"] = evidence_grant(makerspace, photo.pk, contact_email)
    return Response(PublicToolEvidenceUrlResponseSerializer(response).data, status=status.HTTP_201_CREATED)


def principal(makerspace):
    return get_or_create_anonymous_requester(makerspace)
