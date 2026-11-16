"""Guard: client-visible backend text must go through gettext (owner rule 261).

The scanner is plain AST / regex analysis (no Django needed). It flags text that reaches a client
or a recipient as an untranslated string literal, f-string, ``"..." % x`` or ``"...".format()``:

* DRF / Django exceptions raised with a message (``ValidationError``, ``PermissionDenied`` ...);
* every custom exception class that (transitively) subclasses one of those, plus the programme
  helpers (``ProgrammeError``, ``fail``, ``invalid``);
* ``Response({"detail": "..."})`` bodies;
* notification / email / SMS / push / chat calls (``subject``, ``title``, ``body``, ``text`` ...)
  and the ``subject``/``body``/``text`` dicts built in notification modules;
* a local or module variable assigned such a literal and then passed as one of the above;
* Django templates under ``templates/`` and ``apps/*/templates/``: visible text outside
  ``{% translate %}`` / ``{% blocktranslate %}``.

Code-like tokens (``snake_case`` machine codes) are not prose and are ignored. Log lines,
management commands, tests, migrations and OpenAPI ``summary`` strings are internal and skipped.
"""

import ast
import re
from html.parser import HTMLParser
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]
APPS = BACKEND / "apps"

# callee name -> index of the positional message argument (None = scan all positional args).
EXC_NAMES = {
    "ValidationError": None, "PermissionDenied": 0, "NotFound": 0, "APIException": 0,
    "ParseError": 0, "AuthenticationFailed": 0, "NotAuthenticated": 0, "MethodNotAllowed": 1,
    "NotAcceptable": 0, "UnsupportedMediaType": 1, "Throttled": 1,
}
API_ROOTS = {"APIException", "ValidationError", "PermissionDenied", "NotFound", "ParseError"}
# callee name -> (positional index, keyword) for the programme-style helpers.
HELPERS = {"ProgrammeError": (1, "detail"), "fail": (1, "detail"), "invalid": (0, "detail")}
HELPER_PATHS = ("events/",)  # fail()/invalid() mean something else outside the events programme.
GETTEXT = {
    "gettext", "gettext_lazy", "_", "ngettext", "ngettext_lazy", "pgettext", "pgettext_lazy",
    "format_lazy", "gettext_noop", "mark_safe_lazy",
}
CODE_LIKE = re.compile(r"^[a-z0-9_.:\-/]+$")
MESSAGE_KEYS = {"detail", "message", "error", "reason"}
NOTIFY_CALL = re.compile(
    r"send_mail|EmailMessage|EmailMultiAlternatives|emit|notify|notification|send_sms|send_push|dispatch_|broadcast|alert",
    re.I)
NOTIFY_KWARGS = {"subject", "title", "body", "text", "message", "text_body", "html_body", "preview", "heading"}
NOTIFY_DICT_KEYS = {"subject", "title", "body", "text", "preview", "heading", "text_body", "html_body"}
NOTIFY_PATH = re.compile(
    r"(notif|email|reminder|notice|notify|alert|sms|push|chat|broadcast|digest|mail|schedule_mail|trials|lifecycle)")
FANOUT_CALLS = {"fanout", "queue_rooms", "emit", "emit_notification"}
FANOUT_KWARGS = {"staff", "own", "rendered", "staff_body", "owner_body"}
SKIP_PARTS = {"migrations", "tests", "management"}

# (relative path, callee) -> reason. Keep empty unless genuinely needed.
ALLOW = {}


def _callee(node):
    f = node.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


