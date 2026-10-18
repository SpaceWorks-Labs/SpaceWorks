"""Extend the existing namespace without claiming names or changing consent."""

from django.conf import settings
from django.db import migrations, models

PATTERN = r"^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])$"


def owners():
    return (
        models.Q(user__isnull=False, profile__isnull=False, makerspace__isnull=True, organization__isnull=True)
        | models.Q(user__isnull=True, profile__isnull=True, makerspace__isnull=False, organization__isnull=True)
        | models.Q(user__isnull=True, profile__isnull=True, makerspace__isnull=True, organization__isnull=False)
    )


def backfill_redirect_users(apps, schema_editor):
    redirects = apps.get_model("makerspaces", "PublicHandleRedirect")
    for row in redirects.objects.using(schema_editor.connection.alias).select_related("profile__membership").iterator():
        redirects.objects.using(schema_editor.connection.alias).filter(pk=row.pk).update(user_id=row.profile.membership.user_id)


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0096_enable_existing_presence"),
                    ("organizations", "0004_organization_is_discoverable"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AlterField(model_name="publichandle", name="user", field=models.OneToOneField(
            settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="public_handle")),
        migrations.AlterField(model_name="publichandle", name="profile", field=models.ForeignKey(
            "makerspaces.memberprofile", null=True, blank=True, on_delete=models.CASCADE, related_name="handles")),
        migrations.AlterField(model_name="publichandleredirect", name="profile", field=models.ForeignKey(
            "makerspaces.memberprofile", null=True, blank=True, on_delete=models.CASCADE, related_name="handle_redirects")),
        migrations.AddField(model_name="publichandleredirect", name="user", field=models.ForeignKey(
            settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="public_handle_redirects")),
        migrations.RunPython(backfill_redirect_users, migrations.RunPython.noop),
    ]
    for model in ("publichandle", "publichandleredirect"):
        for app, owner in (("makerspaces", "makerspace"), ("organizations", "organization")):
            field_type = models.OneToOneField if model == "publichandle" else models.ForeignKey
            operations.append(migrations.AddField(model_name=model, name=owner, field=field_type(
                f"{app}.{owner}", null=True, blank=True, on_delete=models.CASCADE,
                related_name="public_handle" if model == "publichandle" else "public_handle_redirects")))
        operations.append(migrations.AddConstraint(model_name=model, constraint=models.CheckConstraint(
            condition=owners(), name="public_handle_typed_owner" if model == "publichandle" else "redirect_handle_typed_owner")))
    operations.append(migrations.AddConstraint(model_name="publichandleredirect", constraint=models.CheckConstraint(
        condition=models.Q(handle__regex=PATTERN), name="redirect_handle_grammar")))
