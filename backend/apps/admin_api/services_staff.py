"""Shared, transactional staff membership attachment helpers."""

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils.crypto import get_random_string
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole


def _is_superadmin_only_membership(membership):
    """Protect an existing Space Manager even when the membership is revoked.

    Inspect its complete stored action set rather than the legacy primary label;
    status-independent authority prevents reattachment from bypassing this guard.
    """
    from apps.accounts.rbac_roles import stored_actions_for_membership

    return rbac.Action.MANAGE_MAKERSPACE in stored_actions_for_membership(membership)


def _global_role_for_membership(legacy_role):
    # The GUEST_ADMIN branch is gone with the built-in role, and so is the enum member
    # itself (accounts `0009` rewrote the stored rows to `requester`, `0010` dropped the
    # choice). Removing it was safe because it gated nothing reachable: its only consumer
    # was `STAFF_ROLES`, read by `IsStaff`, whose sole `StaffAPIView` subclass overrides
    # `permission_classes`.
    if legacy_role == MakerspaceMembership.Role.SPACE_MANAGER:
        return User.Role.SPACE_MANAGER
    return User.Role.REQUESTER


def attach_staff_membership(
    *, actor, makerspace, username, email="", first_name="", last_name="", password="", role=None,
    roles=None,
):
    """Create or attach a user to a complete role set, rolling back on failure."""
    from apps.makerspaces.role_membership_writes import validated_roles

    roles = validated_roles(MakerspaceMembership(makerspace=makerspace),
                            roles if roles is not None else [role])
    role = roles[0]
    actor_is_superadmin = actor.is_superuser or actor.role == User.Role.SUPERADMIN
    is_break_glass = (
        actor_is_superadmin
        and not makerspace.superadmin_access_enabled
        and role.legacy_role == MakerspaceMembership.Role.SPACE_MANAGER
    )
    with transaction.atomic():
        makerspace = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        from apps.makerspaces.membership_admission_settings import ensure_join_allowed, settings_for
        policy = settings_for(makerspace)
        role = MakerspaceRole.objects.select_for_update().get(
            pk=role.pk, makerspace=makerspace
        )
        user_defaults = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "role": _global_role_for_membership(role.legacy_role),
            "password": make_password(password or get_random_string(32)),
        }
        if is_break_glass:
            ensure_join_allowed(makerspace)
            errors = {}
            if User.objects.filter(username=username).exists():
                errors["username"] = "A user with that username already exists."
            if email and User.objects.filter(email__iexact=email).exists():
                errors["email"] = "A user with that email already exists."
            if errors:
                raise ValidationError(errors)
            user = User.objects.create(username=username, **user_defaults)
            limits.check_quota(makerspace, "staff", adding=1)
            membership = MakerspaceMembership.objects.create(
                user=user,
                makerspace=makerspace,
            )
            created = True
        else:
            user, created = User.objects.get_or_create(
                username=username, defaults=user_defaults
            )
            if not actor_is_superadmin:
                # `of=("self",)` because `assigned_role` is nullable: select_related makes
                # it a LEFT OUTER JOIN, and Postgres refuses FOR UPDATE on the nullable
                # side of one. Same pattern as `role_services.assign_role`.
                existing = (
                    MakerspaceMembership.objects.select_for_update(of=("self",))
                    .select_related("assigned_role")
                    .filter(makerspace=makerspace, user=user)
                    .first()
                )
                if existing is not None and _is_superadmin_only_membership(existing):
                    raise PermissionDenied(
                        "Only a superadmin can change a Space Manager membership."
                    )
            from apps.makerspaces.platform import module_enabled
            has_active_membership = MakerspaceMembership.objects.filter(
                user=user, makerspace=makerspace, status="active",
                user__is_active=True, user__access_status=User.AccessStatus.ACTIVE,
            ).exists()
            if not has_active_membership:
                policy = ensure_join_allowed(makerspace)
            if (policy.configured and module_enabled(makerspace, "membership")
                    and not role.granted_actions and not has_active_membership):
                if not user.is_active or user.access_status != User.AccessStatus.ACTIVE:
                    raise ValidationError({"detail": "Community admission requires an unrestricted active account."})
                from apps.makerspaces.membership_activation import _activate_membership
                membership = _activate_membership(actor, makerspace, user, role, source="staff_create")
                return membership, created, is_break_glass
            if not has_active_membership and user.is_active and (
                user.access_status == User.AccessStatus.ACTIVE
            ):
                limits.check_quota(makerspace, "staff", adding=1)
            # Only NEW accounts take a global User.role from the membership (via
            # get_or_create defaults above). Never rewrite an EXISTING account's global
            # role here: doing so would let a manager add a known non-is_superuser global
            # superadmin as a delegable/custom role and silently strip their global
            # authority (P1). Authority is per-makerspace via the membership anyway.
            # Re-adding a previously revoked staff member must reactivate the row, not
            # leave status="revoked" (which the M2 RBAC paths treat as no access).
            membership, _ = MakerspaceMembership.objects.update_or_create(
                user=user,
                makerspace=makerspace,
                defaults={
                    "status": "active",
                    "revoked_at": None,
                    "revoked_by": None,
                    "revocation_reason": "",
                },
            )
        from apps.makerspaces.role_membership_writes import replace_membership_roles
        from apps.audit import services as audit
        changes = replace_membership_roles(
            membership=membership, roles=roles, actor=actor,
            reason="staff.roles_changed", fresh_lifecycle=True,
        )
        audit.record(actor, "staff.roles_changed", makerspace=makerspace, target=user,
                     meta={"membership_id": membership.pk,
                     "before": changes["before"], "after": changes["after"],
                     "removed_machine_type_ids": changes["removed_machine_type_ids"]})
        return membership, created, is_break_glass
