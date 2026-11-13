"""In-process mutation testing for the backend core (decision 457).

Why a bespoke runner instead of mutmut: the core suites need Django + Postgres + Redis + MinIO, which only exist
inside the isolated runner (`scripts/dev.sh test`). mutmut 3 copies the tree into ``mutants/`` and re-imports it,
which does not compose with that runner or with this repo's conftests. This script does the same job in ONE pytest
process: it runs the selected tests once under coverage (one context per test) to learn which tests execute which
line, then for every mutant swaps the mutated ``__code__`` into the live function objects and runs only the tests
that cover the mutated line, stopping at the first failure. Survivors are the missing conditions.

Scope (same as mutmut): statements inside function bodies. Comparison / boolean / arithmetic operator flips, negated
branch conditions, ``not`` removal, off-by-one numeric constants, bool flips, machine-token string constants
(identifiers / codes, not prose), dropped side-effect call statements, ``return x`` -> ``return None``. Logging calls
are never mutated.

Run inside the test container (see docs/DEV-WORKFLOW.md, "Mutation testing"):
  python scripts/mutation/mutate.py --name workflow --files apps/x/y.py --test-dirs tests/x --test-regex 'regex'
"""
from __future__ import annotations

import argparse
import ast
import gc
import json
import os
import re
import signal
import sys
import time
import types
from dataclasses import dataclass
from pathlib import Path

try:
    import pytest
except ImportError:  # host-side --list-only needs no pytest
    pytest = None

BACKEND = Path(__file__).resolve().parents[2] / "backend"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:\-/]{2,}$")
LOG_NAMES = {"logger", "log", "logging", "LOGGER", "_logger", "_log"}

CMP_SWAP = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In,
}
BIN_SWAP = {
    ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult, ast.FloorDiv: ast.Mult,
    ast.Mod: ast.Mult, ast.BitAnd: ast.BitOr, ast.BitOr: ast.BitAnd,
}


class MutantTimeout(BaseException):
    pass


@dataclass
class Mutant:
    key: str
    file: str
    line: int
    kind: str
    desc: str
    stmt_line: int
    stmt_end: int
    func_lines: tuple
    func_name: str
    edit: tuple  # (container, field, index, new_value, old_value)
    status: str = "pending"
    killed_by: str = ""


def _is_log_call(stmt) -> bool:
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
        return False
    func = stmt.value.func
    while isinstance(func, ast.Attribute):
        func = func.value
    return isinstance(func, ast.Name) and func.id in LOG_NAMES


def _replace_edit(parent, field_name, index, new, old):
    if index is None:
        return (parent, field_name, None, new, old)
    return (getattr(parent, field_name), None, index, new, old)


