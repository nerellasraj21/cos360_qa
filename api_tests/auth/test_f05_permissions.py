import os

import pytest

from api_tests.auth.helpers import (
    PERMISSION_DENIED_PREFIX,
    TEMP_STAFF_PASSWORD,
    detail_text,
    fresh_login,
    grant_permission,
    rand_phone,
    role_id_map,
    set_password,
)
from api_tests.support import unique

ROLE_NAMES = ["admin", "staff", "teacher", "student", "parent"]


def granted_map(admin, role_id):
    rows = admin.get(f"/auth/resource-permissions/role/{role_id}").json()
    result = {}
    for row in rows:
        if row["is_granted"]:
            result.setdefault(row["resource"], set()).add(row["action"])
    return result


def as_sets(permissions):
    return {resource: set(actions) for resource, actions in permissions.items()}


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A01")
def test_admin_permissions_equal_granted_rows(admin, role_ids, logins, year_id):
    body = fresh_login(logins["admin"]["user"]["username"], os.environ["QA_ADMIN_PASSWORD"], year_id).json()
    assert as_sets(body["permissions"]) == granted_map(admin, role_ids["Admin"])
    assert set(body["permissions"]["role_management"]) == {"create", "read", "update", "delete", "list"}


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A02")
@pytest.mark.parametrize("role", ROLE_NAMES[1:])
def test_role_maps_equal_granted_rows(admin, role_ids, logins, year_id, role):
    body = fresh_login(logins[role]["user"]["username"], os.environ[f"QA_{role.upper()}_PASSWORD"], year_id).json()
    assert as_sets(body["permissions"]) == granted_map(admin, role_ids[role.capitalize()])


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A02")
def test_teacher_has_no_fee_and_student_no_plain_student_read(logins):
    assert not [r for r in logins["teacher"]["permissions"] if r.startswith("fee")]
    assert "read" not in logins["student"]["permissions"].get("students", [])


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A03")
@pytest.mark.parametrize("role", ROLE_NAMES)
def test_action_lists_sorted(logins, role):
    for actions in logins[role]["permissions"].values():
        assert actions == sorted(actions)


def custom_role_user(new_staff, custom_role):
    role = custom_role()
    user = new_staff("Staff", role_id=role["id"])
    return role, user


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A04")
def test_revoked_action_absent_after_new_login(admin, cleanup, new_staff, custom_role):
    role, user = custom_role_user(new_staff, custom_role)
    resource = unique("auth_res_")
    grant_permission(admin, cleanup, role["id"], resource, "read")
    grant_permission(admin, cleanup, role["id"], resource, "list")
    before = user.login_data()
    assert set(before["permissions"][resource]) == {"list", "read"}
    grant_permission(admin, cleanup, role["id"], resource, "read", granted=False)
    after = user.login_data()
    assert after["permissions"][resource] == ["list"]


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A05")
def test_new_grant_works_immediately_with_old_token(admin, cleanup, new_staff, custom_role, api_client):
    role, user = custom_role_user(new_staff, custom_role)
    data = user.login_data()
    client = api_client(token=data["access_token"])
    assert client.get("/admin/users/").status_code == 403
    grant_permission(admin, cleanup, role["id"], "user_management", "list")
    assert client.get("/admin/users/").status_code == 200
    assert "user_management" not in data["permissions"]


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A06")
def test_revoked_grant_denied_immediately(admin, cleanup, new_staff, custom_role, api_client):
    role, user = custom_role_user(new_staff, custom_role)
    grant_permission(admin, cleanup, role["id"], "user_management", "list")
    client = api_client(token=user.login_data()["access_token"])
    assert client.get("/admin/users/").status_code == 200
    grant_permission(admin, cleanup, role["id"], "user_management", "list", granted=False)
    response = client.get("/admin/users/")
    assert response.status_code == 403
    assert detail_text(response) == (
        f"{PERMISSION_DENIED_PREFIX}: {role['name']} cannot list user_management. "
        "Contact administrator to configure permissions."
    )


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A07")
def test_role_without_grants_gets_empty_map_and_menu(new_staff, custom_role):
    role, user = custom_role_user(new_staff, custom_role)
    data = user.login_data()
    assert data["permissions"] == {}
    assert data["menu"] == []


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A08")
@pytest.mark.parametrize("role", ROLE_NAMES)
def test_user_list_permission_matrix(role_clients, role):
    response = role_clients[role].get("/admin/users/")
    assert response.status_code == (200 if role == "admin" else 403)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A09")
def test_set_password_map_equals_login_map(new_staff):
    user = new_staff("Teacher")
    first = set_password(user.challenge(), "Password#Map1").json()
    user.password = "Password#Map1"
    again = user.login_data()
    assert first["permissions"] == again["permissions"]
    assert first["menu"] == again["menu"]


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A10")
def test_other_tenant_grant_does_not_leak(tenant_b, role_clients, logins, year_id):
    roles_b = role_id_map(tenant_b)
    resource = unique("auth_iso_")
    response = tenant_b.put(
        f"/admin/role-mgmt/roles/{roles_b['Staff']}/permissions",
        params={"resource": resource, "action": "read", "is_granted": "true"},
    )
    assert response.status_code == 200
    try:
        body = fresh_login(logins["staff"]["user"]["username"], os.environ["QA_STAFF_PASSWORD"], year_id).json()
        assert resource not in body["permissions"]
        rows = tenant_b.get(f"/auth/resource-permissions/role/{roles_b['Staff']}").json()
        assert any(r["resource"] == resource for r in rows)
    finally:
        for row in tenant_b.get(f"/auth/resource-permissions/role/{roles_b['Staff']}").json():
            if row["resource"] == resource:
                tenant_b.delete(f"/auth/resource-permissions/{row['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-05-A11")
@pytest.mark.parametrize("role_name", ["Student", "Parent"])
def test_plan_without_scoped_actions_gives_no_own_or_related(tmp_main, cleanup, role_name):
    admin = tmp_main.admin
    role_id = role_id_map(admin)[role_name]
    email = f"{unique('auth_')}@example.com"
    made = admin.post(
        "/staff/enrollment",
        json={"first_name": "T", "email": email, "phone": rand_phone(), "address": "x", "role_id": role_id},
    )
    assert made.status_code in (200, 201), made.text
    cleanup.add(admin.patch, f"/admin/users/{made.json()['user_id']}", json={"is_active": False})
    cleanup.add(admin.delete, f"/staff/enrollment/{made.json()['id']}")
    first = fresh_login(email, TEMP_STAFF_PASSWORD, tmp_main.year_id, tenant=tmp_main.client_name).json()
    done = set_password(first["change_password_token"], "Password#11", tenant=tmp_main.client_name).json()
    permissions = done["permissions"]
    assert "profile" not in permissions
    for actions in permissions.values():
        assert not [a for a in actions if a.endswith("_own") or a.endswith("_related")]
    assert sum(len(a) for a in permissions.values()) == (10 if role_name == "Student" else 8)
