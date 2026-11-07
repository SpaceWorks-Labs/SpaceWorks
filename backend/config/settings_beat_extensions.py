"""Additional beat entries and deployment tombstone filtering."""

from config.settings_beat import CELERY_BEAT_SCHEDULE
from config.settings_django import TOMBSTONED_APPS
from config.settings_runtime import crontab, env

from apps.presence.schedule import beat_entries as presence_beat_entries
CELERY_BEAT_SCHEDULE.update(presence_beat_entries(TOMBSTONED_APPS))
# --- Release 2 L2: approval digest, integrity flags, storage reconcile, escalation, room health ---
CELERY_BEAT_SCHEDULE.update({
    "event-approval-digest": {"task": "apps.events.approval_digest.send_approval_digests_task",
                              "schedule": crontab(minute="*/30")},
    "event-submission-integrity": {"task": "apps.events.submissions.integrity_jobs.sweep_integrity_checks_task",
                                   "schedule": crontab(minute="*/15")},
    "event-storage-reconcile": {"task": "apps.events.submissions.storage_reconcile.reconcile_event_storage_task",
                                "schedule": crontab(hour=4, minute=25)},
    "notification-escalation": {"task": "apps.notifications.escalation.escalate_unseen_task",
                                "schedule": crontab(minute="*/5")},
    "notification-destination-health": {"task": "apps.integrations.destination_health.disable_dead_destinations_task",
                                        "schedule": crontab(minute=50)},
})
# --- lane L5 (release 2): gateway poll of open attempts and pending provider refunds.
# Read-only provider lookups; the task itself no-ops while payments_rail is tombstoned.
CELERY_BEAT_SCHEDULE["payment-gateway-poll"] = {
    "task": "apps.payments.tasks.run_gateway_poll_task", "schedule": crontab(minute="*/5"),
}
# --- end lane L5
# --- lanes L10/L11 (release 2): restore drills (one due space per hourly tick, 7-day default
# cadence per space, #128 C-22) and a requested re-encryption to rotated keys (BK-68).
CELERY_BEAT_SCHEDULE["restore-drill"] = {
    "task": "apps.backup.tasks.run_restore_drill_task", "schedule": crontab(minute=20),
}
CELERY_BEAT_SCHEDULE["reencrypt-backup-archives"] = {
    "task": "apps.backup.tasks.reencrypt_archives_task", "schedule": crontab(minute="*/10"),
}
# --- end lanes L10/L11
# --- lane L12 (release 2): loan pickup expiry and waitlist lapses; machine job quotes,
# pickup reminders, uncollected flags and prepaid jobs entering the queue. Bounded sweeps.
CELERY_BEAT_SCHEDULE["loan-pickups"] = {
    "task": "apps.hardware_requests.tasks_loans.sweep_loan_pickups_task", "schedule": crontab(minute="*/15"),
}
CELERY_BEAT_SCHEDULE["machine-job-flow"] = {
    "task": "apps.machines.tasks_jobs.sweep_job_flow_task", "schedule": crontab(minute="*/15"),
}
# --- end lane L12
# --- lane L23 (release 2): machine sessions that reached their max length, the member's
# check-out or closing time stop themselves (flagged for staff). Bounded sweep.
CELERY_BEAT_SCHEDULE["machine-sessions"] = {
    "task": "apps.machines.tasks_sessions.sweep_machine_sessions_task", "schedule": crontab(minute="*/5"),
}
# --- end lane L23
# --- lane S-C (release 2): IP auto-block rows 7 d after they end, axes rows after 30 d.
CELERY_BEAT_SCHEDULE["purge-login-security"] = {
    "task": "apps.accounts.tasks_login_security.purge_login_security_task", "schedule": crontab(hour=3, minute=40),
}
# --- end lane S-C

# --- lane L3 (release 2): card jobs resume (free tick + broker loss), 7-day result purge,
# wallet-pass refresh after renewals/expiry, and the single "photo needs update" reminder.
CELERY_BEAT_SCHEDULE["card-jobs"] = {
    "task": "apps.card_designs.tasks.resume_card_jobs", "schedule": crontab(minute="*"),
}
CELERY_BEAT_SCHEDULE["card-job-results"] = {
    "task": "apps.card_designs.tasks.purge_expired_card_job_results", "schedule": crontab(minute="7"),
}
CELERY_BEAT_SCHEDULE["card-wallet-refresh"] = {
    "task": "apps.card_designs.tasks.refresh_wallet_passes", "schedule": crontab(minute="*/30"),
}
CELERY_BEAT_SCHEDULE["event-id-cards"] = {
    "task": "apps.events.tasks_id_cards.reconcile_event_id_cards_task", "schedule": crontab(minute="*/15"),
}
CELERY_BEAT_SCHEDULE["card-photo-reminders"] = {
    "task": "apps.card_designs.tasks.remind_photo_requests", "schedule": crontab(minute="17"),
}
# --- end lane L3
# --- lane L8 (release 2): advance running per-space key jobs (re-encrypt / re-index), bounded.
CELERY_BEAT_SCHEDULE["advance-key-jobs"] = {
    "task": "apps.encryption.rekey_tasks.advance_key_jobs_task", "schedule": crontab(minute="*"),
}
# --- end lane L8 beat

