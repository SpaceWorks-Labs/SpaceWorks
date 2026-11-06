"""Presentation-only PII masking for a platform superadmin without an open window.

Owner decision #111 Q12. PII is the scoped-encryption registry's fields plus an account's
email, phone and name. It is masked where a superadmin READS it -- staff-console API
responses, /control/ pages and PII exports -- and never anywhere else:

- never at the decrypt seam (``encryption.mappers.ScopedPiiModelMixin``): workflows,
  mail, receipts and notifications read those attributes and must keep the real values;
- never for anyone but a platform superadmin: for every other viewer RBAC alone decides.

A superadmin sees a space's PII while their window on that space is open, and a person's
PII while a per-person window on that person is open (or while every space the person
belongs to has an open window). Platform accounts are not tenant data and are not masked.
"""

from django.utils.translation import gettext
from datetime import timedelta

from django.utils import timezone

from apps.accounts.platform_authority import is_platform_superadmin
from apps.accounts.staff_identity import is_platform

MASK = "••••••"
ACCOUNT_PII_FIELDS = ("email", "phone", "phone_e164", "first_name", "last_name", "display_name")
_CACHE_ATTR = "_pii_grant_scope_cache"


def registry_field_names(model_label):
    from apps.encryption.registry import fields_for_label
    return tuple(field.field_name for field in fields_for_label(model_label))


def _scopes(viewer):
    """(space ids, person ids) the viewer has open windows on; cached until one expires."""
    now = timezone.now()
    cached = getattr(viewer, _CACHE_ATTR, None)
    if cached is not None and now < cached[0]:
        return cached[1], cached[2]
    from apps.accounts.pii_access import active_grants
    spaces, people, first_expiry = set(), set(), None
    for space_id, subject_id, expires_at in active_grants(viewer, now).values_list(
            "makerspace_id", "subject_id", "expires_at"):
        if subject_id is not None:
            people.add(subject_id)
        elif space_id is not None:
            spaces.add(space_id)
        first_expiry = expires_at if first_expiry is None else min(first_expiry, expires_at)
    until = first_expiry or now + timedelta(seconds=30)
    setattr(viewer, _CACHE_ATTR, (until, frozenset(spaces), frozenset(people)))
    return frozenset(spaces), frozenset(people)


def forget(viewer):
    """Drop the cached scopes after opening or closing a window in this request."""
    if viewer is not None and hasattr(viewer, _CACHE_ATTR):
        delattr(viewer, _CACHE_ATTR)


def pii_visible(viewer, makerspace_id, *, subject=None):
    """May this viewer read unmasked PII belonging to one makerspace (and person)?"""
    if not is_platform_superadmin(viewer):
        return True
    spaces, people = _scopes(viewer)
    if subject is not None and getattr(subject, "pk", subject) in people:
        return True
    return makerspace_id is not None and int(makerspace_id) in spaces


def person_space_ids(person):
    from apps.makerspaces.models import MakerspaceMembership
    # Both tracks: the spaces a person belongs to and the ones they staff.
    return {*MakerspaceMembership.objects.filter(user=person).values_list("makerspace_id", flat=True),
            *MakerspaceMembership.staff_tracks.filter(user=person).values_list("makerspace_id", flat=True)}


def person_pii_visible(viewer, person):
    """For account-level surfaces (/control/ user admin) where no single space applies."""
    if not is_platform_superadmin(viewer) or is_platform(person):
        return True
    spaces, people = _scopes(viewer)
    if person.pk in people:
        return True
    if not spaces:
        return False
    belongs = person_space_ids(person)
    return bool(belongs) and belongs <= spaces


def mask_data(data, names):
    """Replace every present, non-empty named value; return whether anything was masked."""
    masked = False
    for name in names:
        if data.get(name) not in (None, "", [], {}):
            data[name] = MASK
            masked = True
    return masked


def pii_makerspace_id(instance):
    """Resolve the registry-declared tenant of a row, else its own makerspace_id."""
    from apps.encryption.registry import fields_for, makerspace_id_for
    fields = fields_for(instance)
    if fields:
        return makerspace_id_for(instance, fields[0])
    return getattr(instance, "makerspace_id", None)


class PiiMaskingSerializerMixin:
    """Mask registry PII (and declared account fields) for a superadmin without a window.

    ``pii_account_fields`` names representation keys that carry an account's email, phone
    or name. Override ``get_pii_makerspace_id`` when the row reaches its space differently,
    or ``get_pii_subject`` when the row is about one person.
    """

    pii_account_fields = ()

    def get_pii_makerspace_id(self, instance):
        return pii_makerspace_id(instance)

    def get_pii_subject(self, instance):
        return None

    def pii_row_visible(self, viewer, instance):
        return pii_visible(viewer, self.get_pii_makerspace_id(instance), subject=self.get_pii_subject(instance))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        viewer = getattr(request, "user", None)
        if not is_platform_superadmin(viewer):
            return data
        if self.pii_row_visible(viewer, instance):
            return data
        names = (*registry_field_names(instance._meta.label), *self.pii_account_fields)
        if mask_data(data, names):
            data["pii_masked"] = True
        return data


def require_pii_access(viewer, makerspace_id):
    """Refuse a PII export/report to a superadmin with no open window on this space."""
    if not pii_visible(viewer, makerspace_id):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied({"detail": gettext("Open a PII access window on this space first."),
                                "code": "pii_access_required"})
