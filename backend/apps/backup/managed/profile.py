"""Parse deployment selectors before importing Django or reading a host marker."""

from dataclasses import dataclass
import os

from apps.backup.process_roles import ProcessRole


class DeploymentConfigurationError(ValueError):
    code = "deployment_configuration_invalid"


@dataclass(frozen=True, slots=True)
class DeploymentProfile:
    mode: str = "host"
    profile: str = "full"

    @property
    def free(self):
        return self.profile == "free"


FREE_ENV = {
    "CLOUD_TASK_PROFILE": "brokerless", "CLOUD_SCHEDULER": "tick",
    "CELERY_BROKER_URL": "", "CACHE_URL": "", "LIVE_REDIS_URL": "",
    "CELERY_RESULT_BACKEND": "", "CELERY_TASK_ALWAYS_EAGER": "true",
    "GUNICORN_WORKERS": "1", "GUNICORN_THREADS": "1",
    "GUNICORN_WORKER_CLASS": "sync", "UPLOAD_SCAN_POLICY": "none",
}


def deployment_profile(environ=None):
    source = os.environ if environ is None else environ
    mode = source.get("SPACEWORKS_DEPLOYMENT_MODE", "host")
    profile = source.get("SPACEWORKS_DEPLOYMENT_PROFILE", "full")
    if mode not in {"host", "managed"} or profile not in {"full", "free"}:
        raise DeploymentConfigurationError("Select deployment mode host|managed and profile full|free.")
    if profile == "free" and mode != "managed":
        raise DeploymentConfigurationError("The free profile requires explicit managed mode.")
    # This value must come from immutable image build metadata, never operator env.
    from .image import image_profile

    if image_profile() == "free" and profile != "free":
        raise DeploymentConfigurationError("A reduced free image cannot run the full profile.")
    if profile == "free":
        for name, expected in FREE_ENV.items():
            value = source.get(name, expected)
            if name == "CELERY_TASK_ALWAYS_EAGER":
                value = "true" if str(value).lower() in {"true", "1", "yes", "on"} else "false"
            if value != expected:
                raise DeploymentConfigurationError(f"{name} contradicts the free profile.")
        if source.get("GUNICORN_CMD_ARGS"):
            raise DeploymentConfigurationError("GUNICORN_CMD_ARGS is not supported in the free profile.")
    elif mode == "managed" and source.get("CLOUD_SCHEDULER") == "tick":
        raise DeploymentConfigurationError("The tick scheduler is exclusive to the free profile.")
    return DeploymentProfile(mode, profile)


def effective_environment(environ):
    """Return a copy; full deployments receive no free defaults or mutations."""
    profile = deployment_profile(environ)
    result = dict(environ)
    if profile.free:
        for name, value in FREE_ENV.items():
            result.setdefault(name, value)
    return result


def validate_process(profile, role, command):
    role = ProcessRole(role)
    fixed = ["python", "-m", "scripts.run_cloud_role"]
    runtime_management = {"verify_storage", "reconcile_cloud_email", "reconcile_cloud_storage",
                          "bind_legacy_storage_receipts", "migrate_cloud_storage", "resume_cloud_storage", "recover_managed_capture",
                          "reconcile_cloud_outbox", "cancel_cloud_delivery"}
    if profile.mode != "managed":
        return
    if role == ProcessRole.MIGRATE and command != fixed + ["release"]:
        raise DeploymentConfigurationError("Managed migrations require the fixed release command.")
    if not profile.free:
        allowed = {
            ProcessRole.BACKEND: ("web", "live"), ProcessRole.WORKER: ("worker",),
            ProcessRole.BEAT: ("beat",), ProcessRole.CRON: ("scheduler",),
            ProcessRole.MIGRATE: ("release",),
        }
        admitted_commands = [fixed + [name] for name in allowed.get(role, ())]
        if role in {ProcessRole.WORKER, ProcessRole.CRON}:
            admitted_commands += [argv + ["--once"] for argv in admitted_commands]
        if role in allowed and command not in admitted_commands:
            raise DeploymentConfigurationError("Managed process role and fixed command disagree.")
        if role == ProcessRole.MANAGEMENT:
            finite = {
                "check", "showmigrations", "setup_instance", "setup_platform_email",
                "backup_preflight", "export_tenant_migration_archive", "export_portable_tenant_dump", "verify_storage",
            }
            finite |= runtime_management
            adopt = command == ["python", "-m", "apps.backup.managed.adopt"]
            if not adopt and not (len(command) >= 3 and command[:2] == ["python", "manage.py"] and command[2] in finite):
                raise DeploymentConfigurationError("Managed management command is not in the finite allowlist.")
    if profile.free:
        admitted = {
            ProcessRole.BACKEND: fixed + ["web"],
            ProcessRole.MIGRATE: fixed + ["release"],
        }
        finite = {"check", "showmigrations", "setup_instance", "setup_platform_email", "verify_storage"}
        finite |= runtime_management
        if role == ProcessRole.MANAGEMENT and command == ["python", "-m", "apps.backup.managed.adopt"]:
            return
        if role == ProcessRole.MANAGEMENT and len(command) >= 3 and command[:2] == ["python", "manage.py"] and command[2] in finite:
            return
        if command != admitted.get(role):
            raise DeploymentConfigurationError("Free profile admits one web worker and finite release/setup commands only.")
