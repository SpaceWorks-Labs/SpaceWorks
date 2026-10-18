"""Mandatory field policy shared by readiness and fenced key maintenance."""

from django.apps import apps

from .crypto import PiiKeyUnavailable
from .registry import all_fields


def mandatory_fields():
    return tuple(item for item in all_fields() if item.encryption_required)


def assert_key_unreferenced(makerspace_id, version):
    for item in mandatory_fields():
        model = apps.get_model(item.model_label)
        path = item.makerspace_path.replace(".", "__")
        if model.objects.filter(**{
            path: makerspace_id, f"{item.field_name}__startswith": f"pii:gcm:v1:{version}:",
        }).exists():
            raise PiiKeyUnavailable("A mandatory encrypted field still references this key.")
