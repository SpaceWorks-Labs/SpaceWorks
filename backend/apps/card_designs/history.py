"""Version history: every saved revision of a design, and restoring one as the new draft.

Revisions are append-only (`CardDesignRevision`), so history is complete and restoring
never rewrites it: the old document is saved as a NEW revision (compare-and-swap, the
same validation as any save) and audited `card_design.restored`. Publishing stays a
separate step, so a restore never changes what holders' cards print.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.audit import services as audit

from . import designs
from .models import CardDesignApproval, CardDesignRevision


def revisions(design):
    """Newest first, each marked published / submitted / approved where that applies."""
    approvals = {row.revision: row.decision for row in CardDesignApproval.objects.filter(design=design)}
    rows = CardDesignRevision.objects.filter(design=design).select_related("created_by").order_by("-revision")
    return rows, approvals


def describe(row, design, approvals):
    author = row.created_by
    return {"revision": row.revision, "created_at": row.created_at,
            "created_by": (author.get_full_name() or author.username) if author else "",
            "is_current": row.revision == design.revision,
            "is_published": row.revision == design.published_revision,
            "review": approvals.get(row.revision, ""),
            "layers": sum(len((row.document.get(side) or {}).get("layers", ())) for side in ("front", "back"))}


def revision(design, number):
    return get_object_or_404(CardDesignRevision, design=design, revision=number)


@transaction.atomic
def restore(actor, design, number, *, expected_revision, acted_for=None):
    source = revision(design, number)
    if number == design.revision:
        return design
    restored = designs.save(actor, design, source.document, expected_revision=expected_revision, acted_for=acted_for)
    audit.record(actor, "card_design.restored", makerspace=restored.makerspace, target=restored,
                 meta={"design_id": restored.pk, "domain": restored.domain, "from_revision": number,
                       "revision": restored.revision, "event_id": restored.event_id,
                       "programme_id": restored.programme_id})
    return restored
