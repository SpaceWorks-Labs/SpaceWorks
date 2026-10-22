"""Build-owned profile marker; the integrator writes this in the free image target."""

from pathlib import Path


def image_profile():
    marker = Path(__file__).resolve().parents[3] / "SPACEWORKS_IMAGE_PROFILE"
    if not marker.exists():
        return "full"  # Existing full images predate the additional image variant.
    value = marker.read_text(encoding="ascii").strip()
    if value not in {"full", "free"}:
        from .profile import DeploymentConfigurationError

        raise DeploymentConfigurationError("Image profile metadata is invalid.")
    return value
