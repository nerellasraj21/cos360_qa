import uuid

import pytest

from api_tests.auth.helpers import create_staff_user, detail_text, grant_permission
from api_tests.support import unique
from api_tests.tenants_admin.conftest import MISSING_AUTH, ROLES, SA_REQUIRED, tenant_usernames

BASE = "/super_admin/tenant-data"


def system_roles(superadmin, tenant_id):
    return {r["name"]: r for r in superadmin.get(f"{BASE}/{tenant_id}/roles/").json()["roles"]}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A01")
def test_tenant_schemas_listing(superadmin):
    response = superadmin.get(f"{BASE}/schemas/")
    assert response.status_code == 200
    body = response.json()
    names = [t["client_name"] for t in body["available_tenants"]]
    assert names == sorted(names)
    assert {"qa_school", "qa_school_b"} <= set(names)
    assert body["total_tenants"] == len(names)
    for row in body["available_tenants"]:
        assert set(row) == {"id", "client_name", "is_active", "created_at"}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A02")
def test_users_of_qa_school(superadmin, admin, tenant_id, logins):
    response = superadmin.get(f"{BASE}/{tenant_id}/users/", params={"limit": 500})
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == tenant_id
    by_name = tenant_usernames(superadmin, tenant_id)
    for role in ("admin", "staff", "teacher", "student", "parent"):
        user = logins[role]["user"]
        assert by_name[user["username"]]["role_name"] == logins[role]["role"]["name"]
        assert set(by_name[user["username"]]) == {"id", "username", "email", "is_active", "role_name"}
    assert body["total_count"] >= len(body["users"])
    mine = admin.get("/admin/users/", params={"limit": 100}).json()["users"]
    assert [u["username"] for u in mine[:10]] == [u["username"] for u in superadmin.get(f"{BASE}/{tenant_id}/users/", params={"limit": 10}).json()["users"]]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A03")
def test_users_of_tenant_b_only_its_own(superadmin, tenant_b_id, logins):
    body = superadmin.get(f"{BASE}/{tenant_b_id}/users/", params={"limit": 500}).json()
    names = {u["username"] for u in body["users"]}
    assert "qa_b_admin" in names
    for role in ("admin", "staff", "teacher", "student", "parent"):
        assert logins[role]["user"]["username"] not in names


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A04")
def test_users_inactive_filter(superadmin, admin, tenant_id, new_staff):
    user = new_staff("Staff")
    assert admin.patch(f"/admin/users/{user.user_id}", json={"is_active": False}).status_code == 200
    body = superadmin.get(f"{BASE}/{tenant_id}/users/", params={"is_active": "false", "limit": 500}).json()
    assert body["filters"]["is_active"] is False
    assert body["users"] and all(u["is_active"] is False for u in body["users"])
    inactive = tenant_usernames(superadmin, tenant_id, is_active="false")
    assert all(u["is_active"] is False for u in inactive.values())
    assert user.user_id in [u["id"] for u in inactive.values()]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A05")
def test_users_limit_and_offset(superadmin, tenant_id):
    whole = superadmin.get(f"{BASE}/{tenant_id}/users/", params={"limit": 4}).json()
    page = superadmin.get(f"{BASE}/{tenant_id}/users/", params={"limit": 2, "offset": 1}).json()
    assert [u["id"] for u in page["users"]] == [u["id"] for u in whole["users"][1:3]]
    assert page["limit"] == 2 and page["offset"] == 1


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A06")
@pytest.mark.parametrize("suffix", ["users", "students", "stats", "roles", "reports"])
def test_unknown_tenant_404(superadmin, suffix):
    pid = str(uuid.uuid4())
    response = superadmin.get(f"{BASE}/{pid}/{suffix}/")
    assert response.status_code == 404
    assert detail_text(response) == f"Tenant '{pid}' not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A07")
def test_malformed_tenant_id_422(superadmin):
    assert superadmin.get(f"{BASE}/abc/users/").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A08")
