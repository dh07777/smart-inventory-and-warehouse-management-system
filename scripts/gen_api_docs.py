"""Generate docs/API.md from the real Flask route decorators:  python scripts/gen_api_docs.py"""
import ast, glob, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = {}
for path in sorted(glob.glob(ROOT + "/backend/app/routes/*.py")):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    prefix = dict(re.findall(r'(\w+)\s*=\s*Blueprint\([^)]*url_prefix="([^"]*)"', src))
    mod = os.path.basename(path)[:-3]
    if mod == "crud":
        continue
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        routes, perms = [], []
        for d in node.decorator_list:
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ("get", "post", "put", "delete") and isinstance(d.func.value, ast.Name):
                routes.append((d.func.attr.upper(), prefix.get(d.func.value.id, "") + d.args[0].value))
            if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "permission_required":
                perms = [a.value for a in d.args]
        for m, p in routes:
            rows.setdefault(mod, []).append((m, p, " or ".join(perms) if perms else ("any signed-in user" if mod != "auth" else "public / token"), node.name))
    for var, model, kw in re.findall(r"register_crud\(\s*(\w+),\s*(\w+),[^)]*?view=\"([\w.]+)\"", src):
        pass
    for m in re.finditer(r'register_crud\(\s*(\w+),\s*(\w+),\s*\w+,\s*view="([\w.]+)",\s*manage="([\w.]+)"', src):
        var, model, view, manage = m.groups()
        pre = prefix[var]
        rows.setdefault(mod, [])
        rows[mod] += [("GET", pre, view, "list (search, filters, sort, pagination)"), ("POST", pre, manage, "create"), ("GET", pre + "/<int:oid>", view, "get"),
                      ("PUT", pre + "/<int:oid>", manage, "update"), ("DELETE", pre + "/<int:oid>", manage, "delete")]
out = ["# StockPilot API reference", "",
       "Generated from the route decorators (`python scripts/gen_api_docs.py`). Interactive Swagger UI: `/api/docs`; OpenAPI JSON: `/api/openapi.json`.", "",
       "All endpoints are under `/api`, return `{success, data, meta}` or `{success:false, error:{code,message,details}}`, and (except those marked public) need `Authorization: Bearer <access token>`.",
       "List endpoints accept `page`, `per_page` (max 200), `q`, `sort`, `order` plus module-specific filters.", ""]
total = 0
for mod, items in rows.items():
    out += [f"## {mod}", "", "| Method | Path | Permission | Handler |", "|---|---|---|---|"]
    for m, p, perm, h in sorted(items, key=lambda x: (x[1], x[0])):
        out.append(f"| {m} | `{p}` | {perm} | {h} |")
        total += 1
    out.append("")
out.insert(2, f"**{total} endpoints.**")
open(ROOT + "/docs/API.md", "w", encoding="utf-8").write("\n".join(out))
print("wrote docs/API.md with", total, "endpoints")
