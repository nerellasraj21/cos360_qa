import uuid

import pytest

from api_tests.auth.helpers import detail_text, grant_permission
from api_tests.support import unique
from api_tests.tenants_admin.conftest import MISSING_AUTH, NON_ADMIN, ROLES, denied_text

SYSTEM = ["Admin", "Staff", "Teacher", "Student", "Parent"]


def new_role(admin, cleanup, description="tenadm test role", name=None):
    name = name or unique("tenadm_")
    response = admin.post("/admin/role-mgmt/", json={"name": name, "description": description})
    assert response.status_code == 201, response.text
    role = response.json()["role"]
    cleanup.add(admin.delete, f"/admin/role-mgmt/{role['id']}")
    return role


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A01")
def test_list_roles_shape(admin, custom_role, tenant_id):
    custom_role()
    response = admin.get("/admin/role-mgmt/roles/")
    assert response.status_code == 200
    body = response.json()
    assert body["total_roles"] == len(body["roles"])
    assert body["tenant_id"] == tenant_id
    names = [r["name"] for r in body["roles"]]
    assert names == sorted(names, key=str.lower)
    assert set(SYSTEM) <= set(names)
    for role in body["roles"]:
        assert role["is_active"] is True
        assert {"id", "name", "description", "is_system_role", "is_custom_role", "created_at", "updated_at", "permission_count"} <= set(role)
    assert {r["name"] for r in body["roles"] if r["is_system_role"]} == set(SYSTEM)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A02")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_list_roles_requires_list_permission(role_clients, logins, role):
    response = role_clients[role].get("/admin/role-mgmt/roles/")
    assert response.status_code == 403
    assert detail_text(response) == denied_text(logins[role]["role"]["name"], "list", "role_management")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A03")
def test_admin_permission_count(tmp_main):
    roles = tmp_main.admin.get("/admin/role-mgmt/roles/").json()["roles"]
    admin_role = next(r for r in roles if r["name"] == "Admin")
    assert admin_role["permission_count"] == 276


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A04")
def test_create_custom_role(admin, cleanup):
    name = unique("tenadm_Lib ")
    response = admin.post("/admin/role-mgmt/", json={"name": name, "description": "QA custom role"})
    assert response.status_code == 201
    body = response.json()
    cleanup.add(admin.delete, f"/admin/role-mgmt/{body['role']['id']}")
    assert body["message"] == "Role created successfully"
    assert body["role"]["name"] == name
    assert body["role"]["is_system_role"] is False
    assert body["role"]["permission_count"] == 0 and body["role"]["user_count"] == 0
    assert len(body["next_steps"]) == 3


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A05")
@pytest.mark.parametrize("name", ["Admin", "Staff"])
def test_create_system_role_name_422(admin, name):
    response = admin.post("/admin/role-mgmt/", json={"name": name, "description": "x"})
    assert response.status_code == 422
    assert "Cannot create system role" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A06")
def test_create_lowercase_system_name_400(admin):
    response = admin.post("/admin/role-mgmt/", json={"name": "admin", "description": "x"})
    assert response.status_code == 400
    assert detail_text(response) == "Role with name 'admin' already exists in this tenant"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A07")
def test_create_duplicate_name_any_case_400(admin, cleanup):
    name = unique("tenadm_dup ")
    role = new_role(admin, cleanup, name=name)
    assert role["name"] == name
    response = admin.post("/admin/role-mgmt/", json={"name": name.upper(), "description": "x"})
    assert response.status_code == 400
    assert detail_text(response) == f"Role with name '{name.upper()}' already exists in this tenant"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A08")