def test_students_listing(superadmin, tenant_id):
    body = superadmin.get(f"{BASE}/{tenant_id}/students/", params={"limit": 5}).json()
    assert body["students"]
    for row in body["students"]:
        assert set(row) == {"id", "first_name", "last_name", "date_of_birth", "gender"}
    assert body["total_count"] >= len(body["students"])


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A09")
def test_students_class_filter_is_only_echoed(superadmin, tenant_id):
    class_id = str(uuid.uuid4())
    plain = superadmin.get(f"{BASE}/{tenant_id}/students/", params={"limit": 5}).json()
    filtered = superadmin.get(f"{BASE}/{tenant_id}/students/", params={"limit": 5, "class_id": class_id}).json()
    assert filtered["students"] == plain["students"]
    assert filtered["filters"]["class_id"] == class_id


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A10")
def test_stats(superadmin, tenant_id):
    response = superadmin.get(f"{BASE}/{tenant_id}/stats/")
    assert response.status_code == 200
    body = response.json()
    stats = body["statistics"]
    assert stats["users"]["total"] == stats["users"]["active"] + stats["users"]["inactive"]
    assert stats["students"]["total"] >= stats["students"]["male"] + stats["students"]["female"]
    assert stats["classes"]["total"] >= 0
    assert body["generated_at"].endswith("Z")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A11")
def test_roles_with_permission_counts(superadmin, admin, tenant_id, role_ids):
    roles = system_roles(superadmin, tenant_id)
    assert {"Admin", "Staff", "Teacher", "Student", "Parent"} <= set(roles)
    summary = admin.get(f"/admin/role-mgmt/roles/{role_ids['Admin']}/permissions").json()["summary"]
    assert roles["Admin"]["permission_count"] == summary["total_permissions"]
    for role in roles.values():
        assert set(role) == {"id", "name", "description", "permission_count"}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A12")