def _translated(node):
    if isinstance(node, ast.Call):
        name = _callee(node)
        if name in GETTEXT:
            return True
        if name == "format" and isinstance(node.func, ast.Attribute):
            return _translated(node.func.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _translated(node.left)
    return False


def _prose(text):
    text = text.strip()
    return bool(text) and not CODE_LIKE.match(text) and any(c.isalpha() for c in text)


def _untranslated_literal(node):
    """True when ``node`` is inline prose that was never routed through gettext."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _prose(node.value)
    if isinstance(node, ast.JoinedStr):  # an f-string is prose only if a literal part is a phrase
        return any(
            isinstance(v, ast.Constant) and " " in v.value and any(c.isalpha() for c in v.value)
            for v in node.values
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _untranslated_literal(node.left)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _untranslated_literal(node.left) or _untranslated_literal(node.right)
    if isinstance(node, ast.Call) and _callee(node) == "format" and isinstance(node.func, ast.Attribute):
        return _untranslated_literal(node.func.value)
    return False


def _bad_in(node, field_dict, resolve, keys=MESSAGE_KEYS):
    """Yield every offending message expression inside ``node`` (descends dicts/lists/tuples).

    ``field_dict`` is True when every dict value is a message (``ValidationError``); otherwise only
    the ``detail``/``message`` style keys are prose. ``resolve`` maps a variable name to the prose
    literal assigned to it (best effort), so a message built into a variable first is still caught.
    """
    if node is None or _translated(node):
        return
    if isinstance(node, ast.Name):
        target = resolve(node.id)
        if target is not None:
            yield target
    elif isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if field_dict or (isinstance(k, ast.Constant) and k.value in keys):
                yield from _bad_in(v, field_dict, resolve, keys)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for v in node.elts:
            yield from _bad_in(v, field_dict, resolve, keys)
    elif _untranslated_literal(node):
        yield node


def _api_subclasses():
    """Names of classes in ``apps/`` whose every definition (transitively) subclasses an API error.

    Requiring every definition keeps a same-named plain ``Exception`` elsewhere from being swept in.
    """
    defs = {}
    for path in APPS.rglob("*.py"):
        if SKIP_PARTS & set(path.relative_to(APPS).parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef):
                defs.setdefault(n.name, []).append({
                    b.id if isinstance(b, ast.Name) else b.attr for b in n.bases
                    if isinstance(b, (ast.Name, ast.Attribute))})
    found, changed = set(), True
    while changed:
        changed = False
        for name, variants in defs.items():
            if name not in found and all(v & (API_ROOTS | found) for v in variants):
                found.add(name)
                changed = True
    return found - API_ROOTS


def _candidates(node, rel, subclasses):
    """Return ``(callee, [message expressions], field_dict)`` for a call, or ``None``."""
    name = _callee(node)
    kws = lambda keys: [k.value for k in node.keywords if k.arg in keys]  # noqa: E731
    if name in EXC_NAMES:
        idx = EXC_NAMES[name]
        args = node.args if idx is None else node.args[idx:idx + 1]
        return name, list(args) + kws({"detail", "message"}), name == "ValidationError"
    if name in HELPERS and rel.startswith(HELPER_PATHS):
        idx, kw = HELPERS[name]
        return name, node.args[idx:idx + 1] + kws({kw}), False
    if name in subclasses:
        return name, list(node.args) + kws({"detail", "message"}), True
    if name == "Response" and node.args and isinstance(node.args[0], ast.Dict):
        d = node.args[0]
        return name, [v for k, v in zip(d.keys, d.values)
                      if isinstance(k, ast.Constant) and k.value in MESSAGE_KEYS], False
    if name in FANOUT_CALLS:
        return name, kws(FANOUT_KWARGS), "notification"
    if name and NOTIFY_CALL.search(name):
        return name, kws(NOTIFY_KWARGS), False
    return None


def _assignments(scope):
    """Names assigned exactly once, directly in ``scope``, to an untranslated prose literal."""
    seen, literal = {}, {}
    body = scope.body if hasattr(scope, "body") else []
    stack = list(body)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            nm = n.targets[0].id
            seen[nm] = seen.get(nm, 0) + 1
            if _untranslated_literal(n.value):
                literal[nm] = n.value
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)) and isinstance(n.target, ast.Name):
            seen[n.target.id] = seen.get(n.target.id, 0) + 2
        for child in ast.iter_child_nodes(n):
            if isinstance(child, ast.stmt):
                stack.append(child)
    return {k: v for k, v in literal.items() if seen.get(k) == 1}


def _scan_tree(tree, rel, subclasses):
    module_literals = _assignments(tree)
    owner = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            local = _assignments(fn)
            for n in ast.walk(fn):
                owner[id(n)] = local
    notify_module = bool(NOTIFY_PATH.search(rel)) and not rel.rsplit("/", 1)[-1].startswith("views")
    for node in ast.walk(tree):
        local = owner.get(id(node), {})
        resolve = lambda nm: local.get(nm) or (module_literals.get(nm) if nm not in local else None)  # noqa: E731
        if isinstance(node, ast.Call):
            got = _candidates(node, rel, subclasses)
            if got:
                name, cands, field_dict = got
                for c in cands:
                    keys = NOTIFY_DICT_KEYS if field_dict == "notification" else MESSAGE_KEYS
                    for bad in _bad_in(c, field_dict is True, resolve, keys):
                        yield name, bad
        elif isinstance(node, ast.Dict) and notify_module:
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value in NOTIFY_DICT_KEYS:
                    for bad in _bad_in(v, False, resolve):
                        yield "notification-dict", bad


def scan_nodes():
    """Yield ``(rel, path, callee, ast_node)`` for every untranslated client message in apps/."""
    subclasses = _api_subclasses()
    found = []
    for path in sorted(APPS.rglob("*.py")):
        rel = path.relative_to(APPS).as_posix()
        if SKIP_PARTS & set(rel.split("/")) or rel.rsplit("/", 1)[-1].startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        seen = set()
        for name, bad in _scan_tree(tree, rel, subclasses):
            key = (bad.lineno, bad.col_offset)
            if key in seen or (rel, name) in ALLOW:
                continue
            seen.add(key)
            found.append((rel, path, name, bad))
    return found


def scan():
    """Return ``[(relative_path, line, callee)]`` for every untranslated client message."""
    return [(rel, node.lineno, name) for rel, _path, name, node in scan_nodes()]


# ---- Django templates -------------------------------------------------------------------------

BLOCK = re.compile(r"\{%\s*blocktrans(?:late)?\b.*?%\}.*?\{%\s*endblocktrans(?:late)?\s*%\}", re.S)
COMMENT = re.compile(r"\{%\s*comment\b.*?%\}.*?\{%\s*endcomment\s*%\}|\{#.*?#\}", re.S)
TRANS = re.compile(r"\{%\s*trans(?:late)?\b.*?%\}", re.S)
TAGS = re.compile(r"\{%.*?%\}|\{\{.*?\}\}", re.S)
VISIBLE_ATTRS = {"alt", "title", "placeholder", "aria-label", "label"}
TEXT_ALLOW = {"Space Works", "SpaceWorks"}  # the product name is a proper noun, not a sentence


class _Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hits, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        for key, value in attrs:
            if key in VISIBLE_ATTRS and value and re.search(r"[A-Za-z]{2}", value) and value not in TEXT_ALLOW:
                self.hits.append((self.getpos()[0], f"{key}={value}"))

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        text = " ".join(data.split())
        if not self.skip and re.search(r"[A-Za-z]{2}", text) and text not in TEXT_ALLOW:
            self.hits.append((self.getpos()[0], text))


def scan_template_text(text, html=True):
    """Visible text left outside translate tags: ``[(line, text)]``."""
    text = TRANS.sub("", BLOCK.sub("", COMMENT.sub("", text)))
    text = TAGS.sub(" ", text)
    if not html:
        return [(i + 1, ln.strip()) for i, ln in enumerate(text.splitlines()) if re.search(r"[A-Za-z]{2}", ln)]
    parser = _Visible()
    parser.feed(text)
    return parser.hits


def scan_templates():
    roots = [BACKEND / "templates", *APPS.glob("*/templates")]
    found = []
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.suffix not in (".html", ".txt"):
                continue
            for line, text in scan_template_text(path.read_text(encoding="utf-8"), path.suffix == ".html"):
                found.append((path.relative_to(BACKEND).as_posix(), line, text))
    return found


# ---- tests ------------------------------------------------------------------------------------

def test_client_visible_backend_messages_are_translatable():
    found = scan()
    report = "\n".join(f"{rel}:{line} {name}(...)" for rel, line, name in found)
    assert not found, (
        "Untranslated client-visible text; wrap in gettext()/gettext_lazy() with %(name)s "
        "placeholders:\n" + report
    )


def test_templates_have_no_untranslated_visible_text():
    found = scan_templates()
    report = "\n".join(f"{rel}:{line} {text[:80]!r}" for rel, line, text in found)
    assert not found, "Visible template text outside {% translate %}/{% blocktranslate %}:\n" + report


def test_scanner_catches_the_patterns_it_exists_for():
    """The guard must not go blind: each pattern below has to be reported."""
    sample = (
        "from rest_framework.exceptions import ValidationError, APIException\n"
        "class Refused(APIException):\n    pass\n"
        "def a():\n    raise ValidationError('Nope, not allowed.')\n"
        "def b(x):\n    raise ValidationError(f'{x} is not allowed.')\n"
        "def c():\n    msg = 'This is wrong.'\n    raise ValidationError(msg)\n"
        "def d():\n    raise Refused('bad', 'You may not do that.')\n"
        "def e():\n    send_mail(subject='Hello there', body='A notice.')\n"
    )
    hits = list(_scan_tree(ast.parse(sample), "demo.py", {"Refused"}))
    assert len(hits) == 6, hits
    ok = "def a():\n    raise ValidationError(gettext('Nope, not allowed.'))\n"
    assert not list(_scan_tree(ast.parse(ok), "demo.py", set()))
    assert scan_template_text("<p>Hello</p>{% translate 'x' %}")
    assert not scan_template_text("{% blocktranslate %}Hello {{ a }}{% endblocktranslate %}<p>{{ a }}</p>")


def test_submission_error_codes_all_have_text():
    """Every SubmissionError code raised in apps/ must have translated text (or be a known fallback)."""
    from apps.events.submissions.errors_text import SUBMISSION_ERROR_TEXT, submission_error_text

    codes = set()
    for path in APPS.rglob("*.py"):
        if "migrations" in path.parts or "tests" in path.parts:
            continue
        for m in re.finditer(r'SubmissionError\(\s*"([a-z_0-9]+)"', path.read_text(encoding="utf-8")):
            codes.add(m.group(1))
    missing = sorted(c for c in codes if c not in SUBMISSION_ERROR_TEXT)
    assert not missing, f"SubmissionError codes without translated text: {missing}"
    assert str(submission_error_text("not_found"))
