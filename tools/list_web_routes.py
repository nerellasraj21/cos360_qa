import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = os.path.abspath(os.path.join(ROOT, os.environ.get("COS360_APP", "../COS360_Full_App")))
tree = os.path.join(app, "web", "src", "routeTree.gen.ts")

with open(tree, encoding="utf-8") as handle:
    text = handle.read()
block = re.search(r"export interface FileRoutesByFullPath \{(.*?)\n\}", text, re.S).group(1)
paths = re.findall(r"'([^']+)':", block)
skip = {"/auth", "/forgot-password", "/login", "/set-password"}
result = {
    "static": sorted(p for p in paths if "$" not in p and p not in skip),
    "dynamic": sorted(p for p in paths if "$" in p),
}
out = os.path.join(ROOT, "ui_tests", "helpers", "web-routes.json")
with open(out, "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=1)
print(f"{len(result['static'])} static and {len(result['dynamic'])} dynamic web routes -> {os.path.relpath(out, ROOT)}", file=sys.stderr)
