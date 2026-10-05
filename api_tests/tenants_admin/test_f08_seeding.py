import pytest

from api_tests.auth.helpers import create_staff_user, detail_text, grant_permission
from api_tests.tenants_admin import tmp_tenants
from api_tests.tenants_admin.conftest import MISSING_AUTH, NON_ADMIN

SEED = "/auth/seed/all-role-permissions"


def row_counts(client):
    permissions = client.get("/auth/resource-permissions/", params={"limit": 1}).json()["total_count"]
    links = len(client.get("/auth/permissions/").json())
    return permissions, links


def staff_role_rows(client, role_id):
    return {(r["resource"], r["action"]): r for r in client.get(f"/auth/resource-permissions/role/{role_id}").json()}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A01")
def test_reseed_response(tmp_main):
    response = tmp_main.admin.post(SEED)
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Role permissions seeded successfully"
    assert body["roles"] == 5
    assert body["permissions"] == 455
    assert body["role_menu_links"] == 243


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A02")
def test_reseed_is_idempotent(tmp_main):
    admin = tmp_main.admin
    first = admin.post(SEED).json()
    before = row_counts(admin)
    second = admin.post(SEED).json()
    assert row_counts(admin) == before
    assert second == first


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A03")
def test_revoked_permission_stays_revoked(tmp_main, cleanup):
    admin = tmp_main.admin
    roles = {r["name"]: r["id"] for r in admin.get("/admin/role-mgmt/roles/").json()["roles"]}
    staff_id = roles["Staff"]
    grant_permission(admin, cleanup, staff_id, "students", "list", granted=False)
    admin.post(SEED)
    assert staff_role_rows(admin, staff_id)[("students", "list")]["is_granted"] is False


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A04")
def test_deleted_permission_comes_back(tmp_main):
    admin = tmp_main.admin
    roles = {r["name"]: r["id"] for r in admin.get("/admin/role-mgmt/roles/").json()["roles"]}
    staff_id = roles["Staff"]
    row = staff_role_rows(admin, staff_id)[("students", "list")]
    assert admin.delete(f"/auth/resource-permissions/{row['id']}").status_code == 204
    try:
        assert ("students", "list") not in staff_role_rows(admin, staff_id)
        assert admin.post(SEED).status_code == 200
        restored = staff_role_rows(admin, staff_id)[("students", "list")]
        assert restored["is_granted"] is True
    finally:
        if ("students", "list") not in staff_role_rows(admin, staff_id):
            admin.post(SEED)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A05")
@pytest.mark.skip(reason="blocked: adding student_attendance:read_own to the Full plan is forbidden by the task rules and no other plan can be created (TEN-PLAN-CREATE)")
def test_plan_addition_reaches_student_after_reseed():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A06")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_reseed_denied_to_non_admin_roles(role_clients, role):
    response = role_clients[role].post(SEED)
    assert response.status_code == 403
    assert detail_text(response) == "Admin access required"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A07")
def test_custom_role_with_role_management_cannot_reseed(admin, cleanup, custom_role, year_id, api_client):
    role = custom_role()
    for action in ("create", "read", "update", "delete", "list"):
        grant_permission(admin, cleanup, role["id"], "role_management", action)
    user = create_staff_user(admin, cleanup, year_id, role_id=role["id"])
    client = api_client(token=user.login_data()["access_token"])
    response = client.post(SEED)
    assert response.status_code == 403
    assert detail_text(response) == "Admin access required"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A08")
@pytest.mark.skip(reason="blocked: a tenant with a NULL plan_id cannot be produced through the API")
def test_tenant_without_plan_409():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A09")
def test_tenant_on_plan_without_resources_409(superadmin, tmp_main):
    plan = tmp_tenants.make_plan(superadmin)
    response = superadmin.put(f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": plan["id"]})
    assert response.status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A10")
def test_reseed_requires_token(anon):
    response = anon.post(SEED)
    assert response.status_code == 401
    assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A11")
def test_reseed_does_not_touch_other_tenant(tmp_main, tenant_b):
    before = row_counts(tenant_b)
    assert tmp_main.admin.post(SEED).status_code == 200
    assert row_counts(tenant_b) == before


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A12")
def test_role_descriptions_unchanged_by_reseed(tmp_main):
    admin = tmp_main.admin

    def descriptions():
        return {r["name"]: r["description"] for r in admin.get("/admin/role-mgmt/roles/").json()["roles"] if r["is_system_role"]}

    before = descriptions()
    admin.post(SEED)
    after = descriptions()
    assert after == before
    assert after["Admin"] == "System administrator with full access"
    assert after["Student"] == "Student with limited read access"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-08-A13")
def test_system_role_names(tmp_main):
    roles = tmp_main.admin.get("/admin/role-mgmt/roles/").json()["roles"]
    assert {r["name"] for r in roles if r["is_system_role"]} == {"Admin", "Teacher", "Student", "Parent", "Staff"}
