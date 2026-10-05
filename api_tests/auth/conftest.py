import pytest

from api_tests.auth import helpers
from api_tests.support import QA_B_TENANT, QA_TENANT, Api


@pytest.fixture(scope="session")
def year_id(anon) -> str:
    years = anon.get("/auth/academic-years").json()
    active = [y for y in years if y["is_active"]]
    return (active or years)[0]["id"]


@pytest.fixture(scope="session")
def role_ids(admin) -> dict:
    return helpers.role_id_map(admin)


@pytest.fixture(scope="session")
def tenant_cschema() -> str:
    return QA_TENANT


@pytest.fixture(scope="session")
def tenant_b_cschema() -> str:
    return QA_B_TENANT


@pytest.fixture
def new_staff(admin, cleanup, year_id, role_ids):
    def make(role_name: str = "Staff", role_id: str | None = None):
        return helpers.create_staff_user(admin, cleanup, year_id, role_name, role_id)

    return make


@pytest.fixture
def new_family(admin, cleanup, year_id):
    def make(class_id: str | None = None, father_email: str | None = None):
        return helpers.create_family(admin, cleanup, year_id, class_id, father_email)

    return make


@pytest.fixture
def grant(admin, cleanup, role_ids):
    def make(role_name: str, resource: str, action: str, granted: bool = True):
        helpers.grant_permission(admin, cleanup, role_ids[role_name], resource, action, granted)

    return make


@pytest.fixture
def custom_role(admin, cleanup):
    def make(prefix: str = "auth_"):
        name = helpers.unique(prefix)
        response = admin.post("/admin/role-mgmt/", json={"name": name, "description": "auth test role"})
        assert response.status_code == 201, response.text
        role = response.json()["role"]
        cleanup.add(admin.delete, f"/admin/role-mgmt/{role['id']}")
        return role

    return make


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


@pytest.fixture(scope="session")
def tmp_main(superadmin):
    from api_tests.tenants_admin import tmp_tenants

    tenant = tmp_tenants.main_tenant(superadmin)
    yield tenant
    tmp_tenants.retire_all()


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
