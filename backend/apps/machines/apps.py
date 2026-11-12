from django.apps import AppConfig


class MachinesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.machines"

    def ready(self):
        from .notifications_p2_service import register
        from .notifications_p2_certifications import register as register_certifications
        from .notifications_p2_maintenance import register as register_maintenance
        from .notifications_p2_stock import register as register_stock
        register()
        register_certifications()
        register_maintenance()
        register_stock()
        from .notifications_job_flow import register as register_job_flow
        register_job_flow()
        from .notifications_machine_access import register as register_machine_access
        register_machine_access()
        from .notifications_sessions import register as register_sessions
        register_sessions()