def test_role_permissions_view(superadmin, admin, tenant_id, role_ids):
    body = superadmin.get(f"{BASE}/{tenant_id}/roles/{role_ids['Staff']}/permissions/").json()
    assert body["role"]["name"] == "Staff"
    granted = sum(len(p["actions"]) for p in body["permissions"])
    summary = admin.get(f"/admin/role-mgmt/roles/{role_ids['Staff']}/permissions").json()["summary"]
    assert body["total_permissions"] == granted == summary["granted_permissions"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A13")
def test_role_of_other_tenant_404(superadmin, tenant_id, tenant_b):
    other = {r["name"]: r["id"] for r in tenant_b.get("/admin/role-mgmt/roles/").json()["roles"]}["Staff"]
    response = superadmin.get(f"{BASE}/{tenant_id}/roles/{other}/permissions/")
    assert response.status_code == 404
    assert detail_text(response) == f"Role {other} not found in tenant {tenant_id}"


@pytest.fixture
def widget_role(custom_role):
    return custom_role(), unique("tenadm_w")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A14")
def test_add_role_permissions(superadmin, tenant_id, widget_role):
    role, resource = widget_role
    response = superadmin.post(
        f"{BASE}/{tenant_id}/roles/{role['id']}/permissions/", params={"resource_name": resource, "actions": "read,list"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Permissions added to role successfully"
    assert body["added_permissions"]["resource"] == resource
    assert body["added_permissions"]["actions"] == ["read", "list"]
    assert body["skipped"] == 0
    assert body["role"]["id"] == role["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A15")
def test_add_same_permissions_again_400(superadmin, tenant_id, widget_role):
    role, resource = widget_role
    params = {"resource_name": resource, "actions": "read,list"}
    superadmin.post(f"{BASE}/{tenant_id}/roles/{role['id']}/permissions/", params=params)
    again = superadmin.post(f"{BASE}/{tenant_id}/roles/{role['id']}/permissions/", params=params)
    assert again.status_code == 400
    assert detail_text(again) == f"All permissions for resource '{resource}' already exist for this role"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A16")
def test_partially_new_actions(superadmin, tenant_id, widget_role):
    role, resource = widget_role
    url = f"{BASE}/{tenant_id}/roles/{role['id']}/permissions/"
    superadmin.post(url, params={"resource_name": resource, "actions": "read"})
    response = superadmin.post(url, params={"resource_name": resource, "actions": "read,update"})
    assert response.status_code == 201
    assert response.json()["added_permissions"]["actions"] == ["update"]
    assert response.json()["skipped"] == 1


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A17")
def test_added_permission_shows_at_next_login(superadmin, admin, tenant_id, custom_role, year_id, cleanup):
    role = custom_role()
    resource = unique("tenadm_w")
    user = create_staff_user(admin, cleanup, year_id, role_id=role["id"])
    before = user.login_data()
    assert resource not in before["permissions"]
    superadmin.post(
        f"{BASE}/{tenant_id}/roles/{role['id']}/permissions/", params={"resource_name": resource, "actions": "read,list"}
    )
    after = user.login_data()
    assert sorted(after["permissions"][resource]) == ["list", "read"]
    assert resource not in before["permissions"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A18")
def test_added_permission_effective_at_once(superadmin, admin, tenant_id, custom_role, year_id, cleanup, api_client):
    role = custom_role()
    user = create_staff_user(admin, cleanup, year_id, role_id=role["id"])
    client = api_client(token=user.login_data()["access_token"])
    assert client.get("/admin/users/").status_code == 403
    response = superadmin.post(
        f"{BASE}/{tenant_id}/roles/{role['id']}/permissions/", params={"resource_name": "user_management", "actions": "list"}
    )
    assert response.status_code == 201
    assert client.get("/admin/users/").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A19")
def test_revoked_row_counts_as_existing(superadmin, admin, tenant_id, custom_role, cleanup):
    role = custom_role()
    resource = unique("tenadm_w")
    grant_permission(admin, cleanup, role["id"], resource, "read", granted=False)
    response = superadmin.post(
        f"{BASE}/{tenant_id}/roles/{role['id']}/permissions/", params={"resource_name": resource, "actions": "read"}
    )
    assert response.status_code == 400
    rows = admin.get(f"/auth/resource-permissions/role/{role['id']}").json()
    assert [r["is_granted"] for r in rows if r["resource"] == resource] == [False]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A20")
def test_add_permissions_unknown_role_404(superadmin, tenant_id):
    rid = str(uuid.uuid4())
    response = superadmin.post(
        f"{BASE}/{tenant_id}/roles/{rid}/permissions/", params={"resource_name": "tenadm_w", "actions": "read"}
    )
    assert response.status_code == 404
    assert detail_text(response) == f"Role {rid} not found in tenant {tenant_id}"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A21")
def test_add_permissions_without_actions_422(superadmin, tenant_id, role_ids):
    response = superadmin.post(
        f"{BASE}/{tenant_id}/roles/{role_ids['Staff']}/permissions/", params={"resource_name": "tenadm_w"}
    )
    assert response.status_code == 422
    assert "actions" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A22")
def test_reports_listing(superadmin, tenant_id):
    response = superadmin.get(f"{BASE}/{tenant_id}/reports/")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["reports"], list)
    assert body["limit"] == 100 and body["offset"] == 0
    assert body["total_count"] >= len(body["reports"])


def all_endpoints(client, tenant_id, role_id):
    return [
        client.get(f"{BASE}/schemas/"),
        client.get(f"{BASE}/{tenant_id}/users/"),
        client.get(f"{BASE}/{tenant_id}/students/"),
        client.get(f"{BASE}/{tenant_id}/stats/"),
        client.get(f"{BASE}/{tenant_id}/roles/"),
        client.get(f"{BASE}/{tenant_id}/roles/{role_id}/permissions/"),
        client.post(
            f"{BASE}/{tenant_id}/roles/{role_id}/permissions/", params={"resource_name": "tenadm_never", "actions": "read"}
        ),
        client.get(f"{BASE}/{tenant_id}/reports/"),
    ]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A23")
@pytest.mark.parametrize("role", ROLES)
def test_tenant_data_denied_to_tenant_roles(role_clients, role, tenant_id, role_ids):
    for response in all_endpoints(role_clients[role], tenant_id, role_ids["Staff"]):
        assert response.status_code == 403
        assert detail_text(response) == SA_REQUIRED


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A24")
def test_tenant_data_requires_token(bare, tenant_id, role_ids):
    for response in all_endpoints(bare, tenant_id, role_ids["Staff"]):
        assert response.status_code == 401
        assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A25")
def test_inactive_tenant_remains_readable(superadmin, tmp_main):
    tmp_main.set_active(False)
    try:
        response = superadmin.get(f"{BASE}/{tmp_main.tenant_id}/users/")
        assert response.status_code == 200
        assert response.json()["tenant_id"] == tmp_main.tenant_id
    finally:
        tmp_main.set_active(True)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-10-A26")
@pytest.mark.skip(reason="blocked: super_admin_audit rows cannot be read through the API and the database must not be touched")
def test_tenant_data_calls_not_audited():
    pass
