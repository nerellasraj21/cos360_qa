import os
import re
import uuid

import httpx
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"), override=True)
APP_ROOT = os.path.abspath(os.path.join(ROOT, os.environ.get("COS360_APP", "../COS360_Full_App")))
BACKEND_ROOT = os.path.join(APP_ROOT, "backend")

API_URL = os.environ.get("QA_API_URL", "http://127.0.0.1:8100/api/v1").rstrip("/")
QA_TENANT = os.environ.get("QA_TENANT", "")
QA_B_TENANT = os.environ.get("QA_B_TENANT", "qa_school_b")

ROLES = ["admin", "staff", "teacher", "student", "parent"]


def assert_safe_environment() -> None:
    if not re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?/", API_URL + "/"):
        raise RuntimeError(f"API tests refuse to run against a non-local API: {API_URL}")
    for name in (QA_TENANT, QA_B_TENANT):
        if not name.startswith("qa_"):
            raise RuntimeError(f"API tests only run against qa_ tenants, got {name!r}")


def unique(prefix: str = "t") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


class Api:
    def __init__(self, token: str | None = None, tenant_header: str | None = None, timeout: float = 60.0):
        self.token = token
        self.client = httpx.Client(base_url=API_URL, timeout=timeout, follow_redirects=True)
        self.tenant_header = tenant_header

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.tenant_header:
            headers["cschema"] = self.tenant_header
        if extra:
            headers.update(extra)
        return headers

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = self._headers(kwargs.pop("headers", None))
        return self.client.request(method, path, headers=headers, **kwargs)

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        self.client.close()


def items_of(response: httpx.Response) -> list:
    data = response.json()
    if isinstance(data, list):
        return data
    for key in ("items", "data", "results"):
        if isinstance(data, dict) and isinstance(data.get(key), list):
            return data[key]
    return []


def login(username: str, password: str, tenant: str) -> dict:
    anon = Api(tenant_header=tenant)
    try:
        years = anon.get("/auth/academic-years")
        years.raise_for_status()
        year_id = years.json()[0]["id"]
        response = anon.post(
            "/auth/login", json={"username": username, "password": password, "academic_year_id": year_id}
        )
        response.raise_for_status()
        data = response.json()
        data["_academic_year_id"] = year_id
        return data
    finally:
        anon.close()


class Cleanup:
    def __init__(self):
        self.actions: list = []

    def add(self, fn, *args, **kwargs) -> None:
        self.actions.append((fn, args, kwargs))

    def delete_later(self, api: Api, path: str) -> None:
        self.actions.append((api.delete, (path,), {}))

    def run(self) -> None:
        while self.actions:
            fn, args, kwargs = self.actions.pop()
            try:
                fn(*args, **kwargs)
            except Exception:
                pass
