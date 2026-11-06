#!/usr/bin/env python3
"""Backend unmarked-literal guard (phase 8 i18n).

Extraction cannot see a string nobody marked, so this AST pass lists every user-facing
literal in a CONFIGURED position that is not wrapped in ``gettext``/``gettext_lazy``/
``ngettext``/``pgettext``. The positions (``POSITIONS`` below) are the product's output
seams: exception and refusal messages, typed ``detail`` responses, model field labels,
choice labels, notification and email fields, ReportLab text and the display catalogues.

A technical string in one of those positions takes a same-line ``# i18n-ignore: <reason>``
comment. Codes (``snake_case`` tokens with no spaces) are never user-facing prose and are
skipped. Tenant-authored text never reaches a literal. Docs: ``docs/i18n.md``.

Usage (from backend/):  python scripts/check_i18n_literals.py [path ...]
Exit status 1 lists each finding as ``path:line: category``.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
MARKERS = {"gettext", "gettext_lazy", "ngettext", "ngettext_lazy", "pgettext", "pgettext_lazy",
           "npgettext", "npgettext_lazy", "gettext_noop", "_"}
EXCEPTIONS = {"ValidationError", "PermissionDenied", "NotFound", "ParseError", "AuthenticationFailed",
              "NotAuthenticated", "APIException", "MethodNotAllowed", "NotAcceptable",
              "UnsupportedMediaType", "Throttled", "Http404", "SuspiciousOperation", "Refused"}
FIELD_KEYWORDS = {"verbose_name", "verbose_name_plural"}
MODEL_FIELD_KEYWORDS = {"help_text"}
EMAIL_KEYWORDS = {"subject", "text_body", "html_body"}
NOTIFY_KEYWORDS = {"title", "body", "message", "summary", "heading"}
NOTIFY_CALL = re.compile(r"^(emit_|notify|send_|dispatch_|push_|_notify|_emit|_send)|"
                         r"(Notification|Delivery|Email|Message|Push|Alert)$")
DETAIL_CALLS = {"Response", "JsonResponse", "HttpResponseBadRequest"}
REPORTLAB_TEXT = {"drawString": 2, "drawCentredString": 2, "drawRightString": 2, "Paragraph": 0}
# Display catalogues: every ``label``/``description``/``title`` keyword or P(action, label).
CATALOGUE_FILES = re.compile(
    r"(audit/presentation_catalog_[a-z0-9_]+|makerspaces/module_registry[a-z0-9_]*|"
    r"makerspaces/capabilit[a-z0-9_]*|makerspaces/module_groups|operations/report_definitions[a-z0-9_]*)\.py$")
CATALOGUE_KEYWORDS = {"label", "description", "title", "summary"}
CODE = re.compile(r"^[A-Za-z0-9_.:/\-]*$")
SKIPPED_PARTS = {"migrations", "tests", "management"}
IGNORE = "i18n-ignore:"


def _name(func):
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def is_prose(node):
    """A literal worth translating: has a letter and is not a bare code token."""
    if isinstance(node, ast.JoinedStr):
        text = "".join(v.value for v in node.values if isinstance(v, ast.Constant))
        return bool(re.search(r"[A-Za-z]", text)) and " " in text.strip()
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value.strip()
        return bool(re.search(r"[A-Za-z]", value)) and not CODE.match(value)
    return False


def literals(node):
    """The string literal nodes an expression in an output position renders."""
    if isinstance(node, (ast.Constant, ast.JoinedStr)):
        if is_prose(node):
            yield node
    elif isinstance(node, ast.Call):
        if _name(node.func) in MARKERS:
            return
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            yield from literals(node.func.value)
    elif isinstance(node, ast.BinOp):
        yield from literals(node.left)
        if isinstance(node.op, ast.Add):
            yield from literals(node.right)
    elif isinstance(node, ast.IfExp):
        yield from literals(node.body)
        yield from literals(node.orelse)
    elif isinstance(node, ast.BoolOp):
        for value in node.values:
            yield from literals(value)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for element in node.elts:
            yield from literals(element)
    elif isinstance(node, ast.Dict):
        for value in node.values:
            yield from literals(value)


def _detail_values(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Dict):
            for key, value in zip(sub.keys, sub.values):
                if isinstance(key, ast.Constant) and key.value in {"detail", "message"}:
                    yield value


def _call_positions(call, catalogue):
    name = _name(call.func)
    base = call.func.value.id if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) else ""
    if name in EXCEPTIONS:
        if call.args:
            yield "exception", call.args[0]
        for kw in call.keywords:
            if kw.arg in {"detail", "message"}:
                yield "exception", kw.value
    if name in DETAIL_CALLS:
        for arg in call.args[:1]:
            for value in _detail_values(arg):
                yield "detail", value
    if name in REPORTLAB_TEXT and len(call.args) > REPORTLAB_TEXT[name]:
        yield "reportlab", call.args[REPORTLAB_TEXT[name]]
    if catalogue and name == "P" and len(call.args) > 1:
        yield "catalogue", call.args[1]
    for kw in call.keywords:
        if kw.arg in FIELD_KEYWORDS or (kw.arg in MODEL_FIELD_KEYWORDS and base == "models"):
            yield "field_label", kw.value
        elif kw.arg == "error_messages" and isinstance(kw.value, ast.Dict):
            yield "error_messages", kw.value
        elif kw.arg in EMAIL_KEYWORDS:
            yield "email", kw.value
        elif kw.arg in NOTIFY_KEYWORDS and NOTIFY_CALL.search(name):
            yield "notification", kw.value
        elif catalogue and kw.arg in CATALOGUE_KEYWORDS:
            yield "catalogue", kw.value


def _choice_labels(cls):
    if not any(_name(base).endswith("Choices") for base in cls.bases):
        return
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Tuple) and len(stmt.value.elts) >= 2:
            yield "choice_label", stmt.value.elts[-1]


class Finder(ast.NodeVisitor):
    def __init__(self, catalogue):
        self.catalogue, self.depth, self.found = catalogue, 0, []

    def _add(self, category, expr):
        for node in literals(expr):
            self.found.append((node, category, self.depth > 0))

    def visit_FunctionDef(self, node):
        self.depth += 1
        self.generic_visit(node)
        self.depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        self.depth += 1
        self.generic_visit(node)
        self.depth -= 1

    def visit_ClassDef(self, node):
        for category, expr in _choice_labels(node):
            self._add(category, expr)
        self.generic_visit(node)

    def visit_Call(self, node):
        for category, expr in _call_positions(node, self.catalogue):
            self._add(category, expr)
        self.generic_visit(node)


def scan_source(source, relpath):
    """``[(node, category, in_function)]`` for every unmarked, unignored literal."""
    tree = ast.parse(source)
    lines = source.splitlines()
    finder = Finder(bool(CATALOGUE_FILES.search(relpath)))
    finder.visit(tree)
    seen, out = set(), []
    for node, category, in_function in finder.found:
        key = (node.lineno, node.col_offset)
        if key in seen:
            continue
        seen.add(key)
        span = lines[node.lineno - 1: node.end_lineno]
        if any(IGNORE in line for line in span):
            continue
        out.append((node, category, in_function))
    return sorted(out, key=lambda item: (item[0].lineno, item[0].col_offset))


def eligible_files(paths=None):
    roots = [Path(p).resolve() for p in paths] if paths else [BACKEND / "apps"]
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in files:
            parts = set(path.relative_to(BACKEND).parts[:-1])
            if parts & SKIPPED_PARTS or path.name == "admin.py" or path.name.startswith("admin_"):
                continue
            yield path


def main(argv):
    total = 0
    for path in eligible_files(argv[1:]):
        rel = path.relative_to(BACKEND).as_posix()
        for node, category, _in_function in scan_source(path.read_text(encoding="utf-8"), rel):
            print(f"{rel}:{node.lineno}: {category}")
            total += 1
    print(f"{total} unmarked user-facing literal(s)", file=sys.stderr)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
