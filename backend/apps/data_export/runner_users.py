"""Bounded account closure reads; retired shells carry no exportable identity."""

from django.apps import apps

from .errors import ExportIntegrityError
from .runner_queries import after_keyset, key_value
from apps.backup.capture_managers import every_row

def _read_users(dataset, closure, page_size, deadline, monotonic):
    from .runner import _check_deadline
    model = apps.get_model("accounts.User")
    queryset = every_row(model).filter(pk__in=closure, retired_at__isnull=True)
    cursor_values, rows = None, []
    while True:
        _check_deadline(dataset.path, len(rows), deadline, monotonic)
        page_query = queryset
        if cursor_values is not None:
            page_query = page_query.filter(after_keyset(dataset.keyset, cursor_values))
        page = list(page_query.order_by(*dataset.keyset)[:page_size])
        if not page:
            break
        rows.extend(page)
        cursor_values = tuple(key_value(page[-1], name) for name in dataset.keyset)
        if any(value is None for value in cursor_values):
            raise ExportIntegrityError("global/users.csv contains a null keyset value.")
    return rows, len(rows)


def staff_track_user_ids(makerspace_id):
    """People holding a staff-track row in this space, in any status: their roster rows
    travel with the space, so their identities join the export's user closure."""
    from apps.accounts.staff_identity import person_q
    from apps.makerspaces.models import MakerspaceMembership

    return set(every_row(MakerspaceMembership).filter(
        person_q("user__"), makerspace_id=makerspace_id, track=MakerspaceMembership.Track.STAFF,
    ).values_list("user_id", flat=True))
