"""Run the periodic tasks a deployment without Celery beat would otherwise never run.

**This is the one thing that stops working silently in cloud mode.** With no broker,
`CELERY_TASK_ALWAYS_EAGER` makes `.delay()` run inline, so everything a request triggers
still works and nothing looks broken -- but `CELERY_BEAT_SCHEDULE` is beat's business,
and with no beat process nothing ever fires it. `send_return_reminders` is a duty-of-care
message in the accountability flow: a member who has not returned hardware simply stops
being reminded, and the first sign is a dispute months later.

So this exists to be driven by whatever scheduler the host already has -- a platform cron
entry, a Kubernetes CronJob, systemd timer:

    * * * * *  python manage.py run_scheduled_tasks --due-only

The typed cloud_jobs catalog declares each cadence for every scheduler, and
`--due-only` makes the command idempotent under a coarser cron: a 15-minute cron running
an hourly task fires it once an hour, not four times. State lives in `PeriodicTaskRun`
rows rather than a file, because a cloud host's filesystem is not durable and two web
dynos would not share one.

Full deployments retain this CLI-only scheduler. Owner decision #43 permits only
profile=free to mount a separate bounded, authenticated HTTP tick. That exception
never exposes this command or arbitrary task selection through HTTP.
"""

from django.conf import settings
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.operations.cloud_jobs.catalog import legacy_schedule, periodic_catalog
from apps.operations.cloud_jobs.full_scheduler import leader
from apps.operations.cloud_jobs import full_progress
from apps.operations.cloud_jobs.outcomes import require_success

SCHEDULED_TASKS = legacy_schedule()
# A tombstoned app's tasks never run from this command, exactly as before the catalog
# (the beat schedule drops them the same way in config/settings.py). Events keeps the
# byte-retention and custody sweeps that must outlive the app (events programme).
_TOMBSTONE_RETAINED = {"events": frozenset({
    "event-asset-work", "event-asset-retention", "event-asset-obligations", "event-print-cleanup",
    "event-stage-file-retention",
})}
for _tombstoned in ("tenant_migration", "events", "event_reimbursements", "devices", "presence", "notifications"):
    if _tombstoned in settings.TOMBSTONED_APPS:
        SCHEDULED_TASKS = tuple(task for task in SCHEDULED_TASKS if f".{_tombstoned}." not in task[1]
                                or task[0] in _TOMBSTONE_RETAINED.get(_tombstoned, ()))
EVIDENCE_OPTION_TASKS = frozenset({"evidence-object-expiry", "evidence-abandoned-upload-cleanup"})


def _import_task(dotted_path):
    from importlib import import_module

    module_path, _, attribute = dotted_path.rpartition(".")
    return getattr(import_module(module_path), attribute)


