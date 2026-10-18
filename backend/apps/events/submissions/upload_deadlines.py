from datetime import timedelta

from apps.makerspaces.private_upload_transport import bounded_not_after, PrivateTransportError
from .errors import SubmissionError


def upload_deadline(context, *, now, expires_at):
    cutoff = context.deadline + timedelta(seconds=context.grace_seconds)
    limits = (expires_at, cutoff if context.late_policy == "reject" else None)
    try:
        return bounded_not_after(now=now, purpose_max_seconds=900, limits=limits)
    except PrivateTransportError as exc:
        raise SubmissionError("uploads_closed", 409) from exc
