"""Atomic owner assignment shared by makerspace creation entry points."""

from django.utils.translation import gettext
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework import serializers

from apps.audit import services as audit
from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMakerspace
from apps.organizations.services_console import (
    OrganizationConflict,
    assert_write_allowed,
    require_superadmin,
    visible_spaces,
)


def organization_slug(name, *, taken):
    """Choose a slug using a predicate that reports whether a candidate exists."""
    base = slugify(name)[:44] or "organization"
    candidate = base
    suffix = 2
    while taken(candidate):
        ending = f"-{suffix}"
        candidate = f"{base[:50 - len(ending)]}{ending}"
        suffix += 1
    return candidate


def _create_organization(actor, name):
    # A savepoint keeps a concurrent slug collision from breaking the enclosing
    # makerspace transaction; retry against the newly committed slug namespace.
    for _ in range(20):
        slug = organization_slug(
            name, taken=lambda value: Organization.objects.filter(slug=value).exists()
        )
        try:
            with transaction.atomic():
                row = Organization.objects.create(name=name, slug=slug, created_by=actor)
        except IntegrityError:
            if not Organization.objects.filter(slug=slug).exists():
                raise
            continue
        audit.record(actor, "organization.created", target=row,
                     meta={"fields": ["name", "slug"]})
        return row
    raise OrganizationConflict("Could not allocate an organization slug. Try again.")


def _validated_choice(organization_id, new_name):
    if (organization_id is None) == (new_name is None):
        message = "Choose an existing organization or provide a new name, exactly one."
        raise serializers.ValidationError({"organization_id": message, "organization_name": message})
    try:
        if new_name is not None:
            return None, serializers.CharField(max_length=200).run_validation(new_name)
        return serializers.IntegerField(min_value=1).run_validation(organization_id), None
    except serializers.ValidationError as exc:
        field = "organization_name" if new_name is not None else "organization_id"
        raise serializers.ValidationError({field: exc.detail}) from exc


def _link_owner(actor, space, *, organization_id, new_name):
    """Attach the owner link to a makerspace row the caller has already locked."""
    if OrganizationMakerspace.objects.filter(
        makerspace=space, relationship=OrganizationMakerspace.Relationship.OWNER,
    ).exists():
        raise OrganizationConflict("This makerspace already has an owner organization.")
    if new_name is not None:
        organization_id = _create_organization(actor, new_name).pk
    organization = Organization.objects.select_for_update().filter(pk=organization_id).first()
    if organization is None or not organization.is_active:
        raise serializers.ValidationError({"organization_id": gettext("Choose an existing active organization.")})
    try:
        with transaction.atomic():
            row = OrganizationMakerspace.objects.create(
                organization=organization, makerspace=space,
                relationship=OrganizationMakerspace.Relationship.OWNER, created_by=actor,
            )
    except IntegrityError as exc:
        raise OrganizationConflict("This makerspace already has an owner organization.") from exc
    audit.record(actor, "organization.link_created", makerspace=space, target=row,
                 meta={"organization_id": organization.pk, "relationship": row.relationship})
    return row


@transaction.atomic
def assign_owner_organization(actor, makerspace_id, *, organization_id=None, new_name=None):
    """Request-path owner assignment: superadmin, visibility and gate checks apply."""
    require_superadmin(actor)
    organization_id, new_name = _validated_choice(organization_id, new_name)
    # Match change_link: visibility, shared migration gate, tenant root, then org.
    get_object_or_404(visible_spaces(actor), pk=makerspace_id)
    assert_write_allowed(makerspace_id)
    space = get_object_or_404(visible_spaces(actor).select_for_update(), pk=makerspace_id)
    return _link_owner(actor, space, organization_id=organization_id, new_name=new_name)


@transaction.atomic
def bootstrap_owner_organization(actor, makerspace_id, *, new_name):
    """Owner for a makerspace ``setup_instance`` has just created, in its transaction.

    The host operator running the command is trusted, so the API guards that stop an
    unrotated generated password from reaching admin endpoints do not apply here. The
    migration gate and the tenant lock still do. Existing makerspaces never use this:
    a setup rerun goes through ``assign_owner_organization`` and its visibility rules.
    """
    _, new_name = _validated_choice(None, new_name)
    assert_write_allowed(makerspace_id)
    space = Makerspace.objects.select_for_update().get(pk=makerspace_id)
    return _link_owner(actor, space, organization_id=None, new_name=new_name)
