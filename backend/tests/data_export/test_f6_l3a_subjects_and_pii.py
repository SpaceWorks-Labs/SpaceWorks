"""Final audit 0.12.0 (m22): L3a subject selectors and the Incident.involved_note scoped-PII entry."""
from django.apps import apps

from apps.data_export.subject_selectors import SUBJECT_PATHS
from apps.encryption.registry import SOURCE_FIELDS


def test_l3a_models_have_subject_selectors_that_resolve():
    expected = {
        "maintenance.Incident": ("involved_user", "sponsor_user"),
        "machines.SupervisedParticipant": ("user",),
        "machines.SupervisedUse": ("user",),
        "machines.GuestCertificationGrant": ("user",),
    }
    for label, paths in expected.items():
        assert SUBJECT_PATHS[label] == paths
        model = apps.get_model(label)
        for path in paths:
            assert model._meta.get_field(path.split("__")[0]).is_relation


def test_incident_involved_note_is_registered_scoped_pii():
    row = next(f for f in SOURCE_FIELDS if (f.model_label, f.field_name) == ("maintenance.Incident", "involved_note"))
    assert row.makerspace_path == "makerspace_id" and row.index_kind == "none"
    assert apps.get_model("maintenance.Incident")._meta.get_field("involved_note").get_internal_type() == "TextField"
