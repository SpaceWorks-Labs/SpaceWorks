"""Every serializer over a PII-bearing model is reviewed for superadmin masking (#111 Q12).

A ModelSerializer whose model carries scoped-registry PII (or is an account) must either
use ``PiiMaskingSerializerMixin`` or be listed below with why it needs none (a member's
own data, a workflow input, or a surface a platform account cannot reach) or which wave-2
lane adopts it. A new serializer fails here until someone decides, because a
``SerializerMethodField`` or a nested field can carry PII the mixin's field list misses.
"""

import importlib
import inspect
import pkgutil

from django.apps import apps
from rest_framework import serializers

import apps as apps_package
from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.encryption.registry import registered_labels

# Each entry names the reviewed disposition.
_STAFF = 'tenant staff console only: surface_policy refuses platform accounts (not in PLATFORM_ROUTES); adopt the mixin if a route joins PLATFORM_ROUTES'
_OWN = "the account holder's own data on a personal/member route; never a superadmin view"
REVIEWED = {
    'apps.accounts.serializers_self_service.AccountProfileSerializer': _OWN,
    'apps.admin_api.serializers_machine_service.MachineServiceRequestSerializer': _STAFF,
    'apps.admin_api.serializers_machine_service_printer.TypedManualUsageResponseSerializer': _STAFF,
    'apps.admin_api.serializers_member_memberships.MembershipRequestSerializer': _STAFF,
    'apps.admin_api.serializers_membership_plans.InvitationRequestSerializer': _STAFF,
    'apps.admin_api.views_email_logs.EmailLogSerializer': _STAFF,
    'apps.bookings.serializers_broadcasts.BookingBroadcastSerializer': _STAFF,
    'apps.bookings.serializers_member.MemberBookingSerializer': _OWN,
    'apps.bookings.serializers_reservation.BookingAdminSerializer': _STAFF,
    'apps.devices.serializers_printers.JobSerializer': _STAFF,
    'apps.events.serializers_broadcasts.EventBroadcastSerializer': _STAFF,
    'apps.events.serializers_feedback.CertificateSummarySerializer': _STAFF,
    'apps.events.serializers_registration_admin.EventRegistrationAdminSerializer': _STAFF,
    'apps.integrations.notification_api_serializers.EndpointSerializer': _OWN,
    'apps.machines.serializers_machines.MachineUsageEntrySerializer': _STAFF,
    'apps.makerspaces.member_card_serializers.MemberCardSerializer': _STAFF,
    'apps.makerspaces.member_card_own_serializer.OwnMemberCardSerializer': _OWN,
    'apps.makerspaces.serializers_admission.AdmissionRequestSerializer': _STAFF,
    'apps.makerspaces.serializers_admission.AdmissionVouchOutcomeSerializer': _STAFF,
    'apps.notifications.serializers_broadcasts.BroadcastSerializer': _STAFF,
    'apps.notifications.serializers_inbox.InboxSerializer': _OWN,
    # L16: a reporter's own reports (no reporter name, email or contractor detail in it).
    'apps.maintenance.repairs.serializers_issues.MemberIssueReportSerializer': _OWN,
    'apps.devices.serializers_adapter_logs.BindingJobSerializer': _STAFF,
    'apps.maintenance.incidents.serializers.IncidentSerializer': _STAFF,
    'apps.maintenance.incidents.serializers.MemberIncidentSerializer': _OWN,
    'apps.maintenance.repairs.serializers_loan_handoff.LoanRepairIssueSerializer': _STAFF,
    # Reviewed 2026-11-06 (AG2) for 650a647e (#190): the superadmin account lookup returns id, username,
    # kind, status, MFA flag and a role count -- no ACCOUNT_PII_FIELDS and no registry field; the lookup
    # key (exact username) is all it echoes, so masking has nothing to cover.
    'apps.accounts.views_platform_accounts.PlatformAccountSerializer':
        'platform route with no masked field: no email, phone, name or registry PII is serialized',
    # Reviewed 2026-11-06 (AG2) for R2 L4: the member's own erasure requests on the member route
    # (MemberErasureRequestView, scoped by `mine`); member_note is their own words.
    'apps.makerspaces.serializers_membership_l4.ErasureRequestSerializer': _OWN,
}


def _serializer_classes():
    for module_info in pkgutil.walk_packages(apps_package.__path__, "apps."):
        name = module_info.name
        if ".migrations" in name or ".tests" in name or ".management" in name:
            continue
        try:
            module = importlib.import_module(name)
        except Exception:
            continue
        for _, value in inspect.getmembers(module, inspect.isclass):
            if value.__module__ == name and issubclass(value, serializers.ModelSerializer):
                yield value


def _pii_model_serializers():
    labels = set(registered_labels()) | {"accounts.User"}
    found = {}
    for cls in _serializer_classes():
        model = getattr(getattr(cls, "Meta", None), "model", None)
        if model is None or model._meta.label not in labels or issubclass(cls, PiiMaskingSerializerMixin):
            continue
        found[f"{cls.__module__}.{cls.__qualname__}"] = model._meta.label
    return found


def test_every_pii_model_serializer_is_reviewed():
    assert apps.ready
    found = _pii_model_serializers()
    missing = sorted(set(found) - set(REVIEWED))
    stale = sorted(set(REVIEWED) - set(found))
    if missing or stale:
        import pytest
        pytest.fail(chr(10).join(["UNREVIEWED:", *(f"{name} ({found[name]})" for name in missing), "STALE:", *stale]))