class Collector:
    def __init__(self, rel: str):
        self.rel = rel
        self.out: list[Mutant] = []

    def add(self, node, kind, desc, edit, ctx):
        line = getattr(node, "lineno", ctx["stmt"].lineno)
        key = f"{self.rel}:{line}:{getattr(node, 'col_offset', 0)}:{kind}:{desc}"
        stmt = ctx["stmt"]
        # Coverage records the physical lines a multi-line statement actually executes, not its first line, so the
        # lookup covers the statement's span (an if/while: its condition only, not its body).
        header = getattr(stmt, "test", None) if isinstance(stmt, (ast.If, ast.While)) else None
        end = getattr(header, "end_lineno", None) or getattr(stmt, "end_lineno", None) or stmt.lineno
        self.out.append(Mutant(key, self.rel, line, kind, desc, stmt.lineno, end, ctx["func_lines"], ctx["func_name"], edit))

    def outer_function(self, fn):
        lines = (fn.lineno,) + tuple(d.lineno for d in fn.decorator_list)
        ctx = {"func_lines": lines, "func_name": fn.name, "stmt": fn}
        self.walk_body(fn.body, ctx, True)

    def walk_body(self, body, ctx, docstring_holder=False):
        for i, stmt in enumerate(body):
            self.walk_stmt(stmt, body, i, ctx, docstring_holder and i == 0)

    def walk_stmt(self, stmt, body, idx, ctx, docstring=False):
        if docstring and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            return
        if _is_log_call(stmt):
            return
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.walk_body(stmt.body, dict(ctx, stmt=stmt), True)
            return
        if isinstance(stmt, ast.ClassDef):
            for sub in stmt.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.walk_body(sub.body, dict(ctx, stmt=sub), True)
            return
        c = dict(ctx, stmt=stmt)
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            self.add(stmt, "stmt_removed", "call statement removed", (body, None, idx, ast.copy_location(ast.Pass(), stmt), stmt), c)
        if isinstance(stmt, ast.Return) and stmt.value is not None and not (
            isinstance(stmt.value, ast.Constant) and stmt.value.value is None
        ):
            self.add(stmt, "return_none", "return value replaced by None", (stmt, "value", None, ast.copy_location(ast.Constant(None), stmt.value), stmt.value), c)
        if isinstance(stmt, (ast.If, ast.While)):
            neg = ast.copy_location(ast.UnaryOp(ast.Not(), stmt.test), stmt.test)
            self.add(stmt, "cond_negated", "branch condition negated", (stmt, "test", None, neg, stmt.test), c)
        for field_name, value in ast.iter_fields(stmt):
            if field_name in ("decorator_list", "returns", "targets", "target", "annotation"):
                continue
            if isinstance(value, ast.expr):
                self.walk_expr(value, stmt, field_name, None, c)
            elif isinstance(value, list):
                for j, v in enumerate(value):
                    if isinstance(v, ast.stmt):
                        self.walk_stmt(v, value, j, ctx)
                    elif isinstance(v, ast.expr):
                        self.walk_expr(v, stmt, field_name, j, c)
                    elif isinstance(v, ast.ExceptHandler):
                        if v.type is not None:
                            self.walk_expr(v.type, v, "type", None, c)
                        self.walk_body(v.body, ctx)
                    elif isinstance(v, ast.withitem):
                        self.walk_expr(v.context_expr, v, "context_expr", None, c)
                    elif isinstance(v, ast.match_case):
                        self.walk_body(v.body, ctx)

    def walk_expr(self, node, parent, field_name, index, c):
        if isinstance(node, ast.Lambda):
            return
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                new = CMP_SWAP.get(type(op))
                if new:
                    self.add(node, "compare", f"{type(op).__name__}->{new.__name__}", (node.ops, None, i, new(), op), c)
        elif isinstance(node, ast.BoolOp):
            new = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            self.add(node, "boolop", f"{type(node.op).__name__}->{type(new).__name__}", (node, "op", None, new, node.op), c)
        elif isinstance(node, ast.BinOp):
            new = BIN_SWAP.get(type(node.op))
            if new:
                self.add(node, "binop", f"{type(node.op).__name__}->{new.__name__}", (node, "op", None, new(), node.op), c)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            self.add(node, "not_removed", "not removed", _replace_edit(parent, field_name, index, node.operand, node), c)
        elif isinstance(node, ast.IfExp):
            neg = ast.copy_location(ast.UnaryOp(ast.Not(), node.test), node.test)
            self.add(node, "cond_negated", "ternary condition negated", (node, "test", None, neg, node.test), c)
        elif isinstance(node, ast.Constant):
            self.constant(node, parent, field_name, index, c)
        if isinstance(node, ast.JoinedStr):
            return
        for fname, value in ast.iter_fields(node):
            if isinstance(value, ast.expr):
                self.walk_expr(value, node, fname, None, c)
            elif isinstance(value, list):
                for j, v in enumerate(value):
                    if isinstance(v, ast.expr):
                        self.walk_expr(v, node, fname, j, c)
                    elif isinstance(v, ast.keyword):
                        self.walk_expr(v.value, v, "value", None, c)
                    elif isinstance(v, ast.comprehension):
                        for fn2, val2 in ast.iter_fields(v):
                            if isinstance(val2, ast.expr):
                                self.walk_expr(val2, v, fn2, None, c)
                            elif isinstance(val2, list):
                                for k, x in enumerate(val2):
                                    if isinstance(x, ast.expr):
                                        self.walk_expr(x, v, fn2, k, c)

    def constant(self, node, parent, field_name, index, c):
        v = node.value
        if isinstance(v, bool):
            new, desc = ast.Constant(not v), f"{v}->{not v}"
        elif isinstance(v, (int, float)):
            new, desc = ast.Constant(v + 1), f"{v}->{v + 1}"
        elif isinstance(v, str) and TOKEN_RE.match(v):
            new, desc = ast.Constant("XX" + v + "XX"), f"'{v[:40]}'->XX"
        else:
            return
        self.add(node, "constant", desc, _replace_edit(parent, field_name, index, ast.copy_location(new, node), node), c)