@pytest.mark.parametrize("name", ["x", "Bad!", "n" * 51], ids=["short", "symbol", "long"])
def test_create_invalid_names_422(admin, name):
    assert admin.post("/admin/role-mgmt/", json={"name": name, "description": "x"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A09")
def test_create_with_100_character_description(admin, cleanup):
    role = new_role(admin, cleanup, description="d" * 100)
    assert role["description"] == "d" * 100


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A09")
@pytest.mark.xfail(strict=True, reason="TEN-ROLE-DESC-LEN: a 101-200 character description passes the schema but fails in the database with 500")
def test_create_with_101_character_description_is_not_a_server_error(admin, cleanup):
    name = unique("tenadm_")
    response = admin.post("/admin/role-mgmt/", json={"name": name, "description": "d" * 101})
    if response.status_code == 201:
        cleanup.add(admin.delete, f"/admin/role-mgmt/{response.json()['role']['id']}")
    assert response.status_code != 500


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A10")
def test_same_role_name_in_two_tenants(admin, tenant_b, cleanup):
    name = unique("tenadm_shared")
    first = new_role(admin, cleanup, name=name)
    second = new_role(tenant_b, cleanup, name=name)
    assert first["name"] == second["name"] == name
    assert first["id"] != second["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A11")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_create_role_denied(role_clients, logins, role):
    response = role_clients[role].post("/admin/role-mgmt/", json={"name": unique("tenadm_"), "description": "x"})
    assert response.status_code == 403
    assert detail_text(response) == denied_text(logins[role]["role"]["name"], "create", "role_management")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A12")
def test_update_role(admin, cleanup):
    role = new_role(admin, cleanup)
    new_name = role["name"] + "x"
    response = admin.put(f"/admin/role-mgmt/{role['id']}", json={"name": new_name, "description": "Updated"})
    assert response.status_code == 200
    changes = response.json()["changes_made"]
    assert changes["name"] == {"old": role["name"], "new": new_name}
    assert changes["description"] == {"old": "tenadm test role", "new": "Updated"}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A13")
def test_update_with_same_values(admin, cleanup):
    role = new_role(admin, cleanup)
    response = admin.put(f"/admin/role-mgmt/{role['id']}", json={"name": role["name"], "description": role["description"]})
    assert response.status_code == 200
    assert response.json()["message"] == "No changes were made to the role"
    assert response.json()["changes_made"] == {}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A14")
def test_rename_to_existing_name_400(admin, cleanup):
    first = new_role(admin, cleanup)
    second = new_role(admin, cleanup)
    response = admin.put(f"/admin/role-mgmt/{second['id']}", json={"name": first["name"].upper()})
    assert response.status_code == 400
    assert detail_text(response) == f"Role with name '{first['name'].upper()}' already exists"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A15")
def test_update_system_role_403(admin, role_ids):
    response = admin.put(f"/admin/role-mgmt/{role_ids['Teacher']}", json={"description": "changed"})
    assert response.status_code == 403
    assert detail_text(response) == "Cannot modify system role 'Teacher'. System roles are protected."


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A16")
def test_rename_to_system_name_422(admin, cleanup):
    role = new_role(admin, cleanup)
    assert admin.put(f"/admin/role-mgmt/{role['id']}", json={"name": "Admin"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A17")
def test_is_active_is_ignored(admin, cleanup):
    role = new_role(admin, cleanup)
    response = admin.put(f"/admin/role-mgmt/{role['id']}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["changes_made"] == {}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A18")
def test_update_unknown_role_404(admin):
    rid = str(uuid.uuid4())
    response = admin.put(f"/admin/role-mgmt/{rid}", json={"description": "x"})
    assert response.status_code == 404
    assert detail_text(response) == f"Role with ID {rid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A19")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_update_role_denied(role_clients, logins, role, custom_role):
    target = custom_role()
    response = role_clients[role].put(f"/admin/role-mgmt/{target['id']}", json={"description": "x"})
    assert response.status_code == 403
    assert detail_text(response) == denied_text(logins[role]["role"]["name"], "update", "role_management")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A20")
def test_delete_unused_custom_role(admin, cleanup):
    role = new_role(admin, cleanup)
    grant_permission(admin, cleanup, role["id"], unique("tenadm_w"), "read")
    removed = admin.get(f"/admin/role-mgmt/roles/{role['id']}/permissions").json()["summary"]["total_permissions"]
    response = admin.delete(f"/admin/role-mgmt/{role['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == f"Role '{role['name']}' deleted successfully"
    assert body["impact_summary"]["permissions_removed"] == removed
    assert role["id"] not in [r["id"] for r in admin.get("/admin/role-mgmt/roles/").json()["roles"]]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A21")
@pytest.mark.parametrize("name", SYSTEM)
def test_delete_system_roles_403(admin, role_ids, name):
    response = admin.delete(f"/admin/role-mgmt/{role_ids[name]}")
    assert response.status_code == 403
    assert detail_text(response) == f"Cannot delete system role '{name}'. System roles are protected."


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A22")
def test_delete_role_with_users_400(admin, cleanup, custom_role, new_staff):
    role = custom_role()
    new_staff("Staff", role_id=role["id"])
    response = admin.delete(f"/admin/role-mgmt/{role['id']}")
    assert response.status_code == 400
    assert detail_text(response) == (
        f"Cannot delete role '{role['name']}'. 1 users are assigned to this role. "
        "Reassign users to different roles first, or use force=true to override."
    )
    assert role["id"] in [r["id"] for r in admin.get("/admin/role-mgmt/roles/").json()["roles"]]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A23")
@pytest.mark.xfail(strict=True, reason="TEN-ROLE-FORCE-DELETE: DELETE with force=true on a role with users answers 500 because users.role_id cannot be NULL")
def test_force_delete_with_users_is_not_a_server_error(admin, custom_role, new_staff):
    role = custom_role()
    user = new_staff("Staff", role_id=role["id"])
    response = admin.delete(f"/admin/role-mgmt/{role['id']}", params={"force": "true"})
    assert response.status_code != 500
    assert admin.get(f"/admin/users/{user.user_id}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A23")
def test_force_delete_with_users_keeps_state(admin, custom_role, new_staff):
    role = custom_role()
    user = new_staff("Staff", role_id=role["id"])
    admin.delete(f"/admin/role-mgmt/{role['id']}", params={"force": "true"})
    assert role["id"] in [r["id"] for r in admin.get("/admin/role-mgmt/roles/").json()["roles"]]
    assert admin.get(f"/admin/users/{user.user_id}").json()["role_id"] == role["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A24")
@pytest.mark.xfail(strict=True, reason="TEN-ROLE-FORCE-DELETE: deleting a role that still has a role-menu link answers 500 (foreign key) instead of a client error")
def test_delete_role_with_menu_link_is_not_a_server_error(tmp_main, custom_role):
    admin = tmp_main.admin
    role = custom_role(client=admin)
    menu = next(m for m in admin.get("/auth/menus/").json() if m["url"] == "/dashboard")
    assert admin.post("/auth/permissions/", json={"role_id": role["id"], "menu_id": menu["id"]}).status_code == 201
    response = admin.delete(f"/admin/role-mgmt/{role['id']}")
    assert response.status_code != 500


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A24")
def test_role_with_menu_link_survives_failed_delete(tmp_main, custom_role):
    admin = tmp_main.admin
    role = custom_role(client=admin)
    menu = next(m for m in admin.get("/auth/menus/").json() if m["url"] == "/dashboard")
    admin.post("/auth/permissions/", json={"role_id": role["id"], "menu_id": menu["id"]})
    assert not admin.delete(f"/admin/role-mgmt/{role['id']}").is_success
    assert role["id"] in [r["id"] for r in admin.get("/admin/role-mgmt/roles/").json()["roles"]]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A25")
def test_delete_unknown_role_404(admin):
    rid = str(uuid.uuid4())
    response = admin.delete(f"/admin/role-mgmt/{rid}")
    assert response.status_code == 404
    assert detail_text(response) == f"Role with ID {rid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A26")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_delete_role_denied(role_clients, logins, role, custom_role, admin):
    target = custom_role()
    response = role_clients[role].delete(f"/admin/role-mgmt/{target['id']}")
    assert response.status_code == 403
    assert detail_text(response) == denied_text(logins[role]["role"]["name"], "delete", "role_management")
    assert target["id"] in [r["id"] for r in admin.get("/admin/role-mgmt/roles/").json()["roles"]]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A27")
def test_delete_validation_for_custom_role(admin, cleanup):
    role = new_role(admin, cleanup)
    response = admin.get(f"/admin/role-mgmt/{role['id']}/delete-validation")
    assert response.status_code == 200
    body = response.json()
    assert body["can_delete"] is True
    assert body["role"]["id"] == role["id"]
    assert body["blocking_factors"] == []


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A28")
def test_delete_validation_for_system_role_and_unknown(admin, role_ids):
    system = admin.get(f"/admin/role-mgmt/{role_ids['Teacher']}/delete-validation")
    assert system.status_code == 200
    assert system.json()["can_delete"] is False
    rid = str(uuid.uuid4())
    missing = admin.get(f"/admin/role-mgmt/{rid}/delete-validation")
    assert missing.status_code == 404
    assert detail_text(missing) == f"Role with ID {rid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A29")
@pytest.mark.parametrize("role", ROLES)
def test_delete_validation_matrix(role_clients, logins, role, custom_role):
    target = custom_role()
    response = role_clients[role].get(f"/admin/role-mgmt/{target['id']}/delete-validation")
    if role == "admin":
        assert response.status_code == 200
    else:
        assert response.status_code == 403
        assert detail_text(response) == denied_text(logins[role]["role"]["name"], "read", "role_management")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A30")
def test_legacy_create_role(admin, cleanup):
    name = unique("tenadm_leg")
    response = admin.post("/auth/roles/roles/", json={"name": name})
    assert response.status_code == 201
    body = response.json()
    cleanup.add(admin.delete, f"/admin/role-mgmt/{body['id']}")
    assert body["name"] == name
    assert body["is_system_role"] is False and body["is_custom_role"] is False


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A31")
def test_legacy_duplicate_400(admin, cleanup):
    name = unique("tenadm_leg")
    first = admin.post("/auth/roles/roles/", json={"name": name})
    cleanup.add(admin.delete, f"/admin/role-mgmt/{first.json()['id']}")
    assert admin.post("/auth/roles/roles/", json={"name": name}).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A32")
def test_legacy_system_name_duplicate_400(admin):
    assert admin.post("/auth/roles/roles/", json={"name": "Admin"}).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A33")
def test_legacy_list_roles(admin, staff, role_ids):
    response = admin.get("/auth/roles/roles/")
    assert response.status_code == 200
    assert {r["name"] for r in response.json()} >= set(SYSTEM)
    assert staff.get("/auth/roles/roles/").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A34")
def test_role_endpoints_require_token(anon, role_ids):
    rid = role_ids["Staff"]
    calls = [
        anon.get("/admin/role-mgmt/roles/"),
        anon.post("/admin/role-mgmt/", json={"name": "tenadm_x", "description": "x"}),
        anon.put(f"/admin/role-mgmt/{rid}", json={}),
        anon.delete(f"/admin/role-mgmt/{rid}"),
        anon.get(f"/admin/role-mgmt/{rid}/delete-validation"),
        anon.post("/auth/roles/roles/", json={"name": "tenadm_x"}),
        anon.get("/auth/roles/roles/"),
    ]
    for response in calls:
        assert response.status_code == 401
        assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-14-A35")
def test_roles_of_other_tenant_invisible(admin, tenant_b, cleanup):
    foreign = new_role(tenant_b, cleanup)
    names = [r["name"] for r in admin.get("/admin/role-mgmt/roles/").json()["roles"]]
    assert foreign["name"] not in names
    response = admin.delete(f"/admin/role-mgmt/{foreign['id']}")
    assert response.status_code == 404
    assert foreign["id"] in [r["id"] for r in tenant_b.get("/admin/role-mgmt/roles/").json()["roles"]]
