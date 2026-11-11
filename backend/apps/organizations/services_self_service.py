"""Bounded organization creation; global governance never grants tenant authority."""
from django.utils.translation import gettext
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError as ModelValidationError
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.organizations import governance
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.services_console import OrganizationConflict


def creation_policy(actor):
    enabled = bool(getattr(settings, "ORGANIZATION_SELF_CREATION_ENABLED", False))
    verified = bool(actor.email and actor.email_verified_at and not actor.is_tenant_dump_stub)
    from apps.accounts.native_session import is_native_session
    # A generated first-run credential must be rotated first (as active_user enforced
    # before the account-kind split); member_account alone does not check it.
    eligible = (governance.member_account(actor) and not actor.must_change_password
                and verified and not is_native_session(actor))
    return {
        "enabled": enabled,
        "eligible": enabled and eligible,
        "max_owned": getattr(settings, "ORGANIZATION_SELF_CREATION_MAX_OWNED", 3),
        "max_per_day": getattr(settings, "ORGANIZATION_SELF_CREATION_MAX_PER_DAY", 1),
        "reason": (
            gettext("Organization self-creation is disabled by the operator.") if not enabled
            else gettext("A verified member browser account is required.")
            if not eligible else ""
        ),
    }


@transaction.atomic
def create_self_service(actor, *, name, slug, description="", website=""):
    # One account lock serializes simultaneous attempts, including across workers.
    locked_actor = User.objects.select_for_update().get(pk=actor.pk)
    policy = creation_policy(locked_actor)
    if not policy["eligible"]:
        raise PermissionDenied(policy["reason"])
    if Organization.objects.filter(created_by=locked_actor).count() >= policy["max_owned"]:
        raise OrganizationConflict("Your organization ownership limit has been reached.")
    recent = AuditLog.objects.filter(
        actor=locked_actor, action="organization.self_created",
        created_at__gte=timezone.now() - timedelta(days=1),
    ).count()
    if recent >= policy["max_per_day"]:
        raise OrganizationConflict("Your daily organization creation limit has been reached.")
    if not isinstance(name, str) or not isinstance(slug, str):
        raise ValidationError(gettext("A name and slug must be strings."))
    if not isinstance(description, str) or len(description) > 10000:
        raise ValidationError({"description": gettext("Use at most 10,000 characters.")})
    name, slug = name.strip(), slug.strip()
    if not name or not slug:
        raise ValidationError(gettext("A name and slug are required."))
    from apps.organizations import services_review
    services_review.assert_slug_available(slug)
    try:
        with transaction.atomic():
            row = Organization(
                name=name, slug=slug, description=description, website=website,
                created_by=locked_actor, public_profile_enabled=False,
            )
            try:
                row.full_clean(validate_unique=False)
            except ModelValidationError as exc:
                raise ValidationError(exc.message_dict) from exc
            row.save(force_insert=True)
            membership = OrganizationMembership.objects.create(
                organization=row, user=locked_actor, created_by=locked_actor,
                governance_actions=sorted(governance.GOVERNANCE_ACTIONS),
                granted_actions=[],
            )
    except IntegrityError as exc:
        raise OrganizationConflict("An organization with this slug already exists.") from exc
    audit.record(locked_actor, "organization.self_created", target=row)
    if services_review.review_required():
        services_review.submit_new(row, locked_actor)
    audit.record(locked_actor, "organization.membership_created", target=membership)
    row.actor_memberships = [membership]
    return row
