"""Decision 236: own space vs hosted space -- the one question every limit, trial and invoice asks first.

* ``own``: the operator's own space. No plan, no limits, no trials, no hosting billing.
* ``hosted``: a space hosted for someone else. Plans, per-space limits, trials and billing apply.

With hosting off (``hosts_other_spaces()`` false) every space is treated as ``own``, whatever is
stored, and nothing is deleted. A space with no row is ``own`` (spaces the superadmin creates);
an approved host-your-makerspace request records ``hosted``.
"""

from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .models_hosting_type import SpaceHostingType

OWN, HOSTED = SpaceHostingType.Kind.OWN.value, SpaceHostingType.Kind.HOSTED.value
# What a space with no row is. Production: own (#236). The test suite's conftest flips it so
# legacy limit tests keep exercising enforcement; tests of the real default opt back out.
ABSENT_TYPE = OWN


def _space_id(makerspace):
    return getattr(makerspace, "pk", makerspace)


def stored_type(makerspace) -> str:
    value = (SpaceHostingType.objects.filter(makerspace_id=_space_id(makerspace))
             .values_list("hosting_type", flat=True).first())
    return value or ABSENT_TYPE


def hosted_q(prefix="makerspace__"):
    """A queryset filter for hosted spaces (the type only; callers check ``hosting_active`` first)."""
    from django.db.models import Q

    q = Q(**{f"{prefix}hosting_type_row__hosting_type": HOSTED})
    return q | Q(**{f"{prefix}hosting_type_row__isnull": True}) if ABSENT_TYPE == HOSTED else q


def hosting_active() -> bool:
    """Hosting other makerspaces is on (#234): the console switch, or a platform domain, which only a
    hosting install has (``hosts_other_spaces``). Off: every space behaves as own (#236)."""
    from apps.makerspaces.domain_verification import hosts_other_spaces

    return hosts_other_spaces()


def is_hosted(makerspace) -> bool:
    """True only for a stored ``hosted`` space while hosting is on. Never raises (off is the safe answer)."""
    try:
        return hosting_active() and stored_type(makerspace) == HOSTED
    except Exception:  # noqa: BLE001 - a DB-less caller (checks, imports) means "own": no limits
        return False


def require_hosted(makerspace):
    """Trials and hosting billing exist only for hosted spaces."""
    if not is_hosted(makerspace):
        raise ValidationError({"hosting_type": gettext(
            "This is an own space: plans, trials and hosting invoices apply only to hosted spaces. "
            "Change the hosting type first.")}, code="own_space")


def set_type(actor, makerspace, value, *, reason="superadmin"):
    """Record the type (audited). Changing it never deletes plans, invoices or overrides."""
    if value not in (OWN, HOSTED):
        raise ValidationError({"hosting_type": gettext("Use own or hosted.")})
    with transaction.atomic():
        row, created = SpaceHostingType.objects.select_for_update().get_or_create(
            makerspace_id=_space_id(makerspace), defaults={"hosting_type": value, "updated_by": actor})
        before = None if created else row.hosting_type
        if not created and row.hosting_type != value:
            row.hosting_type, row.updated_by = value, actor
            row.save(update_fields=["hosting_type", "updated_by", "updated_at"])
        if before != value:
            audit.record(actor, "managed_hosting.hosting_type_changed", makerspace=row.makerspace, target=row,
                         meta={"from": before, "to": value, "reason": reason})
    return row
