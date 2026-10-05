import os

import httpx
import pytest

from api_tests.support import (
    API_URL,
    QA_B_TENANT,
    QA_TENANT,
    Api,
    Cleanup,
    assert_safe_environment,
    login,
)

assert_safe_environment()


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is missing in .env")
    return value


@pytest.fixture(scope="session", autouse=True)
def api_is_up():
    try:
        response = httpx.get(f"{API_URL}/auth/academic-years", headers={"cschema": QA_TENANT}, timeout=20)
    except httpx.HTTPError as exc:
        pytest.exit(f"Test API is not reachable at {API_URL}: {exc}. Start it with scripts/qa/run_test_api.py", 2)
    if response.status_code != 200:
        pytest.exit(
            f"Test API answered {response.status_code} for tenant {QA_TENANT}; run scripts/qa/setup_qa_tenant.py", 2
        )


@pytest.fixture(scope="session")
def tenant_name() -> str:
    return QA_TENANT


@pytest.fixture(scope="session")
def logins() -> dict:
    result = {}
    for role in ("admin", "staff", "teacher", "student", "parent"):
        result[role] = login(env(f"QA_{role.upper()}_USER"), env(f"QA_{role.upper()}_PASSWORD"), QA_TENANT)
    return result


@pytest.fixture(scope="session")
def academic_year_id(logins) -> str:
    return logins["admin"]["_academic_year_id"]


def _client(logins, role):
    return Api(token=logins[role]["access_token"])


@pytest.fixture(scope="session")
def admin(logins):
    client = _client(logins, "admin")
    yield client
    client.close()


@pytest.fixture(scope="session")
def staff(logins):
    client = _client(logins, "staff")
    yield client
    client.close()


@pytest.fixture(scope="session")
def teacher(logins):
    client = _client(logins, "teacher")
    yield client
    client.close()


@pytest.fixture(scope="session")
def student(logins):
    client = _client(logins, "student")
    yield client
    client.close()


@pytest.fixture(scope="session")
def parent(logins):
    client = _client(logins, "parent")
    yield client
    client.close()


@pytest.fixture(scope="session")
def role_clients(admin, staff, teacher, student, parent) -> dict:
    return {"admin": admin, "staff": staff, "teacher": teacher, "student": student, "parent": parent}


@pytest.fixture(scope="session")
def anon():
    client = Api(tenant_header=QA_TENANT)
    yield client
    client.close()


@pytest.fixture(scope="session")
def superadmin():
    client = Api()
    response = client.post(
        "/super_admin/auth/login",
        json={"username": env("QA_SUPERADMIN_USER"), "password": env("QA_SUPERADMIN_PASSWORD")},
    )
    if response.status_code != 200:
        pytest.exit(f"Super admin login failed ({response.status_code}); run scripts/qa/setup_qa_tenant.py", 2)
    client.token = response.json()["access_token"]
    yield client
    client.close()


@pytest.fixture(scope="session")
def tenant_b_name() -> str:
    return QA_B_TENANT


@pytest.fixture(scope="session")
def tenant_b(superadmin):
    plans = superadmin.get("/super_admin/plans/").json()["plans"]
    plan_id = next(p["id"] for p in plans if p["name"] == "Full")
    tenants = superadmin.get("/super_admin/system/tenants/").json()["tenants"]
    if not any(t["client_name"] == QA_B_TENANT for t in tenants):
        created = superadmin.post(
            f"/super_admin/system/tenants/?client_name={QA_B_TENANT}&plan_id={plan_id}",
            json={
                "username": env("QA_B_ADMIN_USER"),
                "email": f"{env('QA_B_ADMIN_USER')}@example.com",
                "password": env("QA_B_ADMIN_PASSWORD"),
            },
        )
        assert created.status_code == 201, created.text
    data = login(env("QA_B_ADMIN_USER"), env("QA_B_ADMIN_PASSWORD"), QA_B_TENANT)
    client = Api(token=data["access_token"])
    client.academic_year_id = data["_academic_year_id"]
    yield client
    client.close()


@pytest.fixture
def cleanup():
    stack = Cleanup()
    yield stack
    stack.run()
