"""What a staff card says about its holder: every held role (translated) and the machine scope (O-B4 part 2).

Read live from the staff membership, so the card never drifts from the person's real authority. Names of
built-in roles are translated; a custom role shows the name the space gave it. Machine Manager and
Technician also show the machine types and machines they reach (decision 282).
"""
from django.utils.translation import gettext

from apps.accounts.rbac_roles import membership_roles
from apps.makerspaces.models import MakerspaceMembership

MACHINE_ROLES = {"machine_manager", "technician"}
MAX_NAMES = 4


def role_name(role):
    if role.legacy_role:
        label = dict(MakerspaceMembership.Role.choices).get(role.legacy_role)
        if label:
            return gettext(label)
    return role.name


def held_roles(membership):
    return membership_roles(membership) if membership is not None else []


def role_slugs(membership):
    return [role.slug for role in held_roles(membership)]


def roles_text(membership):
    return ", ".join(role_name(role) for role in held_roles(membership))


def machine_scope_text(membership):
    """"" unless the person holds a machine role; otherwise "Laser cutters, Printer 2 and 3 more"."""
    if membership is None or not MACHINE_ROLES & set(role_slugs(membership)):
        return ""
    from apps.machines.models_membership_scope import MembershipMachineScope, MembershipMachineTypeScope
    names = list(MembershipMachineTypeScope.objects.filter(membership=membership).values_list(
        "machine_type__name", flat=True))
    names += list(MembershipMachineScope.objects.filter(membership=membership).values_list("machine__name", flat=True))
    if not names:
        return ""  # nothing assigned yet: print nothing rather than a claim the person does not hold
    shown = ", ".join(names[:MAX_NAMES])
    extra = len(names) - MAX_NAMES
    return shown if extra <= 0 else gettext("%(names)s and %(count)d more") % {"names": shown, "count": extra}
