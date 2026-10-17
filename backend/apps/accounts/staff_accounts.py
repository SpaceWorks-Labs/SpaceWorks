"""Create a separate tenant staff principal and its complete authority atomically."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils.text import slugify
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.username_allocation import UsernameAllocationError, allocate_staff_username
from apps.audit import services as audit
from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.makerspaces.role_assignments import can_assign_roles
from apps.makerspaces.role_membership_writes import replace_membership_roles, validated_roles


@transaction.atomic
def create_staff_account(makerspace, *, name, email="", username=None, roles,
                         machine_type_ids=(), created_by):
    if not getattr(created_by, "is_authenticated", False) or not created_by.pk:
        raise PermissionDenied()
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        raise ValidationError({"name": "Provide a name of at most 200 characters."})
    if not isinstance(email, str) or len(email.strip()) > 254:
        raise ValidationError({"email": "Provide a valid email address."})
    email = email.strip().lower()
    try:
        if email:
            validate_email(email)
    except DjangoValidationError as exc:
        raise ValidationError({"email": exc.messages}) from exc
    if username is not None and (not isinstance(username, str) or not username.strip()
                                 or len(username) > 150):
        raise ValidationError({"username": "Provide a username handle of at most 150 characters."})
    makerspace = Makerspace.objects.select_for_update(no_key=True).get(pk=makerspace.pk)
    created_by = User.objects.select_for_update().filter(pk=created_by.pk).first()
    if (created_by is None or not created_by.is_active
            or created_by.access_status != User.AccessStatus.ACTIVE
            or created_by.is_tenant_dump_stub or created_by.retired_at is not None):
        raise PermissionDenied()
    if not rbac.can(created_by, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk):
        raise PermissionDenied()
    membership = MakerspaceMembership(makerspace=makerspace)
    if (not isinstance(roles, (list, tuple)) or not roles
            or any(not isinstance(role, MakerspaceRole) or not role.pk for role in roles)):
        raise ValidationError({"roles": "Choose saved built-in staff roles."})
    role_ids = {role.pk for role in roles}
    roles = list(MakerspaceRole.objects.filter(pk__in=role_ids, makerspace=makerspace))
    if len(roles) != len(role_ids):
        raise ValidationError({"roles": "Choose roles from this makerspace."})
    roles = validated_roles(membership, roles)
    if any(role.slug == "member" for role in roles):
        raise ValidationError({"roles": "Staff accounts require built-in staff roles."})
    can_assign_roles(created_by, makerspace, roles)
    if (not isinstance(machine_type_ids, (list, tuple))
            or any(type(value) is not int or value <= 0 for value in machine_type_ids)
            or len(set(machine_type_ids)) != len(machine_type_ids)):
        raise ValidationError({"machine_type_ids": "Use distinct positive integer ids."})
    if machine_type_ids and "machine_manager" not in {role.slug for role in roles}:
        raise ValidationError({"machine_type_ids": "Machine scopes require the Machine Manager role."})
    limits.check_quota(makerspace, "staff", adding=1)

    def insert(candidate):
        return User.objects.create_user(
            username=candidate, email=email, password=None, account_kind="staff",
            staff_makerspace=makerspace, display_name=name.strip(), must_change_password=True,
            role=User.Role.SPACE_MANAGER if roles[0].slug == "space_manager" else User.Role.REQUESTER,
        )

    try:
        user = allocate_staff_username(
            username or slugify(name) or email.partition("@")[0] or "staff",
            makerspace.slug, create=insert,
        )
    except DjangoValidationError as exc:
        raise ValidationError({"username": exc.messages}) from exc
    except UsernameAllocationError as exc:
        raise ValidationError({"username": "Could not allocate an available staff username."}) from exc
    except IntegrityError as exc:
        if getattr(getattr(exc.__cause__, "diag", None), "constraint_name", "") == "uniq_staff_space_email":
            raise ValidationError({"email": "A staff account in this makerspace already uses this email."}) from exc
        raise
    membership.user = user
    membership.assigned_role = roles[0]
    membership.role = roles[0].legacy_role or MakerspaceMembership.Role.CUSTOM
    membership.save()
    replace_membership_roles(membership=membership, roles=roles, actor=created_by,
                             reason="staff.account_created", fresh_lifecycle=True)
    if "machine_manager" in {role.slug for role in roles}:
        from apps.machines.member_scope_services import set_member_machine_scope

        set_member_machine_scope(makerspace=makerspace, membership=membership,
                                 actor=created_by, machine_type_ids=list(machine_type_ids))
    audit.record(created_by, "staff.account_created", makerspace=makerspace, target=user,
                 meta={"membership_id": membership.pk, "roles": [role.slug for role in roles],
                       "machine_type_ids": sorted(machine_type_ids)})
    return user