# --- lane L6 (release 2): expired checkout holds, missed order settlements, one payment reminder.
CELERY_BEAT_SCHEDULE["event-order-checkouts"] = {
    "task": "apps.events.reminders_payments.sweep_order_checkouts_task", "schedule": crontab(minute="*"),
}
# --- end lane L6

# --- lane L18 (release 2): pledge periods (hourly) and sponsor perk reminders (daily).
CELERY_BEAT_SCHEDULE["donation-pledges"] = {
    "task": "apps.payments.donations.tasks.raise_pledges_task", "schedule": crontab(minute=7),
}
CELERY_BEAT_SCHEDULE["sponsor-perk-reminders"] = {
    "task": "apps.payments.donations.tasks.remind_perks_task", "schedule": crontab(hour=6, minute=17),
}
# --- end lane L18
# --- lane L22 (release 2): shop holds that lapsed, missed settlements, uncollected-order reminders.
CELERY_BEAT_SCHEDULE["shop-sweep"] = {
    "task": "apps.shop.tasks.sweep_shop_task", "schedule": crontab(minute="*"),
}
# --- end lane L22
# --- lane r2-superadmin-controls (#185, #187A): scheduled archive/purge and reminders (hourly),
# announcement emails (every 5 min), and the managed-hosting sweep (hourly; inert while off).
CELERY_BEAT_SCHEDULE["space-control-schedules"] = {
    "task": "apps.space_controls.tasks.run_space_schedules_task", "schedule": crontab(minute=23),
}
CELERY_BEAT_SCHEDULE["platform-announcement-emails"] = {
    "task": "apps.space_controls.tasks.send_announcement_emails_task", "schedule": crontab(minute="*/5"),
}
CELERY_BEAT_SCHEDULE["managed-hosting-sweep"] = {
    "task": "apps.managed_hosting.tasks.sweep_managed_hosting_task", "schedule": crontab(minute=41),
}
# The managed-hosting limiter (#187A) is OFF by default: with MANAGED_PLANS_ENABLED false nothing
# of it is visible or enforced and self-host behaves exactly as before. It also needs a managed
# deployment (PLATFORM_DOMAIN_SUFFIX). Online hosting checkout is a second switch, also off.
MANAGED_PLANS_ENABLED = env.bool("MANAGED_PLANS_ENABLED", default=False)
MANAGED_BILLING_ONLINE_ENABLED = env.bool("MANAGED_BILLING_ONLINE_ENABLED", default=False)
# --- end lane r2-superadmin-controls

if "tenant_migration" in TOMBSTONED_APPS:
    CELERY_BEAT_SCHEDULE = {
        name: entry
        for name, entry in CELERY_BEAT_SCHEDULE.items()
        if ".tenant_migration." not in entry["task"]
    }
if "events" in TOMBSTONED_APPS:
    CELERY_BEAT_SCHEDULE = {
        name: entry
        for name, entry in CELERY_BEAT_SCHEDULE.items()
        if ".events." not in entry["task"] or name in {
            "event-asset-work", "event-asset-retention", "event-asset-obligations", "event-print-cleanup",
            "event-stage-file-retention",
        }
    }
if "event_reimbursements" in TOMBSTONED_APPS:
    CELERY_BEAT_SCHEDULE = {
        name: entry for name, entry in CELERY_BEAT_SCHEDULE.items()
        if ".event_reimbursements." not in entry["task"]
    }

if "devices" in TOMBSTONED_APPS:
    CELERY_BEAT_SCHEDULE = {
        name: entry for name, entry in CELERY_BEAT_SCHEDULE.items()
        if ".devices." not in entry["task"]
    }
if "shop" in TOMBSTONED_APPS:
    CELERY_BEAT_SCHEDULE = {
        name: entry for name, entry in CELERY_BEAT_SCHEDULE.items() if ".shop." not in entry["task"]
    }
