"""Backup build errors, importable without the Django app registry.

The root producer-capability installer runs this package's marker code in a bare
`python` container with no settings module, so the error type cannot live beside models.
"""


class BackupBuildError(RuntimeError):
    pass
