import json
import os
import sys

import httpx
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

api_url = os.environ.get("QA_API_URL", "http://127.0.0.1:8100/api/v1").rstrip("/")
base = api_url[: -len("/api/v1")] if api_url.endswith("/api/v1") else api_url

response = httpx.get(f"{base}/openapi.json", timeout=60)
if response.status_code != 200:
    sys.exit(f"Could not read {base}/openapi.json: {response.status_code}. Is the API running?")

spec = response.json()
spec["info"]["title"] = "COS360 API"
spec["servers"] = [{"url": api_url}]

out = os.path.join(ROOT, "swagger")
os.makedirs(out, exist_ok=True)
with open(os.path.join(out, "openapi.json"), "w", encoding="utf-8") as handle:
    json.dump(spec, handle, indent=2, ensure_ascii=False)
with open(os.path.join(out, "openapi.js"), "w", encoding="utf-8") as handle:
    handle.write("window.COS360_SPEC = ")
    json.dump(spec, handle, ensure_ascii=False)
    handle.write(";\n")

operations = sum(1 for item in spec["paths"].values() for method in item if method in {"get", "post", "put", "patch", "delete"})
print(f"Exported {len(spec['paths'])} paths and {operations} operations to swagger/openapi.json and swagger/openapi.js")
