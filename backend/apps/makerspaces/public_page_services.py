"""Owner-locked optimistic mutations; saving never changes the live pointer."""

from django.utils.translation import gettext
from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.audit.services import record
from .public_page_adapters import adapter
from .public_page_contract import empty_document, normalize_document
from .public_page_errors import PageConflict
from .public_page_handles import claim_locked, release_locked, owner_filter
from .public_page_revisions import append_revision, editor_document, validated_revision
from .models_profiles import PublicHandle


def lock_state(kind, owner_id, actor, version=None):
    typed = adapter(kind)
    owner, actor = typed.lock_owner(owner_id, actor)
    page = typed.page.objects.select_for_update().filter(**typed.lookup(owner)).first()
    if version is not None and (isinstance(version, bool) or not isinstance(version, int) or version < 0):
        raise ValidationError({"version": gettext("Use a nonnegative integer.")})
    if version is not None and version != (page.version if page else 0):
        raise PageConflict("stale_version", gettext("The page changed. Reload before trying again."))
    return typed, owner, actor, page


def read_state(kind, owner_id, actor):
    """Owner authority for GETs: no tenant write fence and no row locks."""
    typed = adapter(kind)
    owner, actor = typed.read_owner(owner_id, actor)
    return typed, owner, actor, typed.page.objects.filter(**typed.lookup(owner)).first()


def ensure_page(typed, owner, page, actor):
    if page is not None:
        return page
    page = typed.page.objects.create(**typed.lookup(owner))
    # Adoption preserves consented legacy identity/description/logo and required P5
    # groups. New editorial content is a separate draft and is never auto-published.
    if typed.kind == "organization" and owner.public_profile_enabled:
        baseline = append_revision(typed, page, empty_document(typed.kind), actor)
        page.draft_revision = page.published_revision = baseline
        page.save(update_fields=["draft_revision", "published_revision"])
    return page


def finish(typed, owner, page, actor, action, **metadata):
    page.version += 1
    page.save(update_fields=["version"])
    record(actor, action, makerspace=owner if typed.kind == "makerspace" else None,
           target=page, meta={"owner_kind": typed.kind, "owner_id": owner.pk,
                             "version": page.version, **metadata})
    return page


def read_editor(kind, owner_id, *, actor):
    typed, owner, actor, page = read_state(kind, owner_id, actor)
    return editor_state(typed, owner, page)


@transaction.atomic
def save(kind, owner_id, *, actor, version, document, request=None):
    typed, owner, actor, page = lock_state(kind, owner_id, actor, version)
    previous = editor_document(page.draft_revision, kind) if page and page.draft_revision_id else None
    document = normalize_document(document, kind=kind, previous=previous)
    page = ensure_page(typed, owner, page, actor)
    revision = append_revision(typed, page, document, actor, request=request)
    page.draft_revision = revision
    page.save(update_fields=["draft_revision"])
    finish(typed, owner, page, actor, "public_page.updated", revision_id=str(revision.pk),
           section_types=[row["type"] for row in document["sections"]])
    return editor_state(typed, owner, page)


@transaction.atomic
def publish(kind, owner_id, *, actor, version, draft_revision_id):
    typed, owner, actor, page = lock_state(kind, owner_id, actor, version)
    if page is None or page.draft_revision_id is None or str(page.draft_revision_id) != str(draft_revision_id):
        raise PageConflict("stale_version", gettext("Only the current saved draft can be published."))
    if not PublicHandle.objects.filter(**owner_filter(kind, owner)).exists():
        raise ValidationError({"handle": gettext("Claim a handle before publishing.")})
    validated_revision(page.draft_revision, kind)
    page.published_revision = page.draft_revision
    page.save(update_fields=["published_revision"])
    if kind == "organization":
        owner.public_profile_enabled = True
        owner.save(update_fields=["public_profile_enabled", "updated_at"])
    finish(typed, owner, page, actor, "public_page.published", revision_id=str(page.published_revision_id))
    return editor_state(typed, owner, page)


@transaction.atomic
def unpublish(kind, owner_id, *, actor, version):
    typed, owner, actor, page = lock_state(kind, owner_id, actor, version)
    page = ensure_page(typed, owner, page, actor)
    page.published_revision = None
    page.save(update_fields=["published_revision"])
    if kind == "organization":
        owner.public_profile_enabled = False
        owner.save(update_fields=["public_profile_enabled", "updated_at"])
    finish(typed, owner, page, actor, "public_page.unpublished")
    return editor_state(typed, owner, page)


@transaction.atomic
def change_handle(kind, owner_id, *, actor, version, handle=None, release=False):
    typed, owner, actor, page = lock_state(kind, owner_id, actor, version)
    page = ensure_page(typed, owner, page, actor)
    if release:
        release_locked(kind, owner, page)
        if kind == "organization":
            owner.public_profile_enabled = False
            owner.save(update_fields=["public_profile_enabled", "updated_at"])
    else:
        claim_locked(kind, owner, handle)
    finish(typed, owner, page, actor, "public_page.handle_released" if release else "public_page.handle_claimed")
    return editor_state(typed, owner, page)


