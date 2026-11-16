"""Kit contents preview for an account-less borrower (owner decisions #91/#95/#104).

Where a space has no member accounts, a borrower checking a kit out (or returning one)
sees the same component preview a member does, after the email code. The code is checked
but NOT spent -- the checkout or return that follows consumes it -- and identity is the
confirmed-email key, so a return preview only finds a loan checked out under that address.
Taking a kit needs the #95 switch; previewing a return never does.
"""

from django.shortcuts import get_object_or_404
from rest_framework import serializers

from apps.boxes.access import inventory_qr_codes
from apps.boxes.models import QrCode
from apps.boxes.qr_lookup import scanned_or_404
from apps.hardware_requests.contact_verification import check_code, email_key
from apps.hardware_requests.kit_checklists import return_expectations
from apps.hardware_requests.kit_preview import preview_targets
from apps.hardware_requests.models import PublicToolLoan
from apps.hardware_requests.return_helpers import remaining_quantity


class ContactKitPreviewInputSerializer(serializers.Serializer):
    payload = serializers.CharField(max_length=64)
    phase = serializers.ChoiceField(choices=["issue", "return"])
    contact_email = serializers.EmailField(max_length=254)
    email_code = serializers.RegexField(r"^\d{6}$", write_only=True)


def contact_kit_rows(space, data):
    check_code(space, data["contact_email"], data["email_code"])
    if data["phase"] == "issue":
        return preview_targets(None, space, qr_payloads=[data["payload"]], public=True)
    qr = scanned_or_404(inventory_qr_codes(QrCode.objects.filter(makerspace=space, status=QrCode.Status.ACTIVE)),
                        data["payload"])
    loan = get_object_or_404(
        PublicToolLoan.objects.select_related("request"),
        qr_code=qr, makerspace=space, requester_id=space.anonymous_requester_id,
        source=PublicToolLoan.Source.PUBLIC_SELF_CHECKOUT, status=PublicToolLoan.Status.CHECKED_OUT,
        request__anonymous_payload_fingerprint=email_key(space, data["contact_email"]),
    )
    resolutions = [{"item": item, "returned": remaining_quantity(item), "damaged": 0, "missing": 0}
                   for item in loan.request.items.all() if remaining_quantity(item) > 0]
    return return_expectations(loan.request, resolutions)
