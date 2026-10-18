"""Query-free retained provider declarations for G's lifecycle registries."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StageRetentionProvider:
    key: str = "events.stage_files"
    retained_models: tuple = ("events.StageFormAsset", "events.StageFileCleanup")

    def sweep(self, *, limit=100):
        from .retention import sweep
        return sweep(limit=limit)

    def collect_keys(self, makerspace, add):
        from .object_capture import collect_keys
        return collect_keys(makerspace, add)

    def preflight(self, **kwargs):
        from .purge import preflight
        return preflight(**kwargs)

    def purge_locked(self, **kwargs):
        from .purge import delete_locked
        return delete_locked(**kwargs)

    def after_import_locked(self, assets):
        from .retention import register_imported_locked
        return register_imported_locked(assets)


STAGE_RETENTION_PROVIDER = StageRetentionProvider()
