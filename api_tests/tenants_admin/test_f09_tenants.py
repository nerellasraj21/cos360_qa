import uuid

import pytest

from api_tests.auth.helpers import detail_text
from api_tests.tenants_admin import tmp_tenants
from api_tests.tenants_admin.conftest import MISSING_AUTH, ROLES, SA_REQUIRED


def tenant_rows(superadmin, **params):
    params.setdefault("limit", 500)
    return superadmin.get("/super_admin/system/tenants/", params=params)


@pytest.fixture
def toggled(tmp_main):
    tmp_main.set_active(True)
    yield tmp_main
    tmp_main.set_active(True)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A01")
def test_list_tenants_shape(superadmin):
    response = tenant_rows(superadmin)
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 2
    assert set(body["pagination"]) == {"total", "limit", "offset", "has_more"}
    for row in body["tenants"]:
        assert set(row) == {"id", "client_name", "is_active", "created_at", "updated_at"}
    created = [r["created_at"] for r in body["tenants"]]
    assert created == sorted(created, reverse=True)
    names = {r["client_name"] for r in body["tenants"]}
    assert {"qa_school", "qa_school_b"} <= names


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A02")
def test_filter_inactive_tenants(superadmin, toggled):
    toggled.set_active(False)
    rows = tenant_rows(superadmin, is_active="false").json()["tenants"]
    assert rows and all(r["is_active"] is False for r in rows)
    assert toggled.tenant_id in [r["id"] for r in rows]
    active = tenant_rows(superadmin, is_active="true").json()["tenants"]
    assert toggled.tenant_id not in [r["id"] for r in active]
    assert all(r["is_active"] for r in active)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A03")
def test_pagination_has_more(superadmin):
    total = tenant_rows(superadmin).json()["pagination"]["total"]
    first = tenant_rows(superadmin, limit=1, offset=0).json()
    assert len(first["tenants"]) == 1
    assert first["pagination"]["has_more"] is (total > 1)
    last = tenant_rows(superadmin, limit=1, offset=total - 1).json()
    assert len(last["tenants"]) == 1
    assert last["pagination"]["has_more"] is False


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A04")
def test_limit_zero_returns_empty_page(superadmin):
    response = tenant_rows(superadmin, limit=0)
    assert response.status_code == 200
    assert response.json()["tenants"] == []


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A05")
@pytest.mark.xfail(strict=True, reason="TEN-NEG-LIMIT: a negative limit on GET /super_admin/system/tenants/ reaches the database and answers 500 instead of a 4xx validation error")
def test_negative_limit_is_a_client_error(superadmin):
    response = tenant_rows(superadmin, limit=-1)
    assert 400 <= response.status_code < 500


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A05")
def test_negative_limit_does_not_succeed(superadmin):
    assert tenant_rows(superadmin, limit=-1).status_code >= 400


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A06")
def test_toggle_deactivates(superadmin, toggled):
    response = superadmin.put(f"/super_admin/system/tenants/{toggled.tenant_id}/activate")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Tenant deactivated successfully"
    assert body["tenant"]["is_active"] is False
    assert set(body["tenant"]) == {"id", "client_name", "is_active", "updated_at"}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A07")
def test_inactive_tenant_blocks_login(superadmin, toggled):
    toggled.set_active(False)
    client = toggled.anon()
    try:
        response = client.post(
            "/auth/login",
            json={"username": toggled.admin_username, "password": toggled.admin_password, "academic_year_id": str(uuid.uuid4())},
        )
    finally:
        client.close()
    assert response.status_code == 404
    assert detail_text(response) == f"Tenant '{toggled.client_name}' not found or inactive"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A08")
def test_inactive_tenant_token_rejected(superadmin, toggled, api_client):
    client = api_client(token=toggled.admin_login()["access_token"])
    assert client.get("/admin/users/").status_code == 200
    toggled.set_active(False)
    response = client.get("/admin/users/")
    assert response.status_code == 401
    assert detail_text(response) == "Invalid connection"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A09")
def test_toggle_back_reactivates(superadmin, toggled):
    toggled.set_active(False)
    response = superadmin.put(f"/super_admin/system/tenants/{toggled.tenant_id}/activate")
    assert response.status_code == 200
    assert response.json()["message"] == "Tenant activated successfully"
    data = toggled.admin_login()
    assert data["role"]["name"] == "Admin"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A10")
