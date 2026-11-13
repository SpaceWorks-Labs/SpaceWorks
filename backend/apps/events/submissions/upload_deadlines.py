from apps.makerspaces.private_upload_transport import bounded_not_after, PrivateTransportError
from .errors import SubmissionError


def upload_deadline(context, *, now, expires_at):
    from .stage_runtime import team_cutoff
    cutoff = team_cutoff(context)  # The last stage's cutoff or the team's later extension (#178, S2).
    limits = (expires_at, cutoff if context.late_policy == "reject" else None)
    try:
        return bounded_not_after(now=now, purpose_max_seconds=900, limits=limits)
    except PrivateTransportError as exc:
        raise SubmissionError("uploads_closed", 409) from exc
