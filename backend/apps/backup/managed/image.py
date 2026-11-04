"""Build-owned image marker. The one published image writes `full` and runs every profile;
only the retired reduced free image (pre-#75a) wrote `free`, and it still refuses full."""

from pathlib import Path


def image_profile():
    marker = Path(__file__).resolve().parents[3] / "SPACEWORKS_IMAGE_PROFILE"
    if not marker.exists():
        return "full"  # Images built before the marker existed are full images.
    value = marker.read_text(encoding="ascii").strip()
    if value not in {"full", "free"}:
        from .profile import DeploymentConfigurationError

        raise DeploymentConfigurationError("Image profile metadata is invalid.")
    return value
