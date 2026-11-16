"""AST call graph and path ordering for the fundraising switch fence.

Resolve local/import aliases; inspect calls in evaluation order, including call
arguments before the called fence. A gate in one branch cannot bless another.
Model persistence hooks are sinks, not application entry points.
"""

import ast
from functools import lru_cache
from pathlib import Path

PACKAGE = "apps.payments.donations"
ROOT = Path(__file__).resolve().parents[2] / "apps" / "payments" / "donations"
FENCE = PACKAGE + ".gates.require_fundraising_locked"
CONTEXT = PACKAGE + ".gates.donation_write"
DISPATCH = "apps.operations.notifications_p2.safe_notification"
NOTICE_FENCE = PACKAGE + ".notices._fundraising_notification"
NOTICE_WRAPPER = NOTICE_FENCE + "._decorate._guarded"
ORM = {"save", "delete", "create", "get_or_create", "update_or_create", "bulk_create", "bulk_update"}
EFFECTS = {
    "consume_code", "issue_code", "get_or_create_anonymous_requester", "create_payment", "create_checkout_url",
    "record", "record_change", "record_case", "submit_claim", "confirm_claim", "reject_claim", "cancel_pending",
    "reconcile_payments", "fanout", "direct_mail_unless_routed", "presigned_upload", "finalize_upload",
    "delete_object", "release_public_image_on_commit", "charge_upload", "check_upload_headroom", "_notify",
    "safe_notification", "unclassified_callable",
}
PURE_UPDATES = {
    (PACKAGE + ".serializers_staff.DonationSettingsSerializer.validate", "data.update"),
    (PACKAGE + ".views_staff_area.donors", "row.update"),
}


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return dotted(node.value) + "." + node.attr
    return ""


@lru_cache(maxsize=1)
def inventory():
    functions, imports = {}, {}
    for path in sorted(ROOT.rglob("*.py")):
        if path.name.startswith("models"):
            continue
        module = PACKAGE + "." + ".".join(path.relative_to(ROOT).with_suffix("").parts)
        module = module.removesuffix(".__init__")
        package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                base = ".".join(package.split(".")[:len(package.split(".")) - node.level + 1]) if node.level else ""
                prefix = ".".join(part for part in (base, node.module) if part)
                for item in node.names:
                    aliases[item.asname or item.name] = prefix + "." + item.name
            elif isinstance(node, ast.Import):
                for item in node.names:
                    aliases[item.asname or item.name.split(".")[0]] = (
                        item.name if item.asname else item.name.split(".")[0])
        aliases["<bindings>"] = tree.body  # Retain module assignments without importing/executing source.
        imports[module] = aliases

        def visit(nodes, parent=module):
            for node in nodes:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = parent + "." + node.name
                    if not isinstance(node, ast.ClassDef):
                        functions[name] = (module, node)
                    visit(node.body, name)
        visit(tree.body)
    return functions, imports


def resolve(name, value, functions, imports):
    module = functions[name][0]
    first, *tail = value.split(".")
    if first in imports[module]:
        return ".".join([imports[module][first], *tail])
    parent = name.rsplit(".", 1)[0]
    return parent + "." + value if parent + "." + value in functions else module + "." + value


def effect(node, name="", target=None):
    value = dotted(node.func)
    leaf = (target or value).rsplit(".", 1)[-1]
    # Only two reviewed dictionary updates; an assigned QuerySet still counts.
    return leaf in ORM | EFFECTS or leaf == "update" and (name, value) not in PURE_UPDATES


