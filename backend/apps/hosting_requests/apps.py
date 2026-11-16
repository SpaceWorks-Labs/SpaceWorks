from django.apps import AppConfig


class HostingRequestsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.hosting_requests"
    verbose_name = "Hosting requests"

    def ready(self):
        # Applicant mail carries source_kind="hosting_request" so retention can find and
        # delete its EmailLog rows. An unregistered source kind makes delivery refuse
        # the message, so the source must be registered before any send.
        from apps.hosting_requests.notifications import register_delivery_source

        register_delivery_source()
