"""Static consistency checks that need no installed dependencies:
  1. every Python file compiles and has no undefined names
  2. every permission code used by a route exists in app/permissions.py (and every role permission is valid)
  3. every API URL called by the React code matches a real Flask route
  4. every named import between frontend modules resolves to an export
Run:  python scripts/verify_static.py
"""
import ast, builtins, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACK, FRONT = os.path.join(ROOT, "backend"), os.path.join(ROOT, "frontend", "src")
errors = []


def check_python():
    n = 0
    for path in glob.glob(BACK + "/**/*.py", recursive=True):
        if "__pycache__" in path or "/.venv" in path or "\\.venv" in path:
            continue
        src = open(path, encoding="utf-8").read()
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            errors.append(f"SYNTAX {path}: {e}")
            continue
        n += 1
        defined = set(dir(builtins)) | {"__file__", "__name__"}
        star = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for a in node.names:
                    if a.name == "*":
                        star = True
                    defined.add((a.asname or a.name).split(".")[0])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
                if not isinstance(node, ast.ClassDef):
                    for a in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                        defined.add(a.arg)
                    if node.args.vararg: defined.add(node.args.vararg.arg)
                    if node.args.kwarg: defined.add(node.args.kwarg.arg)
            elif isinstance(node, ast.Lambda):
                for a in node.args.args: defined.add(a.arg)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                defined.add(node.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                defined.add(node.name)
            elif isinstance(node, ast.comprehension):
                for t in ast.walk(node.target):
                    if isinstance(t, ast.Name): defined.add(t.id)
            elif isinstance(node, ast.arg):
                defined.add(node.arg)
        if star:
            continue  # seed.py uses `from app.models import *`
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in defined:
                errors.append(f"UNDEFINED NAME {os.path.relpath(path, ROOT)}:{node.lineno} '{node.id}'")
    print(f"python: parsed {n} files")


def backend_routes():
    routes = []
    for path in glob.glob(BACK + "/app/routes/*.py"):
        src = open(path, encoding="utf-8").read()
        prefix = {}
        for var, pre in re.findall(r'(\w+)\s*=\s*Blueprint\([^)]*url_prefix="([^"]*)"', src):
            prefix[var] = pre
        for var, method, route in re.findall(r'@(\w+)\.(get|post|put|delete)\(\s*"([^"]*)"', src):
            routes.append((method.upper(), prefix.get(var, "") + route, os.path.basename(path)))
        for var in re.findall(r'register_crud\(\s*(\w+)', src):
            pre = prefix.get(var, "")
            routes += [("GET", pre, "crud"), ("POST", pre, "crud"), ("GET", pre + "/<int:oid>", "crud"), ("PUT", pre + "/<int:oid>", "crud"), ("DELETE", pre + "/<int:oid>", "crud")]
    return routes


def check_permissions():
    ns = {}
    exec(open(BACK + "/app/permissions.py", encoding="utf-8").read(), ns)
    catalogue = set(ns["PERMISSIONS"])
    code_re = re.compile(r'"([a-z]+\.(?:view|manage|create|approve|receive|process|override))"')
    used = set()
    for path in glob.glob(BACK + "/app/routes/*.py") + glob.glob(BACK + "/app/*.py"):
        if path.endswith("permissions.py"):
            continue
        text = open(path, encoding="utf-8").read()
        for call in re.findall(r"permission_required\(([^)]*)\)", text):
            used |= set(code_re.findall(call))
        used |= set(re.findall(r'(?:view|manage)="([a-z]+\.[a-z]+)"', text))
    for u in sorted(used - catalogue):
        errors.append(f"UNKNOWN PERMISSION used in backend: {u}")
    for role, codes in ns["ROLE_PERMS"].items():
        for c in codes:
            if c not in catalogue:
                errors.append(f"ROLE {role} references unknown permission {c}")
    fe = set()
    for path in glob.glob(FRONT + "/**/*.js*", recursive=True):
        if "/test/" not in path.replace("\\", "/"):
            fe |= set(code_re.findall(open(path, encoding="utf-8").read()))
    for u in sorted(fe - catalogue):
        errors.append(f"UNKNOWN PERMISSION used in frontend: {u}")
    unused = catalogue - used
    print(f"permissions: {len(catalogue)} defined, {len(used)} used by routes, {len(fe)} referenced by UI" + (f"; unused by routes: {sorted(unused)}" if unused else ""))


def check_frontend_urls():
    routes = backend_routes()
    pats = []
    for m, r, f in routes:
        rx = re.sub(r"<(?:int:)?\w+>", "[^/]+", r)
        pats.append((m, re.compile("^" + rx + "$")))
    calls, seen = [], set()
    rx_call = re.compile(r'\b(get|post|put|del|download|useList|useFetch|api\.get|api\.post|api\.put|api\.delete)\(\s*([`"])((?:\\.|(?!\2).)*)\2', re.S)
    method_of = {"get": "GET", "useList": "GET", "useFetch": "GET", "api.get": "GET", "download": "GET", "post": "POST", "api.post": "POST", "put": "PUT", "api.put": "PUT", "del": "DELETE", "api.delete": "DELETE"}
    for path in glob.glob(FRONT + "/**/*.js*", recursive=True):
        if "/test/" in path.replace("\\", "/"):
            continue
        src = open(path, encoding="utf-8").read()
        for fn, _, url in rx_call.findall(src):
            if not url.startswith("/"):
                continue
            calls.append((method_of[fn], re.sub(r"\$\{[^}]*\}", "1", url.split("?")[0]), os.path.relpath(path, ROOT)))
        for chunk in src.split("<CrudPage")[1:]:  # CrudPage: list/create + /:id update (+ delete unless noDelete)
            chunk = chunk.split("<CrudPage")[0]
            m = re.search(r'endpoint="(/[^"]+)"', chunk)
            if m:
                ep = m.group(1)
                calls += [("GET", ep, path), ("POST", ep, path), ("PUT", ep + "/1", path)]
                if "noDelete" not in chunk.split("columns=")[0]:
                    calls.append(("DELETE", ep + "/1", path))
    bad = 0
    for m, u, f in calls:
        if (m, u) in seen:
            continue
        seen.add((m, u))
        if not any(pm == m and rx.match("/api" + u) for pm, rx in pats):
            errors.append(f"FRONTEND CALLS MISSING ROUTE {m} {u}  ({f})")
            bad += 1
    print(f"api: {len(seen)} distinct frontend calls checked against {len(routes)} backend routes, {bad} unmatched")


def check_imports():
    exports = {}
    files = glob.glob(FRONT + "/**/*.js*", recursive=True)
    for path in files:
        src = open(path, encoding="utf-8").read()
        names = set(re.findall(r"export\s+(?:default\s+)?(?:async\s+)?(?:function|const|let|class)\s+(\w+)", src))
        for grp in re.findall(r"export\s*\{([^}]*)\}", src):
            names |= {x.split(" as ")[-1].strip() for x in grp.split(",") if x.strip()}
        exports[os.path.normpath(path)] = (names, bool(re.search(r"export\s+default", src)))
    for path in files:
        src = open(path, encoding="utf-8").read()
        for named, default, mod in re.findall(r'import\s+(?:(\w+)\s*,?\s*)?(?:\{([^}]*)\})?\s*from\s*"(\.[^"]*)"', src):
            pass
        for m in re.finditer(r'import\s+([^;"]*?)\s+from\s+"(\.{1,2}/[^"]*)"', src):
            what, mod = m.group(1), m.group(2)
            base = os.path.normpath(os.path.join(os.path.dirname(path), mod))
            target = next((base + e for e in ("", ".js", ".jsx") if os.path.normpath(base + e) in exports), None)
            if not target or not os.path.isfile(target):
                if not mod.endswith(".css"):
                    errors.append(f"IMPORT TARGET NOT FOUND {os.path.relpath(path, ROOT)} -> {mod}")
                continue
            names, has_default = exports[os.path.normpath(target)]
            named = re.search(r"\{([^}]*)\}", what)
            if named:
                for n in [x.split(" as ")[0].strip() for x in named.group(1).split(",") if x.strip()]:
                    if n not in names:
                        errors.append(f"MISSING EXPORT {n} imported by {os.path.relpath(path, ROOT)} from {mod}")
            if re.match(r"^\w+", what.strip()) and not what.strip().startswith("{") and not has_default:
                errors.append(f"NO DEFAULT EXPORT in {mod} imported by {os.path.relpath(path, ROOT)}")
    print(f"imports: checked {len(files)} frontend modules")


def check_structure():
    models = open(BACK + "/app/models.py", encoding="utf-8").read()
    tables = set(re.findall(r'__tablename__\s*=\s*"(\w+)"', models)) | {"role_permissions"}
    classes = set(re.findall(r"^class (\w+)\(", models, re.M))
    for t in re.findall(r'ForeignKey\("(\w+)\.\w+"\)', models):
        if t not in tables:
            errors.append(f"FOREIGN KEY to unknown table {t}")
    for c in re.findall(r'relationship\(\s*"(\w+)"', models):
        if c not in classes:
            errors.append(f"RELATIONSHIP to unknown class {c}")
    required = ["users", "roles", "permissions", "products", "categories", "warehouses", "warehouse_locations", "inventory", "stock_movements", "suppliers",
                "purchase_orders", "purchase_order_items", "customers", "sales_orders", "sales_order_items", "transfers", "transfer_items", "notifications",
                "audit_logs", "batches", "settings"]
    for t in required:
        if t not in tables:
            errors.append(f"REQUIRED TABLE MISSING: {t}")
    for path in glob.glob(BACK + "/app/routes/*.py"):
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        by_bp = {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                for d in node.decorator_list:
                    if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and isinstance(d.func.value, ast.Name) and d.func.attr in ("get", "post", "put", "delete"):
                        by_bp.setdefault(d.func.value.id, []).append(node.name)
        for bp, names in by_bp.items():
            dup = {n for n in names if names.count(n) > 1}
            if dup:
                errors.append(f"DUPLICATE ENDPOINT NAMES in {os.path.basename(path)} blueprint {bp}: {sorted(dup)}")
            if re.search(r"register_crud\(\s*%s\b" % bp, src) and set(names) & {"list_", "get_", "create_", "update_", "delete_"}:
                errors.append(f"ENDPOINT NAME COLLIDES with CRUD factory in {os.path.basename(path)}")
    print(f"structure: {len(tables)} tables, {len(classes)} model classes, all {len(required)} required tables present")


def _neutralize(src):
    src = re.sub(r"`(?:\\.|[^`\\])*`", '""', src, flags=re.S)
    src = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', src)
    src = re.sub(r"'(?:\\.|[^'\\\n])*'", '""', src)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"(?m)^\s*//.*$", "", src)
    return src


def _scan_jsx(src):
    """Tiny JSX scanner: balanced tags with real attribute/brace parsing. Returns an error string or None."""
    i, n, stack = 0, len(src), []
    while True:
        i = src.find("<", i)
        if i < 0 or i >= n - 1:
            break
        nxt = src[i + 1]
        if nxt == "/":
            j = src.find(">", i)
            name = src[i + 2:j].strip()
            if not stack or stack[-1] != name:
                return f"</{name}> closes <{stack[-1] if stack else None}> near char {i}: ...{src[max(0, i - 60):i + 20]!r}"
            stack.pop()
            i = j + 1
            continue
        if not (nxt.isalpha() or nxt == ">"):
            i += 1
            continue
        m = re.match(r"<([A-Za-z][\w.]*)?", src[i:])
        name = m.group(1) or ""
        j = i + m.end()
        selfclose = False
        while j < n:
            while j < n and src[j].isspace():
                j += 1
            if src.startswith("/>", j):
                selfclose, j = True, j + 2
                break
            if src[j] == ">":
                j += 1
                break
            if src[j] == "{":
                depth = 0
                while j < n:
                    depth += (src[j] == "{") - (src[j] == "}")
                    j += 1
                    if depth == 0:
                        break
                continue
            am = re.match(r"[\w:-]+", src[j:])
            if not am:
                return f"cannot parse attributes of <{name}> near ...{src[j:j + 40]!r}"
            j += am.end()
            if j < n and src[j] == "=":
                j += 1
                if src[j] == '"':
                    j = src.find('"', j + 1) + 1
                elif src[j] == "{":
                    depth = 0
                    while j < n:
                        depth += (src[j] == "{") - (src[j] == "}")
                        j += 1
                        if depth == 0:
                            break
        if not selfclose:
            stack.append(name)
        i = j
    return f"unclosed tags {stack[-3:]}" if stack else None


def check_jsx_balance():
    bad = 0
    for path in glob.glob(FRONT + "/**/*.jsx", recursive=True):
        err = _scan_jsx(_neutralize(open(path, encoding="utf-8").read()))
        if err:
            errors.append(f"JSX {os.path.relpath(path, ROOT)}: {err}")
            bad += 1
    print(f"jsx: scanned tag/attribute structure, {bad} problem files")


if __name__ == "__main__":
    check_python(); check_structure(); check_permissions(); check_frontend_urls(); check_imports(); check_jsx_balance()
    if errors:
        print("\nPROBLEMS FOUND:"); [print(" -", e) for e in errors]; sys.exit(1)
    print("\nAll static checks passed.")
