"""Build-time inventory. New routes must be reviewed into the reserved snapshot."""

import ast
import re


def route_segments(root):
    paths = {"/share/profiles/", "/share/pages/", "/share/e/", "/e/", "/sitemap.xml", "/robots.txt", "/favicon.ico", "/assets/"}
    frontend = (root / "frontend/src/AppRoutes.tsx").read_text(encoding="utf-8")
    paths.update(re.findall(r'\bpath=["\']([^"\']+)', frontend))
    seen = set()

    def backend_routes(module):
        if module in seen:
            return
        seen.add(module)
        file = root / "backend" / (module.replace(".", "/") + ".py")
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = getattr(node.func, "id", "")
            if name not in {"path", "re_path", "separable"}:
                continue
            offset = 1 if name == "separable" else 0
            arg = node.args[offset]
            if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                continue
            paths.add(arg.value)
            # An empty include can introduce a NEW root segment. Nonempty includes
            # are already covered by their prefix, so never reserve nested API paths.
            if not arg.value and len(node.args) > offset + 1:
                include = node.args[offset + 1]
                target = include.args[0] if isinstance(include, ast.Call) and include.args else include
                if isinstance(target, ast.Constant) and isinstance(target.value, str):
                    backend_routes(target.value)

    backend_routes("config.urls")
    for file in [root / "frontend/nginx.conf", *sorted((root / "deploy").glob("*"))]:
        if file.is_file() and ("nginx" in file.name or "Caddyfile" in file.name):
            for line in file.read_text(encoding="utf-8").splitlines():
                # Only request matchers, never filesystem roots/import paths.
                if re.search(r"\b(?:location|path|path_regexp|handle|handle_path)\s", line):
                    paths.update(re.findall(r'(?:^|\s|["\'])(\^?/[^\s;{}"\']*)', line))
    result = set()
    for path in paths:
        segment = path.lstrip("^/").split("/")[0].lower().rstrip("*$")
        if segment == ".well-known" or re.fullmatch(r"[a-z0-9][a-z0-9._-]*", segment):
            result.add(segment)
    return frozenset(result)
