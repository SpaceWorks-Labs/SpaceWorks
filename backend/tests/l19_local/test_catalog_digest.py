def test_catalog_digest_unchanged():
    from apps.tenant_migration.tenant_dump_catalog import CATALOG_SCHEMA_SHA256, schema_digest
    assert schema_digest() == CATALOG_SCHEMA_SHA256
