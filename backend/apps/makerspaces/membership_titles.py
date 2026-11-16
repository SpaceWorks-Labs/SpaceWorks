"""Display-only member titles (X16): "Treasurer", "Mentor", coloured with a brand accent.

Behind `membership.titles`, under `manage_members`. A title grants NOTHING: authority stays
in RBAC roles, and no rbac reader looks at titles. A membership may hold several titles
and mark one primary; the card (L3) prints the primary one. Archiving a title keeps its
assignments as history but hides it from pickers and cards. Every change is audited.
"""
from django.utils.translation import gettext
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models import MakerspaceMembership, MembershipTitle, MembershipTitleAssignment

EDITABLE = ("name", "colour", "sort_order")


def _locked(makerspace_id):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(makerspace_id)
    return require_membership_feature_locked(makerspace_id, "titles")


def save_title(actor, makerspace, values, title=None):
    try:
        with transaction.atomic():
            space = _locked(makerspace.pk)
            created = title is None
            title = title or MembershipTitle(makerspace=space)
            if not created:
                title = MembershipTitle.objects.select_for_update().get(pk=title.pk, makerspace=space)
            for name in EDITABLE:
                if name in values:
                    setattr(title, name, values[name])
            title.full_clean(exclude=["makerspace"])
            title.save()
            if created:
                audit.record(actor, "membership.title_created", makerspace=space, target=title,
                             meta={"title_id": title.pk, "fields": sorted(values)})
            else:
                audit.record(actor, "membership.title_updated", makerspace=space, target=title,
                             meta={"title_id": title.pk, "fields": sorted(values)})
    except IntegrityError as exc:
        raise ValidationError({"name": gettext("A title with this name already exists.")}) from exc
    return title


def set_archived(actor, title, archived):
    with transaction.atomic():
        space = _locked(title.makerspace_id)
        title = MembershipTitle.objects.select_for_update().get(pk=title.pk)
        if (title.archived_at is not None) != archived:
            title.archived_at = timezone.now() if archived else None
            title.save(update_fields=["archived_at", "updated_at"])
            if archived:
                audit.record(actor, "membership.title_archived", makerspace=space, target=title,
                             meta={"title_id": title.pk})
            else:
                audit.record(actor, "membership.title_restored", makerspace=space, target=title,
                             meta={"title_id": title.pk})
    return title


def assign(actor, membership, title, *, primary=False):
    with transaction.atomic():
        space = _locked(membership.makerspace_id)
        membership = MakerspaceMembership.objects.select_for_update().get(pk=membership.pk)
        before = primary_title(membership)
        if title.makerspace_id != space.pk or title.archived_at is not None:
            raise ValidationError({"title_id": gettext("Choose a current title of this makerspace.")})
        if primary:
            MembershipTitleAssignment.objects.filter(membership=membership, is_primary=True).update(is_primary=False)
        row, created = MembershipTitleAssignment.objects.get_or_create(
            membership=membership, title=title,
            defaults={"makerspace": space, "is_primary": primary, "assigned_by": actor})
        if not created and row.is_primary != primary and primary:
            row.is_primary = True
            row.save(update_fields=["is_primary"])
        audit.record(actor, "membership.title_assigned", makerspace=space, target=membership,
                     meta={"membership_id": membership.pk, "title_id": title.pk, "primary": primary})
        from apps.card_designs.title_reissue import after_title_change
        after_title_change(actor, membership, before)
    return row


def unassign(actor, membership, title):
    with transaction.atomic():
        space = _locked(membership.makerspace_id)
        before = primary_title(membership)
        deleted, _ = MembershipTitleAssignment.objects.filter(membership=membership, title=title).delete()
        if deleted:
            from apps.card_designs.title_reissue import after_title_change
            after_title_change(actor, membership, before)
            audit.record(actor, "membership.title_unassigned", makerspace=space, target=membership,
                         meta={"membership_id": membership.pk, "title_id": title.pk})
    return bool(deleted)


def primary_title(membership):
    """The title the card prints (L3), or None. Archived titles are never printed."""
    row = (MembershipTitleAssignment.objects.select_related("title")
           .filter(membership=membership, title__archived_at__isnull=True)
           .order_by("-is_primary", "title__sort_order", "title__name").first())
    return row.title if row else None


def clear_titles(membership):
    """Erasure (X29): titles are part of the space's membership data."""
    MembershipTitleAssignment.objects.filter(membership=membership).delete()
