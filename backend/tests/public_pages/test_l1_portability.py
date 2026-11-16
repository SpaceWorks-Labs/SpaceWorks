import csv
import pytest
from django.apps import apps
from django.db import models
from django.test.utils import isolate_apps
from apps.tenant_migration.archive_stream import PortableArchive, PORTABLE_DATASETS
from apps.tenant_migration.dependency_order import exported_models_in_dependency_order, topologically_sort_models
from apps.tenant_migration.insertion_errors import ArchiveFormatError, DependencyCycleError
from apps.tenant_migration.page_pointer_fixups import PAGE_POINTERS
from apps.events.website_section_registry import validate_payload
from rest_framework.exceptions import ValidationError


def test_full_registry_sorts_even_without_page_rows():
    labels = [model._meta.label for model in exported_models_in_dependency_order(apps)]
    assert labels.index("events.EventPage") < labels.index("events.EventPageRevision")
    assert labels.index("makerspaces.MakerspacePublicPage") < labels.index("makerspaces.MakerspacePublicPageRevision")
    assert labels.index("events.EventSessionIdentity") < labels.index("events.EventSession")
    assert set(PAGE_POINTERS) == {
        (owner, field) for owner in ("makerspaces.MakerspacePublicPage", "events.EventPage")
        for field in ("draft_revision", "published_revision")}


@isolate_apps()
def test_unrelated_cycle_remains_rejected():
    class A(models.Model):
        class Meta:
            app_label = "cycle_test"
    class B(models.Model):
        a = models.ForeignKey(A, on_delete=models.CASCADE)
        class Meta:
            app_label = "cycle_test"
    # Merged staging (decision #86): the events programme graph needs nullable pointers
    # to close cycles (PKs are preallocated and FKs deferred), so only a cycle through
    # REQUIRED foreign keys is refused. Pending owner review of the Pages-era rule that
    # every unreviewed nullable cycle was refused.
    A.add_to_class("b", models.ForeignKey(B, on_delete=models.CASCADE))
    with pytest.raises(DependencyCycleError):
        topologically_sort_models([A, B])


def write_csv(root, label, fields):
    path = root / PORTABLE_DATASETS[label].path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(fields)


def test_legacy_reader_admits_only_exact_approved_additions(tmp_path):
    dataset = PORTABLE_DATASETS["events.EventPage"]
    fields = [column.name for column in dataset.columns]
    legacy = [name for name in fields if name not in {"draft_revision_id", "published_revision_id", "editorial_document"}]
    write_csv(tmp_path, "events.EventPage", legacy)
    archive = PortableArchive(tmp_path)
    assert list(archive.raw_rows("events.EventPage")) == []
    assert list(archive.raw_rows("events.EventPageRevision")) == []
    write_csv(tmp_path, "events.EventPage", [name for name in legacy if name != "revision"])
    with pytest.raises(ArchiveFormatError):
        list(archive.raw_rows("events.EventPage"))


def test_modern_missing_dataset_is_not_treated_as_legacy(tmp_path):
    write_csv(tmp_path, "events.EventPage", [column.name for column in PORTABLE_DATASETS["events.EventPage"].columns])
    with pytest.raises(ArchiveFormatError):
        list(PortableArchive(tmp_path).raw_rows("events.EventPageRevision"))


def test_future_hackathon_provider_is_not_writable():
    with pytest.raises(ValidationError):
        validate_payload("results", {"private_participants": [1]})
