"""Serialisation of notification-job arguments: ids and call-time state only, never personal data."""
from django.db import models


class Unserializable(TypeError):
    pass


_STATE_FIELDS = (models.BooleanField, models.IntegerField, models.FloatField, models.DecimalField,
                 models.DateTimeField, models.DateField)


def _scalar(value):
    import datetime
    import decimal
    import uuid
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime.datetime):
        return {"dt": value.isoformat()}
    if isinstance(value, datetime.date):
        return {"da": value.isoformat()}
    if isinstance(value, decimal.Decimal):
        return {"dec": str(value)}
    if isinstance(value, uuid.UUID):
        return {"uu": str(value)}
    raise Unserializable(type(value).__name__)


def _unscalar(value):
    import datetime
    import decimal
    import uuid
    if isinstance(value, dict):
        if "dt" in value:
            return datetime.datetime.fromisoformat(value["dt"])
        if "da" in value:
            return datetime.date.fromisoformat(value["da"])
        if "dec" in value:
            return decimal.Decimal(value["dec"])
        if "uu" in value:
            return uuid.UUID(value["uu"])
    return value


def _state_snapshot(row):
    """The row's state-bearing columns AS OF THE CALL (status, version, timestamps, enum choices, FK ids).

    Dedup keys and revisions read these; the worker overlays them on the freshly loaded row so a job that runs a
    moment later still computes the key the caller would have. Free text, names and addresses are never captured
    (nothing personal enters the job row), and account models are never snapshotted.
    """
    if row._meta.app_label == "accounts":
        return {}
    snap = {}
    for field in row._meta.concrete_fields:
        enum_like = isinstance(field, models.CharField) and field.choices
        if not (isinstance(field, _STATE_FIELDS) or enum_like or field.many_to_one):
            continue
        if "birth" in field.name:
            continue
        try:
            snap[field.attname] = _scalar(getattr(row, field.attname))
        except Unserializable:
            continue
    return snap


def _encode(value):
    if isinstance(value, models.Model):
        if value.pk is None:
            raise Unserializable("unsaved row")
        return {"m": value._meta.label_lower, "pk": value.pk, "f": _state_snapshot(value)}
    if isinstance(value, str):
        if "@" in value:
            raise Unserializable("address-like string")  # nothing personal rides the job row
        return value
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return {"l": [_encode(item) for item in value]}
    if isinstance(value, dict) and all(isinstance(key, str) and "@" not in key for key in value):
        return {"d": {key: _encode(item) for key, item in value.items()}}
    return _scalar(value)


class SubjectGone(LookupError):
    pass


def _decode(value):
    from django.apps import apps
    if isinstance(value, dict):
        if "m" in value:
            row = apps.get_model(value["m"]).objects.filter(pk=value["pk"]).first()
            if row is None:
                raise SubjectGone(value["m"])
            for name, stored in (value.get("f") or {}).items():
                setattr(row, name, _unscalar(stored))  # in memory only; the row is never saved from here
            return row
        if "l" in value:
            return [_decode(item) for item in value["l"]]
        if "d" in value:
            return {key: _decode(item) for key, item in value["d"].items()}
        return _unscalar(value)
    return value
