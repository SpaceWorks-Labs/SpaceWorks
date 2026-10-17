"""Live domain authority for the retained staff matrix/room lifecycle legs."""
from types import SimpleNamespace


def eligible_source(space, feature, event, source):
    from apps.makerspaces.servability import is_servable
    from .recipients import feature_available
    from .notification_sources import source_eligible
    space.refresh_from_db()
    kind = source["source_kind"]
    if not is_servable(space) or not feature_available(space, feature, source_kind=kind):
        return False
    return source_eligible(SimpleNamespace(**source, makerspace=space, makerspace_id=space.pk,
        audience="staff", recipient_id=None, feature=feature, event=event))
