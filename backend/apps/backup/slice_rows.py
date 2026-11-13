"""Lossless backup slices also carry staff credentials omitted from tenant exports."""

from apps.data_export.datasets import DATASET_SPECS
from apps.data_export.types import TenantPredicate
from .staff_shells import STAFF_CREDENTIAL_PATHS

SLICE_ROW_SPECS = {
    **DATASET_SPECS,
    **{label: ("", TenantPredicate((path,))) for label, path in STAFF_CREDENTIAL_PATHS.items()},
}
