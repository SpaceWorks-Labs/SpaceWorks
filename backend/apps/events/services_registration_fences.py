"""Already-fenced ordinary queue locking, with no downstream account row locks."""
from .programme_locks import lock_admission_sources


def _fence(event):
    from apps.makerspaces.models import Makerspace
    lock_admission_sources(event, event.registrations.values_list("member_id", flat=True))
    event.makerspace = Makerspace.objects.select_for_update().get(pk=event.makerspace_id)