def editor_state(typed, owner, page):
    from .public_page_contract import PALETTES, REQUIRED, SECTION_TYPES
    from .public_page_handles import suggestion
    claim = PublicHandle.objects.filter(**owner_filter(typed.kind, owner)).first()
    pinned = pinned_assets(page) if page else set()
    if typed.kind == "organization":
        from apps.organizations.models_public_pages import OrganizationPublicPageStorage
        storage_used = OrganizationPublicPageStorage.objects.filter(organization=owner).values_list("used_bytes", flat=True).first() or 0
        storage_limit = 100000000
    else:
        from .models import Makerspace
        from .limits import resource_limit
        storage_used = Makerspace.objects.filter(pk=owner.pk).values_list("storage_bytes_used", flat=True).get()
        storage_limit = resource_limit(owner, "storage")
    base = f"/api/v1/admin/{'makerspaces' if typed.kind == 'makerspace' else 'organizations'}/{owner.pk}/public-page/"
    return {"kind": typed.kind, "owner_id": owner.pk, "version": page.version if page else 0,
            "handle": claim.handle if claim else None,
            "draft_revision_id": page.draft_revision_id if page else None,
            "published_revision_id": page.published_revision_id if page else None,
            "document": editor_document(page.draft_revision if page else None, typed.kind),
            "assets": [{"id": row.pk, "alt_text": row.alt_text, "size_bytes": row.size_bytes,
                        "preview_url": f"{base}assets/{row.pk}/", "pinned": row.pk in pinned}
                       for row in page.assets.all()] if page else [],
            "capabilities": {"allowed_section_types": SECTION_TYPES[typed.kind], "required_groups": REQUIRED[typed.kind],
                             "palette_choices": {"inherit": None, **PALETTES}, "can_edit_details": True,
                             "can_publish": True, "suggested_handle": suggestion(typed.kind, owner)},
            "limits": {"document_bytes": 131072, "sections": 20, "assets": 50, "upload_bytes": 5000000,
                       "storage_bytes": storage_limit, "storage_bytes_used": storage_used}}


def pinned_assets(page):
    return set(page.revisions.values_list("asset_references__asset_id", flat=True))


@transaction.atomic
def preview(kind, owner_id, *, actor, version, document, request=None):
    from copy import deepcopy
    from types import SimpleNamespace
    from .models_profiles import MemberProfile
    from .public_page_contract import reference_slots
    from .public_page_projection import page_description, project_sections, presentation
    from .public_page_access import canonical_url
    from .public_profile_access import profile_is_public
    typed, owner, actor, page = lock_state(kind, owner_id, actor, version)
    previous = editor_document(page.draft_revision, kind) if page and page.draft_revision_id else None
    document = normalize_document(document, kind=kind, previous=previous)
    assets, members = reference_slots(document)
    if assets and (page is None or set(page.assets.filter(pk__in=assets.values()).values_list("pk", flat=True)) != set(assets.values())):
        raise ValidationError({"document": gettext("Images must belong to this page.")})
    profiles = {row.pk: row for row in MemberProfile.objects.filter(pk__in=members.values()).select_related(
        "membership__user", "membership__makerspace")}
    if any(not profile_is_public(profiles.get(pk)) for pk in members.values()):
        raise ValidationError({"document": gettext("Choose currently public member profiles.")})
    class PreviewReferences:
        def select_related(self, *args):
            return [SimpleNamespace(slot=slot, profile=profiles[pk]) for slot, pk in members.items()]
    stored = deepcopy(document)
    for section in stored["sections"]:
        if section["type"] == "team":
            for row in section["payload"]["entries"]:
                if row["kind"] == "member":
                    row.pop("profile_id")
                    row["member_slot_id"] = row["id"]
    preview_page = page or SimpleNamespace(assets=typed.asset.objects.none())
    revision = SimpleNamespace(document=stored, page=preview_page, member_references=PreviewReferences())
    base = f"/api/v1/admin/{'makerspaces' if kind == 'makerspace' else 'organizations'}/{owner.pk}/public-page/"
    image = lambda pk: f"{base}assets/{pk}/"
    cover = None
    if document["cover_mode"] == "asset":
        asset = page.assets.get(pk=document["cover_asset_id"])
        cover = {"url": image(asset.pk), "alt": asset.alt_text}
    return {"schema_version": 1, "kind": kind, "canonical_url": canonical_url(kind, owner),
            "title": owner.name, "description": page_description(kind, owner, document), "publication_token": None, "draft": True,
            "cover": cover, "presentation": presentation(kind, owner, document),
            "sections": project_sections(kind, owner, revision, request=request, image_url=image)}
