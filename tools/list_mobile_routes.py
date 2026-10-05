import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = os.path.abspath(os.path.join(ROOT, os.environ.get("COS360_APP", "../COS360_Full_App")))
base = os.path.join(app, "mobile", "app")

static, dynamic = [], []
for directory, _, files in os.walk(base):
    for name in files:
        if not name.endswith((".tsx", ".ts")) or name.startswith("_"):
            continue
        relative = os.path.relpath(os.path.join(directory, name), base).replace("\\", "/")
        route = "/" + relative.rsplit(".", 1)[0]
        parts = [p for p in route.split("/") if not (p.startswith("(") and p.endswith(")"))]
        route = "/".join(parts)
        if route.endswith("/index"):
            route = route[: -len("/index")]
        route = route or "/"
        (dynamic if "[" in route else static).append(route)

result = {"static": sorted(set(static)), "dynamic": sorted(set(dynamic))}
out = os.path.join(ROOT, "ui_tests", "helpers", "mobile-routes.json")
with open(out, "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=1)
print(f"{len(result['static'])} static and {len(result['dynamic'])} dynamic mobile routes -> {os.path.relpath(out, ROOT)}", file=sys.stderr)
