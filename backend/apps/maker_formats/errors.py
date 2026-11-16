class FormatError(ValueError):
    """Safe public error: no filenames, keys, file bytes or provider text."""

    def __init__(self, code="invalid_format", status=400):
        self.code, self.status = code, status
        super().__init__(code)
