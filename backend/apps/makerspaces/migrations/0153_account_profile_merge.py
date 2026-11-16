"""Merge every person's per-membership profiles into one account profile (decision 304d).

Legacy rows are never edited or deleted. Reverse is a no-op: the account rows are derived and the
legacy rows are untouched, so rolling back leaves the old model exactly as it was.
"""

from types import SimpleNamespace

from django.db import migrations


def merge(apps, schema_editor):
    from apps.makerspaces.account_profile_merge import merge_all

    names = {
        "AccountProfile": "makerspaces", "AccountProject": "makerspaces", "AccountTimelineEntry": "makerspaces",
        "MemberProfile": "makerspaces", "MemberProject": "makerspaces", "ProfileTimelineEntry": "makerspaces",
        "AuditLog": "audit",
    }
    models = SimpleNamespace(**{name: apps.get_model(app, name) for name, app in names.items()})
    merge_all(models)


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0152_account_profile"),
        ("audit", "0001_initial"),
    ]

    operations = [migrations.RunPython(merge, migrations.RunPython.noop)]
