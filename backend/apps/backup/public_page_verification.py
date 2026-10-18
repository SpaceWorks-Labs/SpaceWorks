"""Database-only post-restore validation, including rows loaded without triggers.

Always use the candidate connection. No visibility queries, storage I/O or repairs
are allowed here: failure keeps the existing restore checkpoint closed.
"""

from collections import Counter
from copy import deepcopy

from django.apps import apps
from django.db import connections
from django.db.models import Sum

from .recipient_selection import BackupBuildError


def refuse(message):
    raise BackupBuildError(f"Public page restore verification failed: {message}.") from None


def verify_public_pages(*, using="default"):
    from apps.makerspaces.public_page_contract import validate_stored_document
    counts = {"pages": 0, "revisions": 0, "assets": 0}
    for app, name, kind in (
        ("makerspaces", "MakerspacePublicPage", "makerspace"),
        ("organizations", "OrganizationPublicPage", "organization"),
    ):
        Page = apps.get_model(app, name)
        for page in Page.objects.using(using).iterator(chunk_size=100):
            verify_pointers(page)
            counts["pages"] += 1
        Revision = apps.get_model(app, name + "Revision")
        for revision in Revision.objects.using(using).iterator(chunk_size=100):
            if revision.schema_version != 1:
                refuse("unsupported editorial snapshot schema")
            try:
                validate_stored_document(revision.document, kind=kind)
                verify_references(revision, revision.document)
            except BackupBuildError:
                raise
            except (KeyError, TypeError, ValueError):
                refuse("invalid editorial snapshot")
            except Exception:
                # DRF field errors must not expose authored text in restore logs.
                refuse("invalid snapshot")
            counts["revisions"] += 1
        Asset = apps.get_model(app, name + "Asset")
        for asset in Asset.objects.using(using).select_related("page").iterator(chunk_size=100):
            verify_asset(asset, kind, getattr(asset.page, f"{kind}_id"), using)
            counts["assets"] += 1
    from .event_page_verification import verify_event_pages
    counts["event_pages"] = verify_event_pages(using=using)
    verify_quota(using=using)
    return counts


def verify_pointers(page):
    for field in ("draft_revision_id", "published_revision_id"):
        value = getattr(page, field)
        if value is not None and not page.revisions.filter(pk=value).exists():
            refuse("missing or wrong-owner revision pointer")
    if page.published_revision_id and not page.draft_revision_id:
        refuse("publication without a draft")
    if getattr(page, "released", False) and not page.published_revision_id:
        refuse("release without a publication")


def verify_references(revision, document, *, event=False):
    """Compare exact slots, including null member links retained after withdrawal."""
    from apps.makerspaces.public_page_contract import reference_slots
    editorial = deepcopy(document.get("editorial_document") if event else document)
    members = []
    for section in editorial["sections"]:
        if section["type"] == "team":
            for row in section["payload"]["entries"]:
                if row["kind"] == "member":
                    slot = row.pop("member_slot_id")
                    if slot != row["id"]:
                        refuse("unstable member slot")
                    members.append(str(slot))
                    row["profile_id"] = 1
    assets, _ = reference_slots(editorial)
    if event:
        assets = {f"editorial:{slot}": pk for slot, pk in assets.items()}
        assets.update({f"section:{row['slug']}": row["asset_id"]
                       for row in document["sections"] if row.get("asset_id") is not None})
    actual_assets = list(revision.asset_references.values_list("slot", "asset_id", "asset__page_id"))
    if (len(actual_assets) != len(assets) or
            {slot: pk for slot, pk, _ in actual_assets} != assets or
            any(owner != revision.page_id for _, _, owner in actual_assets)):
        refuse("incomplete or foreign asset references")
    actual_members = [str(slot) for slot in revision.member_references.values_list("slot", flat=True)]
    if Counter(members) != Counter(actual_members):
        refuse("incomplete member references")


def verify_asset(asset, kind, owner_id, using):
    from apps.inventory.public_image_storage import is_safe_object_key
    from apps.makerspaces.public_page_assets import prefix
    from apps.makerspaces.website_assets import MAX_BYTES
    key = asset.object_key
    if not is_safe_object_key(key) or not 0 < asset.size_bytes <= MAX_BYTES or not asset.alt_text.strip():
        refuse("invalid private asset metadata")
    expected = (f"events/website/{owner_id}/{asset.page_id}/" if kind == "event"
                else prefix(kind, owner_id, asset.page_id))
    if key.startswith(expected):
        return
    if kind != "organization":
        Journal = apps.get_model("tenant_migration.TenantImportObject")
        if Journal.objects.using(using).filter(
            target_key=key, bucket_kind="private", job__target_makerspace_id=owner_id,
            state__in=("promoted", "verified"),
        ).exists():
            return
    refuse("private asset namespace ownership")


def verify_quota(*, using):
    """Reproduce charges from retained bytes plus unfinalized cleanup intents."""
    Asset = apps.get_model("organizations.OrganizationPublicPageAsset")
    Storage = apps.get_model("organizations.OrganizationPublicPageStorage")
    Cleanup = apps.get_model("makerspaces.PublicPageObjectCleanup")
    from apps.makerspaces.public_page_assets import MAX_ASSETS, ORGANIZATION_STORAGE_BYTES
    Organization = apps.get_model("organizations.Organization")
    for owner in Organization.objects.using(using).iterator(chunk_size=100):
        assets = Asset.objects.using(using).filter(page__organization=owner)
        pending = Cleanup.objects.using(using).filter(
            owner_kind="organization", owner_id=owner.pk, completed_at__isnull=True,
        ).exclude(object_key__in=assets.values("object_key"))
        total = (assets.aggregate(n=Sum("size_bytes"))["n"] or 0) + (pending.aggregate(n=Sum("size_bytes"))["n"] or 0)
        charged = Storage.objects.using(using).filter(organization=owner).values_list("used_bytes", flat=True).first()
        if (total != (charged or 0) or total > ORGANIZATION_STORAGE_BYTES
                or assets.count() + pending.count() > MAX_ASSETS):
            refuse("global storage accounting or allowance")
    # Tenant counters include other domains too. Never replace one with a page subtotal.
    from apps.makerspaces import limits
    if not limits.is_self_host():
        with connections[using].cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM makerspaces_makerspace m WHERE m.storage_bytes_used <
                  (SELECT coalesce(sum(size_bytes),0) FROM makerspaces_makerspacepublicpageasset a
                   JOIN makerspaces_makerspacepublicpage p ON p.id=a.page_id WHERE p.makerspace_id=m.id)
                + (SELECT coalesce(sum(a.size_bytes),0) FROM events_eventpageasset a
                   JOIN events_eventpage p ON p.id=a.page_id WHERE p.makerspace_id=m.id)
                LIMIT 1
            """)
            if cursor.fetchone():
                refuse("tenant storage counter below retained page bytes")
