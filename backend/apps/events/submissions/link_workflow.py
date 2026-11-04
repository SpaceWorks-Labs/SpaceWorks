"""Draft links are revised with the project aggregate, frozen links never change."""
from .errors import SubmissionError
from .links import normalize_link
from .models_projects import SubmissionLink


def replace_links_locked(project, values):
    if not isinstance(values, list) or len(values) > 30:
        raise SubmissionError("invalid_links")
    normalized = []
    for value in values:
        if not isinstance(value, dict) or set(value) != {"kind", "url", "public_requested"}:
            raise SubmissionError("invalid_links")
        if type(value["public_requested"]) is not bool:
            raise SubmissionError("invalid_consent")
        url, provider = normalize_link(value["url"], value["kind"])
        normalized.append((value["kind"], url, provider, value["public_requested"]))
    # Retain rows referenced by old snapshots. Removed draft rows are excluded
    # using a current-version marker instead of deleting frozen provenance.
    next_version = project.version + 1
    for kind, url, provider, public in normalized:
        SubmissionLink.objects.create(submission=project, kind=kind, url=url, provider=provider,
                                      public_requested=public, version=next_version)
    project.links_version = next_version
