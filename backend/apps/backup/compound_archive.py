"""Deployment capture: one platform-readable main component, verified before sealing.

Every makerspace is readable by the superadmin platform key (owner decision #110),
so a deployment archive has exactly one component. The readable-main projection
still removes operational rows and is restored into a fresh verification database
before packaging; there are no sovereign slices, reservations or delayed merges.
"""

from pathlib import Path
import shutil
import uuid

from django.db import connection

from apps.backup.build_errors import BackupBuildError
from apps.backup.digests import sha256_file
from apps.backup.main_projection import project_readable_main_dump
from apps.backup.main_projection_registry import table_rules
from apps.backup.main_projection_verification import build_expected_ledger
from apps.backup.models import BackupArtifactLedger, PlatformBackupSettings
from apps.backup.object_ownership import MAIN_COMPONENT
from apps.backup.physical_catalog import catalog_digest, physical_catalog_ledger
from apps.makerspaces.models import Makerspace


class CompoundCapture:
    def __init__(self, *, archive, root, modes, platform_recipients):
        from .cloud_operations import require_host
        require_host("deployment_backup_requires_host_supervisor")
        self.archive = archive
        self.capture_id = uuid.uuid4()
        self.root = Path(root)
        self.modes = modes
        self.platform_recipients = frozenset(
            entry["public_recipient"] for entry in platform_recipients
        )
        self.prepared = False
        self.expected_main_ledger = None
        self.source_catalog_digest = ""
        self.source_dump_sha256 = ""
        self.source_database_identity = ""
        self.source_server_identity = ""
        self.object_plan = None
        self.population_ids = ()
        self.predecessor_snapshot = {}

    def prepare_from_snapshot(self):
        if self.prepared:
            raise BackupBuildError("Compound capture was prepared more than once.")
        self.prepared = True
        self.population_ids = tuple(
            Makerspace.objects.order_by("pk").values_list("pk", flat=True)
        )
        self.predecessor_snapshot = predecessor_snapshot()
        self.source_dump_sha256 = sha256_file(self.root / "database.dump")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_database(), current_setting('server_version_num'), "
                "(pg_catalog.pg_control_system()).system_identifier"
            )
            database_name, version, system_identifier = cursor.fetchone()
        self.source_database_identity = database_name
        self.source_server_identity = f"postgresql:{version}:{system_identifier}"
        self.source_catalog_digest = catalog_digest(physical_catalog_ledger("default"))
        self.expected_main_ledger = build_expected_ledger(
            "default", table_rules(), (), sequence_facts=()
        )

    def capture_from_snapshot(self, *, object_plan):
        if self.expected_main_ledger is None:
            raise BackupBuildError("Compound capture was not prepared in the snapshot.")
        object_plan.assert_complete()
        self.object_plan = object_plan

    def promotion_snapshot(self):
        return {
            **self.predecessor_snapshot,
            "retained": [{"makerspace_id": value} for value in self.population_ids],
        }

    def project_readable_main(self, manifest):
        if self.expected_main_ledger is None:
            raise BackupBuildError("Readable-main verification ledger is missing.")
        build_root = self.root / ".main-build"
        source_dump = build_root / "source.dump"
        build_root.mkdir()
        (self.root / "database.dump").replace(source_dump)
        try:
            project_readable_main_dump(
                source_dump,
                self.root / "database.dump",
                (),
                self.expected_main_ledger,
            )
            if self.object_plan is None:
                raise BackupBuildError("Compound object ownership proof is missing.")
            self.object_plan.verify_component(
                MAIN_COMPONENT, manifest["storage"]["objects"]
            )
            result = dict(manifest)
        finally:
            shutil.rmtree(build_root, ignore_errors=True)
        result["covered_makerspace_ids"] = list(self.population_ids)
        result["excluded_makerspace_ids"] = []
        result["partial"] = False
        return result


def predecessor_snapshot():
    predecessor = BackupArtifactLedger.objects.filter(
        state=BackupArtifactLedger.State.AVAILABLE
    ).order_by("-promoted_at", "-created_at").first()
    last_success_at = PlatformBackupSettings.objects.filter(pk=1).values_list(
        "last_success_at", flat=True
    ).first()
    return {
        "predecessor_artifact_id": str(predecessor.artifact_id) if predecessor else None,
        "predecessor_success_at": last_success_at.isoformat() if last_success_at else None,
    }
