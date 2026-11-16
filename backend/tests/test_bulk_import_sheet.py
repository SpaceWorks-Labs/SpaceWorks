import datetime
import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.admin_api import bulk_import_sheet
from apps.audit.models import AuditLog
from tests.return_helpers import authenticated_client, make_member, make_print_manager, make_space

pytestmark = pytest.mark.django_db
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def sheet_url(space):
    return f"/api/v1/admin/makerspace/{space.id}/inventory/import/sheet"


def workbook_bytes(*sheets):
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for title, rows in sheets:
        sheet = workbook.create_sheet(title)
        for row in rows:
            sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def upload(data, name="stock.xlsx"):
    return SimpleUploadedFile(name, data, content_type=XLSX)


def post(user, space, data, name="stock.xlsx"):
    return authenticated_client(user).post(sheet_url(space), {"file": upload(data, name)}, format="multipart")


def test_happy_path_returns_first_sheet_rows_like_the_browser_parser():
    space = make_space("sheet-happy")
    manager = make_member("sheet-happy-manager", space)
    data = workbook_bytes(
        ("Stock", [
            ["Name", "Qty", "Bought", "Notes", None],
            ["Calipers", 2, datetime.date(2026, 1, 5), None, None],
            [None, None, None, None, None],
            ["Scope", 1, None, "=1+1", None],
        ]),
        ("Other", [["Ignored"], ["x"]]),
    )
    response = post(manager, space, data)
    assert response.status_code == 200, response.content
    assert response.json() == {"rows": [
        {"Name": "Calipers", "Qty": 2, "Bought": "2026-01-05T00:00:00", "Notes": ""},
        # data_only reads the cached value; openpyxl-written formulas have none, so no evaluation happens.
        {"Name": "Scope", "Qty": 1, "Bought": "", "Notes": ""},
    ]}
    log = AuditLog.objects.get(action="inventory.bulk_import_sheet_read", makerspace=space)
    assert log.actor_id == manager.id
    assert log.meta["rows"] == 2 and log.meta["columns"] == 4


def test_staff_without_edit_inventory_is_refused():
    space = make_space("sheet-perm")
    machine_manager = make_print_manager("sheet-perm-machines", space)
    response = post(machine_manager, space, workbook_bytes(("S", [["Name"], ["A"]])))
    assert response.status_code == 403
    assert not AuditLog.objects.filter(action="inventory.bulk_import_sheet_read").exists()


def test_manager_of_another_space_is_refused():
    space = make_space("sheet-tenant-a")
    other = make_space("sheet-tenant-b")
    outsider = make_member("sheet-tenant-b-manager", other)
    response = post(outsider, space, workbook_bytes(("S", [["Name"], ["A"]])))
    assert response.status_code == 404  # 481(1): another space answers like a missing one


def test_anonymous_is_refused():
    space = make_space("sheet-anon")
    from rest_framework.test import APIClient

    response = APIClient().post(sheet_url(space), {"file": upload(workbook_bytes(("S", [["Name"]])))}, format="multipart")
    assert response.status_code in (401, 403)


def test_module_off_is_refused():
    space = make_space("sheet-module-off")
    manager = make_member("sheet-module-off-manager", space)
    space.enabled_modules = [key for key in space.enabled_modules if key != "bulk_import"]
    space.save(update_fields=["enabled_modules"])
    response = post(manager, space, workbook_bytes(("S", [["Name"], ["A"]])))
    assert response.status_code == 404
    assert response.json()["code"] == "module_disabled"


def test_malformed_file_is_a_400_not_a_500():
    space = make_space("sheet-malformed")
    manager = make_member("sheet-malformed-manager", space)
    response = post(manager, space, b"PK\x03\x04 this is not really a workbook")
    assert response.status_code == 400
    assert response.json()["file"] == "XLSX file could not be read."


def test_non_xlsx_name_is_refused():
    space = make_space("sheet-csv")
    manager = make_member("sheet-csv-manager", space)
    response = post(manager, space, b"Name\nA\n", name="stock.csv")
    assert response.status_code == 400


def test_size_limit(monkeypatch):
    space = make_space("sheet-size")
    manager = make_member("sheet-size-manager", space)
    monkeypatch.setattr(bulk_import_sheet, "MAX_IMPORT_UPLOAD_BYTES", 100)
    response = post(manager, space, workbook_bytes(("S", [["Name"], ["A"]])))
    assert response.status_code == 400
    assert "bytes or smaller" in response.json()["file"]


def test_row_limit(monkeypatch):
    space = make_space("sheet-rows")
    manager = make_member("sheet-rows-manager", space)
    monkeypatch.setattr(bulk_import_sheet, "MAX_IMPORT_ROWS", 3)
    response = post(manager, space, workbook_bytes(("S", [["Name"]] + [[f"Item {i}"] for i in range(5)])))
    assert response.status_code == 400
    assert "3 rows" in response.json()["file"]


def test_column_limit(monkeypatch):
    space = make_space("sheet-cols")
    manager = make_member("sheet-cols-manager", space)
    monkeypatch.setattr(bulk_import_sheet, "MAX_IMPORT_COLUMNS", 3)
    response = post(manager, space, workbook_bytes(("S", [["A", "B", "C", "D"], [1, 2, 3, 4]])))
    assert response.status_code == 400
    assert "3 columns" in response.json()["file"]


def test_trailing_blank_columns_do_not_trip_the_column_limit(monkeypatch):
    space = make_space("sheet-cols-blank")
    manager = make_member("sheet-cols-blank-manager", space)
    monkeypatch.setattr(bulk_import_sheet, "MAX_IMPORT_COLUMNS", 2)
    response = post(manager, space, workbook_bytes(("S", [["A", "B", None, None], [1, 2, None, 9]])))
    assert response.status_code == 200
    assert response.json() == {"rows": [{"A": 1, "B": 2}]}


def test_preview_and_import_job_read_the_same_sheet_when_another_tab_is_active():
    from apps.admin_api.bulk_import_parsers import xlsx_rows
    from apps.admin_api.models import BulkImportJob
    from apps.inventory.models import InventoryProduct

    workbook = openpyxl.Workbook()
    first = workbook.active
    first.title = "Stock"
    for row in (["Item", "Total", "Available"], ["Bench Vise", 2, 2]):
        first.append(row)
    second = workbook.create_sheet("Notes")
    for row in (["Wrong", "Header"], ["Not an item", 9]):
        second.append(row)
    workbook.active = 1  # saved with the second tab selected
    buffer = io.BytesIO()
    workbook.save(buffer)
    data = buffer.getvalue()
    assert openpyxl.load_workbook(io.BytesIO(data)).active.title == "Notes"

    assert xlsx_rows(data) == [{"Item": "Bench Vise", "Total": 2, "Available": 2}]

    space = make_space("sheet-active-tab")
    manager = make_member("sheet-active-tab-manager", space)
    preview = post(manager, space, data)
    assert preview.status_code == 200
    assert list(preview.json()["rows"][0]) == ["Item", "Total", "Available"]

    job = authenticated_client(manager).post(
        f"/api/v1/admin/makerspace/{space.id}/inventory/import/jobs",
        {
            "mode": "apply",
            "file": upload(data),
            "mapping": '{"name":"Item","total_quantity":"Total","available_quantity":"Available"}',
        },
        format="multipart",
    )
    assert job.status_code == 201, job.data
    assert job.data["status"] == BulkImportJob.Status.COMPLETED
    assert job.data["created_count"] == 1
    assert InventoryProduct.objects.get(makerspace=space, name="Bench Vise").total_quantity == 2
