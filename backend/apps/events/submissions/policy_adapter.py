"""Only the installed, versioned maker policy can authorize new uploads."""
from apps.maker_formats.registry import POLICY_NAME, POLICY_VERSION
from .errors import SubmissionError


def require_policy(name, version):
    if name != POLICY_NAME or type(version) is not int or version != POLICY_VERSION:
        raise SubmissionError("upload_policy_unavailable", 503)
