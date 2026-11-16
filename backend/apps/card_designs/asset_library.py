"""The space's artwork library (decision 344(b)): every uploaded background, image and watermark of a space, reusable
from any of its designs, with storage accounting on delete.

Assets were always space-owned (`CardDesignAsset.makerspace`; a document may reference any asset of its own space);
this module adds the two missing halves: a list to pick from, and a delete that gives the storage back. A delete is
refused while ANY design draft, published document, saved revision or space template of the space still references
the asset, so restoring an old revision or applying a template can never meet a missing picture.
"""
from django.db import transaction
from django.db.models import TextField
from django.db.models.functions import Cast
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit

from .models import CardDesign, CardDesignAsset, CardDesignRevision, CardTemplate
from .storage import delete_quietly

LIST_LIMIT = 200


def _documents_mentioning(space, asset_id):
    """Where the asset id appears as text in a stored document of the space (drafts, published, revisions, templates)."""
    needle = str(asset_id)
    places = []
    for model, fields, scope in ((CardDesign, ("document", "published_document"), {"makerspace": space}),
                                 (CardDesignRevision, ("document",), {"design__makerspace": space}),
                                 (CardTemplate, ("document",), {"makerspace": space})):
        for name in fields:
            found = (model.objects.filter(**scope).annotate(_text=Cast(name, output_field=TextField()))
                     .filter(_text__contains=needle).exists())
            if found:
                places.append(f"{model.__name__}.{name}")
    return places


def list_assets(space, kind=None):
    """Ready assets of the space, newest first (at most LIST_LIMIT)."""
    rows = CardDesignAsset.objects.filter(makerspace=space, ready=True)
    if kind:
        rows = rows.filter(kind=kind)
    return list(rows.order_by("-created_at", "-pk")[:LIST_LIMIT])


@transaction.atomic
def delete_asset(actor, space, asset_id):
    from apps.makerspaces.limits_usage import free_storage
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(space.pk)
    row = CardDesignAsset.objects.select_for_update().filter(makerspace=space, asset_id=asset_id).first()
    if row is None:
        raise NotFound()
    if _documents_mentioning(space, row.asset_id):
        raise ValidationError({"asset_id": gettext("This picture is still used by a design, a saved version or a "
                                                   "template. Remove it there first."), "code": "asset_in_use"})
    key, size = row.object_key, row.size_bytes if row.ready else 0
    # The target is the space: the asset row is gone afterwards, and audit targets must outlive it.
    audit.record(actor, "card_design.asset_deleted", makerspace=space, target=space,
                 meta={"asset_id": str(row.asset_id), "kind": row.kind, "size_bytes": size})
    row.delete()
    transaction.on_commit(lambda: (delete_quietly(key), free_storage(space, size) if size else None))
