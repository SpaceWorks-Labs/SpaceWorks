"""Read-only deployment facts on the existing superadmin backup settings page."""
import json

from django.contrib import admin
from django.utils.html import format_html

from .admin import ReadOnlyBackupAdmin
from .models import PlatformBackupSettings


@admin.register(PlatformBackupSettings)
class PlatformBackupSettingsAdmin(ReadOnlyBackupAdmin):
    readonly_fields = (*[field.name for field in PlatformBackupSettings._meta.fields], "deployment")

    @admin.display(description="Deployment")
    def deployment(self, obj):
        from apps.operations.deployment_projection import deployment_projection
        return format_html("<pre>{}</pre>", json.dumps(deployment_projection(), indent=2, default=str))
