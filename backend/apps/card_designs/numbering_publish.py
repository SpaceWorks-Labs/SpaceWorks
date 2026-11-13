"""Publish a draft numbering scheme together with the design it belongs to (O-B4).

Called from `designs._publish`: the space default design carries the space scheme, a title override
carries that title's scheme. Plan and organisation designs have none. Nothing here runs unless the
`membership.card_numbering` switch is on for the space.
"""
from django.utils import timezone

from apps.audit import services as audit

from .models_numbering import CardNumberScheme


def publish_for(actor, design):
    if design.domain != "member_cards" or design.plan_id or design.organization_id:
        return None
    from apps.makerspaces.platform import feature_enabled
    from .switches import CARD_NUMBERING
    if not feature_enabled(design.makerspace, CARD_NUMBERING):
        return None
    scheme = CardNumberScheme.objects.select_for_update().filter(
        makerspace_id=design.makerspace_id, title_id=design.title_id).first()
    if scheme is None or (scheme.draft_pattern == scheme.pattern and scheme.draft_prefix == scheme.prefix):
        return None
    scheme.prefix, scheme.pattern = scheme.draft_prefix, scheme.draft_pattern
    scheme.published_at = timezone.now()
    scheme.save(update_fields=["prefix", "pattern", "published_at", "updated_at"])
    audit.record(actor, "card_number_scheme.published", makerspace=design.makerspace, target=scheme,
                 meta={"scheme_id": scheme.pk, "title_id": design.title_id, "design_id": design.pk})
    return scheme
