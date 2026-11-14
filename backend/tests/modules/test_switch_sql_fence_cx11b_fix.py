"""The refusal fence rejects attempts before any statement reaches PostgreSQL."""
from unittest.mock import Mock

import pytest

from tests.modules.test_switch_matrix_objects_rest_support import _no_write


@pytest.mark.parametrize("sql", [
    "SELECT 1; UPDATE inventory_inventoryproduct SET name = name",
    "SELECT 1; DELETE FROM audit_auditlog",
    "SELECT 1; CREATE TABLE forbidden (id integer)",
    "SELECT 1; CREATE OR REPLACE VIEW forbidden AS SELECT 1",
    "SELECT 1; ALTER TABLE audit_auditlog ADD COLUMN forbidden integer",
    "SELECT 1; DROP TABLE audit_auditlog",
    "SELECT 1; TRUNCATE audit_auditlog",
    "/* read */ SELECT 1; INSERT INTO audit_auditlog DEFAULT VALUES",
    "WITH changed AS (DELETE FROM audit_auditlog RETURNING *) SELECT * FROM changed",
    "WITH changed AS (INSERT INTO audit_auditlog DEFAULT VALUES RETURNING *) SELECT * FROM changed",
    "SELECT 1; WITH changed AS (UPDATE inventory_inventoryproduct SET name = name RETURNING *) SELECT * FROM changed",
    "SELECT 1; SELECT ensure_login('forbidden')",
])
def test_fence_rejects_later_writes_and_cte_writes_before_executor(sql):
    execute = Mock()
    with pytest.raises(AssertionError):
        _no_write(execute, sql, None, False, {})
    execute.assert_not_called()


@pytest.mark.parametrize("sql", [
    "SELECT 1; SELECT 2",
    "SELECT * FROM audit_auditlog FOR UPDATE",
    "SELECT * FROM audit_auditlog FOR NO KEY UPDATE",
    "WITH rows AS (SELECT 1) SELECT * FROM rows",
    "SELECT 'UPDATE x; DELETE FROM x' /* DROP TABLE x */",
    'ROLLBACK TO SAVEPOINT "refusal"',
    'SAVEPOINT "refusal"; RELEASE SAVEPOINT "refusal"',
    'ROLLBACK; BEGIN; COMMIT',
])
def test_fence_allows_read_batches_literals_and_row_locks(sql):
    execute = Mock(return_value="read")
    assert _no_write(execute, sql, None, False, {}) == "read"
    execute.assert_called_once_with(sql, None, False, {})
