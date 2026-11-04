"""The consent ledger (X10): what a member agreed to, when, and under which notice.

Behind `membership.consent`. The Space Manager publishes the purposes and the privacy
notice version in the admission settings. A member gives consent per purpose (a new row
stamped with the current notice version) and may withdraw it at any time (the row gets
`withdrawn_at`); agreeing again opens a NEW row, so the ledger keeps every period. Rows
are never edited otherwise and never deleted outside a purge. No guardian or minor
fields exist (owner decision 3). Audited as `membership.consent_given|withdrawn`.
"""
import re

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models import MakerspaceMembership, MakerspaceMembershipSettings, MembershipConsent

_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_PURPOSES = 20


def validate_purposes(value):
    if not isinstance(value, list) or len(value) > MAX_PURPOSES:
        raise ValidationError({"consent_purposes": f"Use a list of at most {MAX_PURPOSES} purposes."})
    seen, cleaned = set(), []
    for item in value:
        if not isinstance(item, dict) or not _KEY.match(str(item.get("key", ""))) or item["key"] in seen:
            raise ValidationError({"consent_purposes": "Each purpose needs a unique lowercase key."})
        label = str(item.get("label", "")).strip()[:120]
        if not label:
            raise ValidationError({"consent_purposes": "Each purpose needs a label."})
        seen.add(item["key"])
        cleaned.append({"key": item["key"], "label": label, "description": str(item.get("description", "")).strip()[:500]})
    return cleaned


def published(makerspace):
    """`(purposes, notice_version)` as the space publishes them now."""
    row = MakerspaceMembershipSettings.objects.filter(makerspace=makerspace).first()
    if row is None:
        return [], ""
    return list(row.consent_purposes or []), row.privacy_notice_version or ""


def ledger(membership):
    return MembershipConsent.objects.filter(membership=membership).order_by("purpose", "-given_at", "-pk")


def _lock(membership):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(membership.makerspace_id)
    space = require_membership_feature_locked(membership.makerspace_id, "consent")
    return space, MakerspaceMembership.objects.select_for_update().get(pk=membership.pk)


def give(member, membership, purpose, *, source=MembershipConsent.Source.MEMBER):
    with transaction.atomic():
        space, membership = _lock(membership)
        if membership.user_id != member.pk or membership.status != "active":
            raise NotFound("Membership not found.")
        purposes, version = published(space)
        if purpose not in {item["key"] for item in purposes}:
            raise ValidationError({"purpose": "This space does not ask for that consent."})
        row = MembershipConsent.objects.filter(membership=membership, purpose=purpose, withdrawn_at__isnull=True).first()
        if row is not None:
            return row
        row = MembershipConsent.objects.create(makerspace=space, membership=membership, purpose=purpose,
                                               notice_version=version, source=source, given_at=timezone.now())
        audit.record(member, "membership.consent_given", makerspace=space, target=membership,
                     meta={"membership_id": membership.pk, "consent_id": row.pk, "purpose": purpose,
                           "notice_version": version})
    return row


def withdraw(member, membership, purpose):
    with transaction.atomic():
        space, membership = _lock(membership)
        if membership.user_id != member.pk:
            raise NotFound("Membership not found.")
        row = MembershipConsent.objects.select_for_update().filter(
            membership=membership, purpose=purpose, withdrawn_at__isnull=True).first()
        if row is None:
            raise NotFound("No consent to withdraw.")
        row.withdrawn_at = timezone.now()
        row.save(update_fields=["withdrawn_at"])
        audit.record(member, "membership.consent_withdrawn", makerspace=space, target=membership,
                     meta={"membership_id": membership.pk, "consent_id": row.pk, "purpose": purpose})
    return row