class Command(BaseCommand):
    help = "Run periodic tasks on a deployment with no Celery beat process."

    def add_arguments(self, parser):
        parser.add_argument(
            "--due-only",
            action="store_true",
            help="Skip tasks run more recently than their declared interval.",
        )
        parser.add_argument("--task", help="Run only this task name.")
        parser.add_argument("--lane", choices=("all", "scheduler", "worker"), default="all")
        parser.add_argument("--loop", action="store_true", help="Run the selected full-profile lane continuously.")
        parser.add_argument("--interval", type=int, default=60, help="Loop polling interval, 1..60 seconds.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview an evidence task without deleting rows or objects.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            help="Evidence rows per makerspace (clamped to 1..1000).",
        )

    def handle(self, *args, **options):
        if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
            raise CommandError("Free profile uses the authenticated bounded tick; resident schedulers are forbidden.")
        if not 1 <= options["interval"] <= 60:
            raise CommandError("--interval must be in 1..60 seconds.")
        if options["loop"] and (options["lane"] == "all" or not options["due_only"]):
            raise CommandError("--loop requires --due-only and --lane scheduler or worker.")
        lane = "worker" if options["lane"] == "worker" else "scheduler"
        with leader(lane) as lock:
            while True:
                self._run_pass(options, lock)
                if options["lane"] == "worker" and not options.get("task"):
                    from apps.operations.cloud_jobs.work import run_persisted_work
                    if lock is None:
                        from apps.operations.cloud_jobs.contracts import admit
                        fence = admit
                    else:
                        fence = lock.check
                    run_persisted_work(fence=fence)
                if not options["loop"]:
                    return
                time.sleep(options["interval"])

    def _run_pass(self, options, lock):
        from apps.operations.models_scheduling import PeriodicTaskRun
        from apps.operations.cloud_jobs.diagnostics import scheduler_heartbeat, scheduler_completed
        if options["lane"] != "worker":
            scheduler_heartbeat("loop" if options["loop"] else "external")

        only = options.get("task")
        known = [name for name, _path, _interval in SCHEDULED_TASKS]
        if only and only not in known:
            # A typo here used to exit 0 having run nothing, which a cron entry reports
            # as success forever. Tombstoned apps' tasks are already absent from the list.
            raise CommandError(f"Unknown task {only!r}. Known tasks: {', '.join(known)}.")
        if (options["dry_run"] or options["batch_size"] is not None) and only not in EVIDENCE_OPTION_TASKS:
            raise CommandError(
                "--dry-run and --batch-size require --task evidence-object-expiry or "
                "evidence-abandoned-upload-cleanup."
            )
        now = timezone.now()
        failed = []
        catalog = {task.key: task for task in periodic_catalog()}
        heavy = {task.key for task in catalog.values() if task.heavy}
        for name, dotted_path, interval_minutes in SCHEDULED_TASKS:
            if only and name != only:
                continue
            if options["lane"] == "scheduler" and name in heavy:
                continue
            if options["lane"] == "worker" and name not in heavy:
                continue
            if lock is not None:
                lock.check()
            with transaction.atomic():
                # Locked, so two cron entries or two dynos firing at the same minute run
                # the task once between them rather than twice. The reminder mail is the
                # reason this matters: sending it twice is worse than sending it late.
                # Claiming first makes this AT-MOST-ONCE, deliberately: a missed run is
                # preferable to sending the return reminder twice.
                row, _ = PeriodicTaskRun.objects.select_for_update().get_or_create(name=name)
                if options["due_only"] and not row.is_due(now, interval_minutes):
                    self.stdout.write(f"skip {name} (last run {row.last_run_at:%Y-%m-%d %H:%M})")
                    continue
                # A preview must not postpone the next real sweep under --due-only.
                if not options["dry_run"]:
                    row.last_run_at = now
                    row.save(update_fields=["last_run_at"])

            attempt = None
            task = catalog[name]
            try:
                # Called directly, not via .delay(): under eager mode they are the
                # same thing, and with a broker configured this command should still
                # do the work rather than queue it behind a worker that may not exist.
                task_options = {}
                if name in EVIDENCE_OPTION_TASKS:
                    task_options = {
                        "dry_run": options["dry_run"],
                        "batch_size": options["batch_size"],
                    }
                if lock is not None:
                    lock.check()
                if not options["dry_run"]:
                    attempt = full_progress.begin(task, lock)
                require_success(_import_task(dotted_path)(**task_options))
                if lock is not None:
                    lock.check()
                full_progress.end(attempt, task, lock)
                scheduler_completed()
            except Exception as exc:  # noqa: BLE001 - one failing task must not stop the rest
                scheduler_completed(failed=True)
                full_progress.end(attempt, task, lock, failed=True)
                with transaction.atomic():
                    row = PeriodicTaskRun.objects.select_for_update().get(name=name)
                    row.last_error = type(exc).__name__
                    row.save(update_fields=["last_error"])
                self.stderr.write(self.style.ERROR(f"failed {name}: {type(exc).__name__}"))
                failed.append(name)
                if lock is not None and lock.lost:
                    raise CommandError("Scheduler guard lost; generation must be re-admitted.") from None
                continue

            with transaction.atomic():
                row = PeriodicTaskRun.objects.select_for_update().get(name=name)
                row.last_error = ""
                row.save(update_fields=["last_error"])
            self.stdout.write(self.style.SUCCESS(f"ran {name}"))

        # Host deployments keep their original contract: failures are recorded per task
        # (last_error) and the pass exits 0. A managed one-off provider job reports them
        # through its exit status; a resident loop must never die on one failed task.
        if failed and getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") == "managed" and not options["loop"]:
            raise CommandError(f"{len(failed)} scheduled task(s) failed: {', '.join(failed)}")
