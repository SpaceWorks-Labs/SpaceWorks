"""Selectors shared by pre-Django admission (M), settings (I) and setup (R)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

DeploymentMode = Literal["host", "managed"]
DeploymentProfile = Literal["full", "free"]


@dataclass(frozen=True, slots=True)
class DeploymentSelection:
    mode: DeploymentMode = "host"
    profile: DeploymentProfile = "full"

    @property
    def is_free(self) -> bool:
        return self.profile == "free"


def parse_selection(values: Mapping[str, str]) -> DeploymentSelection:
    """Missing selectors preserve host/full. Empty or unknown values are errors.

    This validates configuration only. It confers no process, database, recovery
    or H1 authority. M must still perform admission, including role validation.
    """
    mode = values.get("SPACEWORKS_DEPLOYMENT_MODE", "host")
    profile = values.get("SPACEWORKS_DEPLOYMENT_PROFILE", "full")
    if mode not in ("host", "managed"):
        raise ValueError("SPACEWORKS_DEPLOYMENT_MODE must be host or managed.")
    if profile not in ("full", "free"):
        raise ValueError("SPACEWORKS_DEPLOYMENT_PROFILE must be full or free.")
    if profile == "free" and mode != "managed":
        raise ValueError("The free profile requires managed deployment mode.")
    return DeploymentSelection(mode=mode, profile=profile)