def test_activate_unknown_and_malformed_ids(superadmin):
    pid = str(uuid.uuid4())
    missing = superadmin.put(f"/super_admin/system/tenants/{pid}/activate")
    assert missing.status_code == 404
    assert detail_text(missing) == f"Tenant with ID {pid} not found"
    assert superadmin.put("/super_admin/system/tenants/abc/activate").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A11")
@pytest.mark.tc("TC-TEN-09-A12")
@pytest.mark.tc("TC-TEN-09-A13")
@pytest.mark.tc("TC-TEN-09-A14")
@pytest.mark.tc("TC-TEN-09-A15")
def test_move_tenant_to_lite_plan_and_back(superadmin, tmp_main):
    plan = tmp_tenants.make_plan(superadmin, {"academic_years": ["read", "list"], "students": ["list"]})
    changed = superadmin.put(f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": plan["id"]})
    try:
        assert changed.status_code == 200
        body = changed.json()
        assert body["message"] == "Plan assigned and permissions synchronized"
        assert body["old_plan_id"] == tmp_main.plan_id
        assert body["permissions"] == 18
        assert body["permissions_removed"] == 437
    finally:
        superadmin.put(f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": tmp_main.plan_id})


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A16")
def test_reapplying_current_plan_resyncs(superadmin, tmp_main):
    response = superadmin.put(f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": tmp_main.plan_id})
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Plan assigned and permissions synchronized"
    assert body["tenant_id"] == tmp_main.tenant_id
    assert body["old_plan_id"] == body["plan_id"] == tmp_main.plan_id
    assert body["plan_name"] == "Full"
    assert body["roles"] == 5 and body["permissions"] == 455 and body["role_menu_links"] == 243
    assert body["permissions_removed"] >= 0 and body["role_menu_links_removed"] >= 0


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A17")
def test_change_to_unknown_plan_404(superadmin, tmp_main):
    response = superadmin.put(
        f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404
    assert detail_text(response) == "Plan not found or inactive"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A17")
def test_change_to_inactive_plan_404(superadmin, tmp_main):
    plan = tmp_tenants.make_plan(superadmin, {"students": ["list"]})
    superadmin.put(f"/super_admin/plans/{plan['id']}", params={"is_active": "false"})
    response = superadmin.put(f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": plan["id"]})
    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A18")
def test_change_plan_of_unknown_tenant_404(superadmin, full_plan):
    response = superadmin.put(f"/super_admin/system/tenants/{uuid.uuid4()}/plan", params={"plan_id": full_plan})
    assert response.status_code == 404
    assert detail_text(response) == "Tenant not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A19")
def test_change_to_plan_without_resources_409(superadmin, tmp_main):
    plan = tmp_tenants.make_plan(superadmin)
    response = superadmin.put(f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": plan["id"]})
    assert response.status_code == 409
    assert detail_text(response) == "The tenant's plan has no resources configured"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A20")
def test_change_plan_without_plan_id_422(superadmin, tmp_main):
    response = superadmin.put(f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan")
    assert response.status_code == 422
    assert "plan_id" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A21")
@pytest.mark.parametrize("role", ROLES)
def test_tenant_management_denied_to_tenant_roles(role_clients, role, full_plan):
    client = role_clients[role]
    pid = str(uuid.uuid4())
    calls = [
        client.get("/super_admin/system/tenants/"),
        client.put(f"/super_admin/system/tenants/{pid}/activate"),
        client.put(f"/super_admin/system/tenants/{pid}/plan", params={"plan_id": full_plan}),
    ]
    for response in calls:
        assert response.status_code == 403
        assert detail_text(response) == SA_REQUIRED


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A22")
def test_tenant_management_requires_token(bare, full_plan):
    pid = str(uuid.uuid4())
    calls = [
        bare.get("/super_admin/system/tenants/"),
        bare.put(f"/super_admin/system/tenants/{pid}/activate"),
        bare.put(f"/super_admin/system/tenants/{pid}/plan", params={"plan_id": full_plan}),
    ]
    for response in calls:
        assert response.status_code == 401
        assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-09-A23")
@pytest.mark.skip(reason="blocked: super_admin_audit rows cannot be read through the API and the database must not be touched")
def test_tenant_audit_rows():
    pass