def call_targets(name, value, functions, imports):
    """Resolve module/default/local bindings; union branches so rebinding cannot hide a sink."""
    aliases = {}
    direct = "." not in value

    def bind(target, source):
        if isinstance(target, ast.Name):
            aliases.setdefault(target.id, set()).add(source or "unclassified_callable")
        elif isinstance(target, (ast.Tuple, ast.List)):
            for child in target.elts:
                bind(child, "")  # Destructured callable values fail closed until classified.
        elif isinstance(target, ast.Starred):
            bind(target.value, "")

    def collect(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            source = dotted(node.value)
            for target in targets:
                bind(target, source)
        for child in ast.iter_child_nodes(node):
            collect(child)

    def expand(value, seen=frozenset()):
        first, *tail = value.split(".")
        if first in seen:
            return {"unclassified_callable"}
        if value.startswith("apps."):  # Already resolved default targets retain their defining scope.
            return {value}
        if first not in aliases:
            target = resolve(name, value, functions, imports)
            if (seen and direct and first not in imports[functions[name][0]] and target not in functions
                    and target.rsplit(".", 1)[-1] not in ORM | EFFECTS):
                return {"unclassified_callable"}
            return {target}
        return set().union(*(expand(".".join([source, *tail]), seen | {first}) for source in aliases[first]))

    for statement in imports[functions[name][0]].get("<bindings>", ()):
        collect(statement)
    node = functions[name][1]
    parameters = [*node.args.posonlyargs, *node.args.args]
    defaults = list(zip(parameters[-len(node.args.defaults):], node.args.defaults))
    defaults += [(arg, default) for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
                 if default is not None]
    # Defaults evaluate in the defining scope, before parameter/local rebindings.
    bound = {arg.arg: expand(dotted(default) or "unclassified_callable", frozenset({"<default>"}))
             for arg, default in defaults}
    aliases.update(bound)
    for statement in node.body:
        collect(statement)
    if name == NOTICE_WRAPPER:
        aliases["function"] = {DISPATCH}  # The outer decorator receives safe_notification's callable.

    return expand(value)


def service_entries(functions=None, imports=None):
    """Discover every public service/job that transitively reaches an effect."""
    if functions is None:
        functions, imports = inventory()

    def reaches(name, seen=frozenset()):
        if name in seen:
            return False
        node = functions[name][1]
        if any(resolve(name, dotted(decorator), functions, imports) == DISPATCH for decorator in node.decorator_list):
            return True
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            for target in call_targets(name, dotted(call.func), functions, imports):
                if target in {FENCE, CONTEXT}:
                    continue
                if target in functions:
                    if reaches(target, seen | {name}):
                        return True
                elif effect(call, name, target):
                    return True
        return False

    return {name for name in functions if not name.removeprefix(PACKAGE + ".").startswith((
        "views_", "serializers_", "models", "gates."))
        and (not name.rsplit(".", 1)[-1].startswith("_") or any(
            "shared_task" in ast.unparse(decorator) for decorator in functions[name][1].decorator_list))
        and reaches(name)}


def violations(entry, functions=None, imports=None):
    if functions is None:
        functions, imports = inventory()
    errors = []

    def check(name, fenced, stack):
        if name in stack:
            return
        # safe_notification may persist a job BEFORE the registered body runs.
        # Only core settled receipts are exempt. Inspect the real outer wrapper,
        # treating its function parameter as the effectful deferred dispatcher.
        node = functions[name][1]
        decorators = [resolve(name, dotted(item.func if isinstance(item, ast.Call) else item), functions, imports)
                      for item in node.decorator_list]
        if DISPATCH in decorators and name != PACKAGE + ".notices.notify_receipt":
            if NOTICE_FENCE not in decorators or decorators.index(NOTICE_FENCE) > decorators.index(DISPATCH):
                if not fenced:
                    errors.append((name, node.lineno, "safe_notification"))
            else:
                check(NOTICE_WRAPPER, fenced, stack | {name})

        def expression(node, admitted):
            if node is None:
                return admitted
            if isinstance(node, ast.BoolOp):
                first = expression(node.values[0], admitted)
                for child in node.values[1:]:
                    expression(child, first)
                return first  # Later operands may never execute.
            if isinstance(node, ast.IfExp):
                admitted = expression(node.test, admitted)
                yes = expression(node.body, admitted)
                no = expression(node.orelse, admitted)
                return yes and no
            if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
                for child in ast.iter_child_nodes(node):
                    expression(child, admitted)
                return admitted  # Zero iterations cannot establish a gate.
            if isinstance(node, ast.Call):
                # Python evaluates nested arguments BEFORE invoking the callee.
                for child in [node.func, *node.args, *(kw.value for kw in node.keywords)]:
                    admitted = expression(child, admitted)
                targets = call_targets(name, dotted(node.func), functions, imports)
                if targets == {FENCE}:
                    return True
                for target in sorted(targets):
                    if target in functions and target not in {CONTEXT, FENCE}:
                        check(target, admitted, stack | {name})
                    elif effect(node, name, target) and not admitted:
                        errors.append((name, node.lineno, dotted(node.func)))
                return admitted
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return admitted
            for child in ast.iter_child_nodes(node):
                admitted = expression(child, admitted)
            return admitted

        def block(nodes, admitted):
            for node in nodes:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if isinstance(node, ast.With):
                    inside = admitted
                    for item in node.items:
                        inside = expression(item.context_expr, inside)
                        if isinstance(item.context_expr, ast.Call) and call_targets(
                                name, dotted(item.context_expr.func), functions, imports) == {CONTEXT}:
                            inside = True
                    block(node.body, inside)
                elif isinstance(node, ast.If):
                    admitted = expression(node.test, admitted)
                    block(node.body, admitted)
                    block(node.orelse, admitted)
                elif isinstance(node, (ast.For, ast.While)):
                    expression(node.iter if isinstance(node, ast.For) else node.test, admitted)
                    block(node.body, admitted)
                    block(node.orelse, admitted)
                elif isinstance(node, ast.Try):
                    block(node.body, admitted)
                    for handler in node.handlers:
                        block(handler.body, admitted)
                    block(node.orelse, admitted)
                    block(node.finalbody, admitted)
                else:
                    admitted = expression(node, admitted)
            return admitted

        block(functions[name][1].body, fenced)

    check(entry, False, frozenset())
    return errors