def apply_edit(edit, new=True):
    container, field_name, index, new_v, old_v = edit
    val = new_v if new else old_v
    if field_name is not None:
        setattr(container, field_name, val)
    else:
        container[index] = val


def enumerate_mutants(rel: str, source: str):
    tree = ast.parse(source)
    col = Collector(rel)

    def visit(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                col.outer_function(node)
            elif isinstance(node, ast.ClassDef):
                visit(node.body)

    visit(tree.body)
    seen: dict = {}
    for m in col.out:
        n = seen.get(m.key, 0)
        seen[m.key] = n + 1
        if n:
            m.key += f"#{n}"
    return tree, col.out


def _code_index(code, out: dict):
    out[(code.co_name, code.co_firstlineno)] = code
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            _code_index(c, out)


class Engine:
    def __init__(self, args):
        self.args = args
        self.items: list = []
        self.baseline_failed: set[str] = set()
        self.durations: dict[str, float] = {}
        self.line_tests: dict[str, dict[int, list[str]]] = {}
        self.results: list[Mutant] = []
        self.mutating = False
        self._mut_failed = None

    @(pytest.hookimpl(tryfirst=True) if pytest else (lambda f: f))
    def pytest_runtestloop(self, session):
        import coverage

        items = list(session.items)
        self.items = items
        self.by_id = {i.nodeid: i for i in items}
        files = [str((BACKEND / f).resolve()) for f in self.args.files]
        mapfile = Path(self.args.out).with_name(f"map-{self.args.name.replace(chr(47), chr(95))}.json")
        cached = {}
        if mapfile.exists() and not self.args.rebuild:
            cached = json.loads(mapfile.read_text())
            self.durations.update(cached["durations"])
            self.baseline_failed.update(cached["failed"])
            self.line_tests = {f: {int(ln): ids for ln, ids in lines.items()} for f, lines in cached["lines"].items()}
            print(f"[mutation] reusing coverage map for {len(cached['durations'])} tests", flush=True)
        todo = [i for i in items if i.nodeid not in self.durations]
        cov = coverage.Coverage(include=files, data_file=None, config_file=False)
        cov.start()
        t0 = time.time()
        for n, item in enumerate(todo):
            nxt = todo[n + 1] if n + 1 < len(todo) else None
            cov.switch_context(item.nodeid)
            s = time.time()
            item.config.hook.pytest_runtest_protocol(item=item, nextitem=nxt)
            self.durations[item.nodeid] = time.time() - s
            self.clean_leaks(item.config)
            if n % 50 == 0:
                print(f"[mutation] baseline {n + 1}/{len(todo)}", flush=True)
            if n and n % 200 == 0:
                self.save_map(mapfile, cov, files)
        cov.stop()
        self.save_map(mapfile, cov, files, final=True)
        slow = sorted(self.durations.items(), key=lambda kv: -kv[1])[:5]
        print("[mutation] slowest baseline tests: " + "; ".join(f"{k} {v:.0f}s" for k, v in slow), flush=True)
        print(f"[mutation] baseline {time.time() - t0:.0f}s, {len(todo)} new tests, {len(self.baseline_failed)} failing in baseline (excluded)", flush=True)
        for nodeid in sorted(self.baseline_failed):
            print(f"[mutation] baseline-failing: {nodeid}", flush=True)
        self.run_mutants()
        return True

    def clean_leaks(self, config):
        """Flush committed rows a leaky test left behind.

        The whole selection runs in ONE process in file order, so a test that commits without cleaning up poisons every
        later test that expects an empty table ("returned 6", "5 == 0"). CI never sees it because shards are small. After
        each test, if a sentinel table holds committed rows, flush (what a transactional test's teardown does).
        """
        try:
            from django.core.management import call_command
            from django.db import connection
            from pytest_django import plugin as pd

            blocker = getattr(pd, "_blocking_manager", None) or config.stash[pd.blocking_manager_key]
            with blocker.unblock():
                with connection.cursor() as cursor:
                    leaked = False
                    for table in ("audit_auditlog", "hardware_requests_hardwarerequest", "accounts_user", "makerspaces_makerspace"):
                        cursor.execute(f"select exists(select 1 from {table} limit 1)")
                        leaked = leaked or cursor.fetchone()[0]
                if leaked:
                    call_command("flush", interactive=False, verbosity=0)
                    self.flushes = getattr(self, "flushes", 0) + 1
        except Exception as exc:  # noqa: BLE001 - never let hygiene break the run
            if not getattr(self, "_leak_warned", False):
                print(f"[mutation] leak guard unavailable: {exc!r}", flush=True)
                self._leak_warned = True

    def save_map(self, mapfile, cov, files, final=False):
        """Merge the contexts recorded so far into the on-disk coverage map (also called mid-baseline)."""
        data = cov.get_data()
        measured = set(data.measured_files())
        for f in files:
            if f in measured:
                merged = self.line_tests.setdefault(f, {})
                for ln, ctxs in data.contexts_by_lineno(f).items():
                    merged[ln] = sorted(set(merged.get(ln, [])) | {c for c in ctxs if c})
        mapfile.parent.mkdir(parents=True, exist_ok=True)
        mapfile.write_text(json.dumps({"durations": self.durations, "failed": sorted(self.baseline_failed), "lines": self.line_tests}))

    def pytest_runtest_logreport(self, report):
        if report.failed:
            if self.mutating:
                self._mut_failed = report.nodeid
            else:
                self.baseline_failed.add(report.nodeid)

    def live_functions(self, filename):
        idx: dict = {}
        for o in gc.get_objects():
            try:
                if isinstance(o, types.FunctionType) and o.__code__.co_filename == filename:
                    idx.setdefault((o.__code__.co_name, o.__code__.co_firstlineno), []).append(o)
            except Exception:
                continue
        return idx

    def run_mutants(self):
        a = self.args
        only = set(json.loads(Path(a.only).read_text())) if a.only else None
        trees, all_mutants = {}, []
        for rel in a.files:
            path = (BACKEND / rel).resolve()
            tree, ms = enumerate_mutants(rel, path.read_text(encoding="utf-8"))
            trees[rel] = (tree, str(path))
            all_mutants.extend(ms)
        if only is not None:
            all_mutants = [m for m in all_mutants if m.key in only]
        if a.shard:
            i, n = (int(x) for x in a.shard.split("/"))
            all_mutants = [m for k, m in enumerate(all_mutants) if k % n == i - 1]
        print(f"[mutation] {len(all_mutants)} mutants to evaluate", flush=True)
        live_cache: dict = {}
        first = self.items[0]
        for mi, m in enumerate(all_mutants):
            tree, abspath = trees[m.file]
            self.evaluate(m, tree, abspath, live_cache, first)
            self.results.append(m)
            print(f"[mutation] {mi + 1}/{len(all_mutants)} {m.status} {m.key} ({self.tally()})", flush=True)
            if mi % 10 == 0:
                self.dump()
        self.dump()
        print(f"[mutation] FINAL {self.tally()}", flush=True)
        for m in self.results:
            if m.status in ("survived", "no_cover", "unpatchable", "uncompilable"):
                print(f"SURVIVOR [{m.status}] {m.key}", flush=True)

    def tally(self):
        c: dict = {}
        for m in self.results:
            c[m.status] = c.get(m.status, 0) + 1
        return ", ".join(f"{k}={v}" for k, v in sorted(c.items()))

    def dump(self):
        out = Path(self.args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(
            [dict(key=m.key, line=m.line, kind=m.kind, desc=m.desc, status=m.status, killed_by=m.killed_by) for m in self.results],
            indent=1,
        ))

    def evaluate(self, m, tree, abspath, live_cache, first):
        lines = self.line_tests.get(abspath, {})
        covering = {t for ln in range(m.stmt_line, m.stmt_end + 1) for t in lines.get(ln, [])}
        tests = [t for t in covering if t not in self.baseline_failed and t in self.by_id]
        if not tests:
            m.status = "no_cover"
            return
        tests.sort(key=lambda t: self.durations.get(t, 0))
        apply_edit(m.edit, True)
        try:
            try:
                code = compile(tree, abspath, "exec", dont_inherit=True)
            except Exception as exc:
                m.status, m.killed_by = "uncompilable", repr(exc)[:200]
                return
            idx: dict = {}
            _code_index(code, idx)
            new_code = next((idx[(m.func_name, ln)] for ln in m.func_lines if (m.func_name, ln) in idx), None)
            if new_code is None:
                m.status = "unpatchable"
                return
            fobjs = None
            for attempt in range(2):
                if abspath not in live_cache or attempt == 1:
                    live_cache[abspath] = self.live_functions(abspath)
                live = live_cache[abspath]
                fobjs = next((live[(m.func_name, ln)] for ln in m.func_lines if (m.func_name, ln) in live), None)
                if fobjs:
                    break
            if not fobjs:
                m.status = "unpatchable"
                return
            originals = [(f, f.__code__) for f in fobjs]
            try:
                for f in fobjs:
                    f.__code__ = new_code
            except ValueError as exc:
                m.status, m.killed_by = "unpatchable", repr(exc)[:200]
                return
            self.mutating = True
            try:
                for nodeid in tests:
                    item = self.by_id[nodeid]
                    budget = min(self.args.max_timeout, max(self.args.min_timeout, 8 * min(self.durations.get(nodeid, 1), 30)))
                    self._mut_failed = None
                    signal.signal(signal.SIGALRM, self._alarm)
                    signal.setitimer(signal.ITIMER_REAL, budget)
                    timed_out = False
                    try:
                        item.ihook.pytest_runtest_protocol(item=item, nextitem=first)
                    except MutantTimeout:
                        timed_out = True
                    finally:
                        signal.setitimer(signal.ITIMER_REAL, 0)
                    self.clean_leaks(item.config)
                    if timed_out or self._mut_failed:
                        m.status, m.killed_by = "killed", nodeid + (" (timeout)" if timed_out else "")
                        return
                m.status = "survived"
            finally:
                self.mutating = False
                for f, c in originals:
                    f.__code__ = c
        finally:
            apply_edit(m.edit, False)

    @staticmethod
    def _alarm(signum, frame):
        raise MutantTimeout()


def select_tests(args) -> list[str]:
    root = BACKEND
    chosen: set[str] = set()
    for d in args.test_dirs:
        p = root / d
        if p.is_file():
            chosen.add(str(p.relative_to(root)).replace("\\", "/"))
        elif p.is_dir():
            chosen.update(str(f.relative_to(root)).replace("\\", "/") for f in p.rglob("test_*.py"))
    if args.test_regex:
        rx = re.compile(args.test_regex)
        for f in (root / "tests").rglob("test_*.py"):
            if "tombstone" in f.parts or (args.exclude_regex and re.search(args.exclude_regex, str(f).replace(chr(92), chr(47)))):
                continue
            try:
                if rx.search(f.read_text(encoding="utf-8", errors="ignore")):
                    chosen.add(str(f.relative_to(root)).replace("\\", "/"))
            except OSError:
                pass
    if args.exclude_regex:
        chosen = {c for c in chosen if not re.search(args.exclude_regex, c)}
    return sorted(chosen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--files", nargs="+", required=True, help="paths relative to backend/")
    ap.add_argument("--test-dirs", nargs="*", default=[])
    ap.add_argument("--test-regex", default="")
    ap.add_argument("--only", default="", help="JSON list of mutant keys to re-evaluate")
    ap.add_argument("--shard", default="", help="i/n")
    ap.add_argument("--out", default="")
    ap.add_argument("--min-timeout", type=float, default=20)
    ap.add_argument("--max-timeout", type=float, default=120)
    ap.add_argument("--exclude-regex", default="", help="test FILES whose path matches are not selected (too slow for a baseline)")
    ap.add_argument("--rebuild", action="store_true", help="ignore the cached coverage map")
    ap.add_argument("--list-only", action="store_true")
    args = ap.parse_args()
    args.out = args.out or str(BACKEND.parent / "mutation-results" / f"{args.name.replace(chr(47), chr(95))}.json")
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    if args.list_only:
        total = 0
        for rel in args.files:
            _, ms = enumerate_mutants(rel, (BACKEND / rel).read_text(encoding="utf-8"))
            print(rel, len(ms))
            total += len(ms)
        print("total", total)
        return 0
    tests = select_tests(args)
    print(f"[mutation] {len(tests)} test files selected", flush=True)
    return pytest.main(["-q", "-p", "no:cacheprovider", *tests], plugins=[Engine(args)])


if __name__ == "__main__":
    sys.exit(main())
