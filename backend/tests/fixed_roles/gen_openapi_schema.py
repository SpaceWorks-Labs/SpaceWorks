"""Not collected by default (no test_ prefix). Run explicitly to regenerate the snapshot:

    ./scripts/dev.sh test tests/fixed_roles/gen_openapi_schema.py -q
"""

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_regenerate_openapi_snapshot():
    call_command(
        "spectacular", "--format", "openapi-json",
        "--file", "/workspace/frontend/openapi-schema.json",
    )
