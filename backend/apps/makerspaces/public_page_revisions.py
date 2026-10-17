"""Append complete immutable documents with typed asset/member reference sets."""

from copy import deepcopy
from rest_framework.exceptions import ValidationError
from .models_profiles import MemberProfile
from .public_profile_access import profile_is_public
from .public_page_contract import reference_slots, normalize_document


def append_revision(adapter, page, document, actor, *, request=None):
    document = normalize_document(document, kind=adapter.kind)
    assets, members = reference_slots(document)
    owned_assets = set(page.assets.filter(pk__in=assets.values()).values_list("pk", flat=True))
    if owned_assets != set(assets.values()):
        raise ValidationError({"document": "Images must belong to this page."})
    if any(not text.strip() for text in page.assets.filter(pk__in=assets.values()).values_list("alt_text", flat=True)):
        raise ValidationError({"document": "Referenced images require descriptive alt text."})
    profiles = {row.pk: row for row in MemberProfile.objects.filter(pk__in=members.values()).select_related(
        "membership__user", "membership__makerspace")}
    from .public_profile_access import _request_tenant_ids
    scopes = _request_tenant_ids(request) if request else []
    for pk in members.values():
        profile = profiles.get(pk)
        if (not profile_is_public(profile) or any(scope != profile.membership.makerspace_id for scope in scopes)
                or profile.membership.user.account_kind != "member"):
            raise ValidationError({"document": "Choose a currently public member profile in the permitted scope."})
    stored = deepcopy(document)
    for section in stored["sections"]:
        if section["type"] == "team":
            for entry in section["payload"]["entries"]:
                if entry["kind"] == "member":
                    entry.pop("profile_id")
                    entry["member_slot_id"] = entry["id"]
    revision = adapter.revision.objects.create(page=page, document=stored, created_by=actor)
    adapter.asset_reference.objects.bulk_create([
        adapter.asset_reference(revision=revision, slot=slot, asset_id=pk) for slot, pk in assets.items()])
    adapter.member_reference.objects.bulk_create([
        adapter.member_reference(revision=revision, slot=slot, profile_id=pk) for slot, pk in members.items()])
    return revision


def editor_document(revision, kind):
    from .public_page_contract import empty_document
    if revision is None:
        return empty_document(kind)
    result = deepcopy(revision.document)
    refs = {str(row.slot): row.profile_id for row in revision.member_references.all()}
    for section in result["sections"]:
        if section["type"] == "team":
            entries = []
            for entry in section["payload"]["entries"]:
                if entry["kind"] == "member":
                    pk = refs.get(entry.pop("member_slot_id"))
                    if pk is None:
                        continue
                    entry["profile_id"] = pk
                entries.append(entry)
            section["payload"]["entries"] = entries
    return result


def validated_revision(revision, kind):
    return normalize_document(editor_document(revision, kind), kind=kind)
