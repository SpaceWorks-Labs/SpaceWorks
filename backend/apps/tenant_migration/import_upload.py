"""Stream import ciphertext straight into its private, persistent staging file."""

from django.utils.translation import gettext
import logging
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.core.files.uploadhandler import FileUploadHandler
from rest_framework.exceptions import ValidationError

from . import import_staging

logger = logging.getLogger(__name__)


class PersistedImportUpload(UploadedFile):
    def __init__(self, *, persisted_path, **kwargs):
        super().__init__(**kwargs)
        self.persisted_path = persisted_path


class ImportArchiveUploadHandler(FileUploadHandler):
    def __init__(self, request=None):
        super().__init__(request)
        self.created_paths = set()
        self.transferred_paths = set()
        self.output = None
        self.path = None
        self.total = 0
        self.archive_seen = False

    def new_file(self, *args, **kwargs):
        try:
            super().new_file(*args, **kwargs)
            if self.field_name != "archive" or self.archive_seen:
                raise ValidationError({"archive": [gettext("Upload exactly one archive file part.")]})
            self.archive_seen = True
            root = Path(settings.BACKUP_OPS_DIR, "tenant-imports")
            if settings.SPACEWORKS_DEPLOYMENT_MODE == "managed":
                import tempfile
                root = Path(tempfile.gettempdir(), "spaceworks-import-uploads")
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.path = root / f"{uuid4()}.tar.age"
            self.output = self.path.open("xb")
            self.created_paths.add(self.path)
            self.path.chmod(0o600)
        except Exception:
            self.cleanup()
            raise

    def receive_data_chunk(self, raw_data, start):
        try:
            self.total += len(raw_data)
            if self.total > import_staging.MAX_ARCHIVE_BYTES:
                raise ValidationError({"archive": [gettext("The encrypted migration archive is too large.")]})
            self.output.write(raw_data)
        except Exception:
            self.cleanup()
            raise
        return None

    def file_complete(self, file_size):
        try:
            self.output.flush()
            self.output.close()
            upload = PersistedImportUpload(
                file=self.output,
                persisted_path=self.path, name=self.file_name,
                content_type=self.content_type, size=self.total,
                charset=self.charset, content_type_extra=self.content_type_extra,
            )
            self.output = None
            return upload
        except Exception:
            self.cleanup()
            raise

    def upload_interrupted(self):
        self.cleanup()

    def cleanup(self):
        try:
            if self.output is not None:
                self.output.close()
        finally:
            self.output = None
            for path in self.created_paths - self.transferred_paths:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.exception(
                        "tenant_import_upload_unlink_failed",
                        extra={"archive_path": str(path)},
                    )
