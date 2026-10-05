import os
import tempfile
import time

import pytest

from api_tests.support import QA_TENANT, Api, unique
from api_tests.tenants_admin import tmp_tenants

ROLES = ["admin", "staff", "teacher", "student", "parent"]
NON_ADMIN = ["staff", "teacher", "student", "parent"]
SA_REQUIRED = "Super Admin access required"
MISSING_AUTH = "Authorization header missing or invalid"
DENIED_PREFIX = "Permission not found in database"


def denied_text(role_name: str, action: str, resource: str) -> str:
    return (
        f"{DENIED_PREFIX}: {role_name} cannot {action} {resource}. "
        "Contact administrator to configure permissions."
    )


@pytest.fixture(scope="session")
def tmp_main(superadmin):
    tenant = tmp_tenants.main_tenant(superadmin)
    yield tenant
    tmp_tenants.retire_all()


@pytest.fixture(scope="session")
def tmp_edge(superadmin):
    tenant = tmp_tenants.edge_tenant(superadmin)
    yield tenant
    tmp_tenants.retire_all()


@pytest.fixture(scope="session")
def tmp_empty(superadmin):
    tenant = tmp_tenants.empty_tenant(superadmin)
    yield tenant
    tmp_tenants.retire_all()


@pytest.fixture(scope="session")
def full_plan(superadmin) -> str:
    return tmp_tenants.full_plan_id(superadmin)


@pytest.fixture(scope="session")
def year_id(anon) -> str:
    years = anon.get("/auth/academic-years").json()
    active = [y for y in years if y["is_active"]]
    return (active or years)[0]["id"]


@pytest.fixture(scope="session")
def tenant_id(logins) -> str:
    return logins["admin"]["tenant_id"]


@pytest.fixture(scope="session")
def tenant_b_id(superadmin) -> str:
    rows = superadmin.get("/super_admin/system/tenants/?limit=500").json()["tenants"]
    return next(r["id"] for r in rows if r["client_name"] == "qa_school_b")


@pytest.fixture(scope="session")
def role_ids(admin) -> dict:
    roles = admin.get("/admin/role-mgmt/roles/").json()["roles"]
    return {r["name"]: r["id"] for r in roles}


@pytest.fixture
def bare():
    client = Api()
    yield client
    client.close()


@pytest.fixture
def api_client():
    clients = []

    def make(token: str | None = None, tenant_header: str | None = None):
        client = Api(token=token, tenant_header=tenant_header)
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()


@pytest.fixture
def custom_role(admin, cleanup):
    def make(prefix: str = "tenadm_", client=None):
        api = client or admin
        name = unique(prefix)
        response = api.post("/admin/role-mgmt/", json={"name": name, "description": "ten test role"})
        assert response.status_code == 201, response.text
        role = response.json()["role"]
        cleanup.add(api.delete, f"/admin/role-mgmt/{role['id']}")
        return role

    return make


@pytest.fixture
def tenant_header_value():
    return QA_TENANT


@pytest.fixture
def new_staff(admin, cleanup, year_id):
    from api_tests.auth import helpers

    def make(role_name: str = "Staff", role_id: str | None = None):
        return helpers.create_staff_user(admin, cleanup, year_id, role_name, role_id)

    return make


@pytest.fixture
def new_family(admin, cleanup, year_id):
    from api_tests.auth import helpers

    def make(class_id: str | None = None, father_email: str | None = None):
        return helpers.create_family(admin, cleanup, year_id, class_id, father_email)

    return make


def tenant_usernames(superadmin, tenant_id: str, **params) -> dict:
    found = {}
    offset = 0
    while True:
        body = superadmin.get(
            f"/super_admin/tenant-data/{tenant_id}/users/", params={"limit": 500, "offset": offset, **params}
        ).json()
        for user in body["users"]:
            found[user["username"]] = user
        offset += 500
        if offset >= body["total_count"]:
            return found


TMP_FIXTURES = {"tmp_main", "tmp_edge", "tmp_empty", "serial_guard"}
LOCK_PATH = os.path.join(tempfile.gettempdir(), "ten_tmp_tenants.lock")
LOCK_STALE_SECONDS = 240


def _acquire_lock() -> None:
    while True:
        try:
            handle = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(handle)
            return
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(LOCK_PATH) > LOCK_STALE_SECONDS:
                    os.remove(LOCK_PATH)
            except OSError:
                pass
            time.sleep(0.1)


def _release_lock() -> None:
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    guarded = "api_tests/tenants_admin" in item.nodeid.replace("\\", "/") and TMP_FIXTURES & set(item.fixturenames)
    if guarded:
        _acquire_lock()
    try:
        yield
    finally:
        if guarded:
            _release_lock()


@pytest.fixture
def serial_guard():
    yield


_RESULTS: dict = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    ids = [m.args[0] for m in item.iter_markers("tc") if m.args]
    if not ids:
        return
    entry = _RESULTS.setdefault(item.nodeid, {"tc": ids, "outcome": "passed", "reason": ""})
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        if hasattr(report, "wasxfail"):
            entry["outcome"] = "xfailed" if report.skipped else "xpassed"
            entry["reason"] = str(report.wasxfail)
        elif report.skipped:
            entry["outcome"] = "skipped"
            entry["reason"] = str(report.longrepr[2]) if isinstance(report.longrepr, tuple) else ""
        elif report.failed:
            entry["outcome"] = "failed"
        else:
            entry["outcome"] = "passed"


def pytest_sessionfinish(session, exitstatus):
    import json
    import os

    target = os.environ.get("QA_RESULTS_FILE")
    if target:
        existing = {}
        if os.path.exists(target):
            with open(target) as handle:
                existing = json.load(handle)
        existing.update(_RESULTS)
        with open(target, "w") as handle:
            json.dump(existing, handle)
