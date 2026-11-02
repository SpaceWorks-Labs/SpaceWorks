"""Built-in, versioned attachment policies for machine service requests."""

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError


@dataclass(frozen=True)
class ServiceFilePolicy:
    name: str
    version: int
    allowed_extensions: tuple[str, ...]
    allowed_mimes: tuple[str, ...]
    max_bytes: int


def _documents_policy():
    return ServiceFilePolicy(
        name="documents",
        version=1,
        allowed_extensions=tuple(settings.MACHINE_DOC_ALLOWED_EXT),
        allowed_mimes=tuple(settings.MACHINE_DOC_ALLOWED_MIME),
        max_bytes=settings.MACHINE_DOC_MAX_BYTES,
    )


def _printer_policy():
    # This is also the policy used by the B4 public-print compatibility route.
    # Its contract must therefore remain identical to the established public
    # print upload contract, including octet-stream model uploads and the
    # larger public model-file limit.
    return ServiceFilePolicy(
        name="printer", version=1,
        allowed_extensions=tuple(settings.PRINT_ALLOWED_MODEL_EXT) + tuple(settings.PRINT_ALLOWED_SCREENSHOT_EXT),
        allowed_mimes=tuple(settings.PRINT_ALLOWED_MODEL_MIME) + tuple(settings.PRINT_ALLOWED_SCREENSHOT_MIME),
        max_bytes=settings.PRINT_UPLOAD_MAX_BYTES,
    )


def _maker_formats_policy():
    """The job flow's per-file registry policy (#142 OQ-12); `job_files` checks each file
    against its own registry entry, so this envelope only names the outer bounds."""
    from apps.maker_formats.registry import REGISTRY
    specs = list(REGISTRY.values())
    return ServiceFilePolicy(
        name="maker_formats", version=1,
        allowed_extensions=tuple(sorted({spec.extension for spec in specs})),
        allowed_mimes=tuple(sorted({spec.canonical_mime for spec in specs})),
        max_bytes=max(spec.max_bytes for spec in specs),
    )


def default_service_file_policy():
    return {"name": "documents", "version": 1}


def get_policy(name: str, version: int) -> ServiceFilePolicy:
    policies = {_documents_policy().name: _documents_policy(), _printer_policy().name: _printer_policy(),
                "maker_formats": _maker_formats_policy()}
    policy = policies.get(name)
    if policy is None or version != policy.version:
        raise ValidationError("Unknown machine service file policy.")
    return policy


def validate_service_file_policy(value):
    if not isinstance(value, dict) or set(value) != {"name", "version"}:
        raise ValidationError("File policy must contain only name and version.")
    name, version = value.get("name"), value.get("version")
    if not isinstance(name, str) or not isinstance(version, int) or isinstance(version, bool):
        raise ValidationError("File policy name and version are invalid.")
    get_policy(name, version)


def policy_for_machine(machine) -> ServiceFilePolicy:
    value = machine.service_file_policy
    validate_service_file_policy(value)
    return get_policy(value["name"], value["version"])


def policy_for_queue(queue) -> ServiceFilePolicy:
    value = queue.machine_type.capability_config or {}
    policy = value.get("service_file_policy") or default_service_file_policy()
    validate_service_file_policy(policy)
    return get_policy(policy["name"], policy["version"])
