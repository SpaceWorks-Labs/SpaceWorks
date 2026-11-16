"""The backend literal guard (scripts/check_i18n_literals.py): fixtures plus the live tree."""
import importlib.util
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("check_i18n_literals", BACKEND / "scripts/check_i18n_literals.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _found(source, rel="apps/x/views.py"):
    return [(node.lineno, category) for node, category, _ in guard.scan_source(textwrap.dedent(source), rel)]


def test_unmarked_eligible_literals_fail():
    source = '''
    from django.db import models
    from rest_framework.exceptions import ValidationError
    from rest_framework.response import Response

    class Status(models.TextChoices):
        OPEN = "open", "Open for requests"

    class Thing(models.Model):
        name = models.CharField(max_length=5, verbose_name="Display name", help_text="Shown to members")

    def view(x):
        raise ValidationError({"field": f"Pick {x} again"})

    def other():
        return Response({"detail": "Not allowed here."}, status=403)

    def mail():
        notify_member(subject="Your loan is due", body="Return it soon please.")

    def pdf(canvas):
        canvas.drawString(1, 2, "Certificate of attendance")
    '''
    categories = {category for _line, category in _found(source)}
    assert categories == {"choice_label", "field_label", "exception", "detail", "email", "notification", "reportlab"}


def test_marked_codes_and_ignored_literals_pass():
    source = '''
    from django.utils.translation import gettext, gettext_lazy
    from rest_framework.exceptions import ValidationError

    class Status(models.TextChoices):
        OPEN = "open", gettext_lazy("Open")

    def view(x):
        raise ValidationError(gettext("Pick {x} again").format(x=x))

    def coded():
        raise ValidationError("invalid_token")

    def technical():
        raise ValidationError("Internal invariant broke")  # i18n-ignore: developer-only assertion text
    '''
    assert _found(source) == []


def test_catalogue_positions_only_in_catalogue_files():
    source = 'ENTRIES = (P("a.b", "Something happened"),)\n'
    assert _found(source, "apps/audit/presentation_catalog_demo.py") == [(1, "catalogue")]
    assert _found(source, "apps/audit/other.py") == []


def test_live_tree_has_no_unmarked_literal():
    findings = []
    for path in guard.eligible_files():
        rel = path.relative_to(BACKEND).as_posix()
        findings += [f"{rel}:{node.lineno}" for node, *_ in guard.scan_source(path.read_text(encoding="utf-8"), rel)]
    assert findings == []


def test_mandatory_sources_are_scanned():
    scanned = {path.relative_to(BACKEND).as_posix() for path in guard.eligible_files()}
    for rel in ("apps/backup/middleware.py", "apps/hardware_requests/workflow_errors.py",
                "apps/audit/presentation_catalog_r2_l9.py"):
        assert rel in scanned or not (BACKEND / rel).exists()
