"""Fixed argv launchers for the managed process vocabulary, without shell parsing."""

import os
import sys

from apps.backup.managed.profile import DeploymentConfigurationError, deployment_profile


def integer(source, name, default, minimum, maximum):
    try:
        value = int(source.get(name, default))
    except (TypeError, ValueError):
        raise DeploymentConfigurationError(f"{name} must be an integer.") from None
    if not minimum <= value <= maximum:
        raise DeploymentConfigurationError(f"{name} is outside supported bounds.")
    return str(value)


def role_argv(role, environ=None, *, once=False):
    source = os.environ if environ is None else environ
    profile = deployment_profile(source)
    if profile.mode != "managed":
        raise DeploymentConfigurationError("Cloud role launcher requires explicit managed mode.")
    if source.get("GUNICORN_CMD_ARGS"):
        raise DeploymentConfigurationError("Use validated role options instead of GUNICORN_CMD_ARGS.")
    if profile.free and role not in {"web", "release"}:
        raise DeploymentConfigurationError("Free deployments do not admit resident worker/live/scheduler processes.")
    if once and role not in {"worker", "scheduler"}:
        raise DeploymentConfigurationError("Finite execution requires a worker or scheduler role.")
    if role == "release":
        return None
    task_profile = source.get("CLOUD_TASK_PROFILE", "brokerless" if profile.free else "redis")
    scheduler = source.get("CLOUD_SCHEDULER", "tick" if profile.free else "beat")
    if task_profile not in {"redis", "brokerless"} or scheduler not in {"beat", "loop", "external", "tick"}:
        raise DeploymentConfigurationError("Task profile or scheduler is unknown.")
    if not profile.free and ((task_profile == "brokerless" and scheduler == "beat") or (task_profile == "redis" and scheduler == "loop") or scheduler == "tick"):
        raise DeploymentConfigurationError("Task profile and scheduler disagree.")
    if task_profile == "brokerless":
        if any(source.get(name) for name in ("CELERY_BROKER_URL", "CACHE_URL", "LIVE_REDIS_URL", "CELERY_RESULT_BACKEND")):
            raise DeploymentConfigurationError("Brokerless mode requires empty broker/cache/live/result URLs.")
        if str(source.get("CELERY_TASK_ALWAYS_EAGER", "true")).lower() not in {"true", "1", "yes", "on"}:
            raise DeploymentConfigurationError("Brokerless short tasks require eager execution.")
    elif not source.get("CELERY_BROKER_URL", "").startswith(("redis://", "rediss://")):
        raise DeploymentConfigurationError("Redis task profile requires a Redis TCP/TLS broker URL.")
    elif str(source.get("CELERY_TASK_ALWAYS_EAGER", "false")).lower() in {"true", "1", "yes", "on"}:
        raise DeploymentConfigurationError("Redis task profile cannot use eager execution.")
    python = sys.executable
    if role in {"web", "live"}:
        base = [python, "-m", "gunicorn", "config.wsgi:application", "--config", "python:config.gunicorn_metrics", "--bind", "0.0.0.0:" + integer(source, "PORT", 8000, 1, 65535)]
        if role == "live":
            if not source.get("LIVE_REDIS_URL"):
                raise DeploymentConfigurationError("Live requires Redis; otherwise use polling.")
            return base + ["--worker-class", "gthread", "--workers", "1", "--threads", integer(source, "LIVE_THREADS", 16, 1, 64), "--timeout", "0", "--max-requests", "0"]
        return base + [
            "--worker-class", "sync", "--workers", integer(source, "GUNICORN_WORKERS", 1, 1, 16),
            "--threads", "1", "--timeout", integer(source, "GUNICORN_TIMEOUT", 60, 30, 600),
            "--max-requests", "400" if profile.free else "1000", "--max-requests-jitter", "50",
        ]
    if role == "worker":
        if task_profile == "brokerless":
            return [python, "-m", "apps.operations.cloud_jobs.runner", "worker"] + (["--once"] if once else [])
        if once:
            raise DeploymentConfigurationError("Finite workers require the brokerless task profile.")
        return [python, "-m", "celery", "-A", "config", "worker", "--loglevel=info", "--concurrency", integer(source, "CELERY_CONCURRENCY", 1, 1, 16), "--prefetch-multiplier", "1"]
    if role == "beat" and scheduler == "beat":
        return [python, "-m", "apps.operations.cloud_jobs.runner", "beat"]
    if role == "scheduler" and scheduler in {"loop", "external"}:
        command = [python, "-m", "apps.operations.cloud_jobs.runner", "scheduler"]
        return command + (["--once"] if once or scheduler == "external" else [])
    raise DeploymentConfigurationError("Unknown role or role incompatible with the selected scheduler.")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if len(argv) not in {1, 2} or (len(argv) == 2 and argv[1] != "--once"):
            raise DeploymentConfigurationError("Select exactly one cloud role.")
        command = role_argv(argv[0], once=len(argv) == 2)
        if command is None:
            from apps.backup.managed.release import run_release

            run_release()
            return 0
        os.execvp(command[0], command)
    except DeploymentConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 78
    except Exception:
        print("Cloud role refused; verify deployment admission and release prerequisites.", file=sys.stderr)
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
