"""Exact non-shell launcher for managed beat, scheduler and durable worker roles."""
import argparse
import os


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("beat", "scheduler", "worker"))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    if settings.SPACEWORKS_DEPLOYMENT_MODE != "managed" or settings.SPACEWORKS_DEPLOYMENT_PROFILE == "free":
        parser.error("Resident cloud roles require managed full mode")
    if args.role == "beat":
        if args.once or settings.CLOUD_SCHEDULER != "beat":
            parser.error("Beat requires the beat scheduler")
        from config.celery import app
        app.Beat(scheduler="apps.operations.cloud_jobs.beat:DatabaseScheduler", max_interval=60).run()
        return
    call_command("run_scheduled_tasks", due_only=True, lane=args.role,
                 loop=not args.once, interval=60)


if __name__ == "__main__":
    main()
