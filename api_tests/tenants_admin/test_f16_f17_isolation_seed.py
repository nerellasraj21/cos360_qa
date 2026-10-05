import uuid

import pytest

from api_tests.auth.helpers import MISSING_AUTH, detail_text, fresh_login, rand_phone, role_id_map
from api_tests.support import QA_B_TENANT, QA_TENANT, Api, unique
from api_tests.tenants_admin import tmp_tenants
from api_tests.tenants_admin.conftest import NON_ADMIN, tenant_usernames

BASE = "/super_admin/tenant-data"


def shared_staff(client, cleanup, email):
    made = client.post(
        "/staff/enrollment",
        json={"first_name": "T", "email": email, "phone": rand_phone(), "address": "x", "role_id": role_id_map(client)["Staff"]},
    )
    assert made.status_code in (200, 201), made.text
    cleanup.add(client.patch, f"/admin/users/{made.json()['user_id']}", json={"is_active": False})
    cleanup.add(client.delete, f"/staff/enrollment/{made.json()['id']}")
    return made.json()


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A01")
def test_same_username_listed_only_in_own_tenant(admin, tenant_b, cleanup):
    email = f"{unique('tenadm_')}@example.com"
    mine = shared_staff(admin, cleanup, email)
    theirs = shared_staff(tenant_b, cleanup, email)
    a = admin.get("/admin/users/", params={"search": email}).json()["users"]
    b = tenant_b.get("/admin/users/", params={"search": email}).json()["users"]
    assert [u["id"] for u in a] == [mine["user_id"]]
    assert [u["id"] for u in b] == [theirs["user_id"]]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A02")
def test_user_of_other_tenant_is_404(admin, tenant_b):
    uid = tenant_b.get("/admin/users/").json()["users"][0]["id"]
    response = admin.get(f"/admin/users/{uid}")
    assert response.status_code == 404
    assert detail_text(response) == f"User with ID {uid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A03")
def test_shared_custom_role_name_in_both_tenants(admin, tenant_b, cleanup):
    name = unique("tenadm_shared")
    for client in (admin, tenant_b):
        response = client.post("/admin/role-mgmt/", json={"name": name, "description": "x"})
        assert response.status_code == 201, response.text
        cleanup.add(client.delete, f"/admin/role-mgmt/{response.json()['role']['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A04")
def test_role_lists_are_per_tenant(admin, tenant_b, cleanup):
    name = unique("tenadm_only_b")
    response = tenant_b.post("/admin/role-mgmt/", json={"name": name, "description": "x"})
    cleanup.add(tenant_b.delete, f"/admin/role-mgmt/{response.json()['role']['id']}")
    assert name in [r["name"] for r in tenant_b.get("/admin/role-mgmt/roles/").json()["roles"]]
    assert name not in [r["name"] for r in admin.get("/admin/role-mgmt/roles/").json()["roles"]]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A05")
def test_school_settings_not_shared(tmp_main, admin, tenant_b):
    name = unique("Tenadm School ")
    assert tmp_main.admin.put("/school-settings", json={"school_name": name}).status_code == 200
    for client in (admin, tenant_b):
        response = client.get("/school-settings")
        if response.status_code == 200:
            assert response.json()["school_name"] != name


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A06")
def test_resource_permission_counts_are_per_tenant(admin, tenant_b):
    for client in (admin, tenant_b):
        total = client.get("/auth/resource-permissions/", params={"limit": 1}).json()["total_count"]
        roles = client.get("/admin/role-mgmt/roles/").json()["roles"]
        summed = 0
        for role in roles:
            if not role["is_system_role"]:
                continue
            summary = client.get(f"/auth/resource-permissions/role/{role['id']}/summary")
            assert summary.status_code == 200, summary.text
            summed += summary.json()["total_permissions"]
        assert 0 < summed <= total


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A07")
def test_role_menu_links_are_per_tenant(admin, tenant_b):
    mine = admin.get("/auth/permissions/").json()
    theirs = tenant_b.get("/auth/permissions/").json()
    assert not ({l["id"] for l in mine} & {l["id"] for l in theirs})


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A08")
@pytest.mark.parametrize("path", ["/admin/users/", "/admin/role-mgmt/roles/", "/auth/resource-permissions/", "/school-settings", "/auth/menus/"])
def test_token_replayed_against_other_tenant_header(admin, path):
    response = admin.get(path, headers={"cschema": QA_B_TENANT})
    assert response.status_code == 403
    assert detail_text(response) == "Tenant does not match your session"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A09")
@pytest.mark.tc("TC-TEN-16-A10")
def test_deactivation_locks_out_and_reactivation_restores(tmp_main, superadmin):
    data = tmp_main.admin_login()
    token_client = Api(token=data["access_token"])
    anon = tmp_main.anon()
    try:
        tmp_main.set_active(False)
        try:
            login = anon.post(
                "/auth/login",
                json={"username": tmp_main.admin_username, "password": tmp_main.admin_password, "academic_year_id": tmp_main.year_id},
            )
            assert login.status_code == 404
            assert anon.get("/auth/academic-years").status_code == 404
            old = token_client.get("/admin/users/")
            assert old.status_code == 401 and detail_text(old) == "Invalid connection"
        finally:
            tmp_main.set_active(True)
        assert anon.get("/auth/academic-years").status_code == 200
        assert token_client.get("/admin/users/").status_code == 200
        assert fresh_login(tmp_main.admin_username, tmp_main.admin_password, tmp_main.year_id, tenant=tmp_main.client_name).status_code == 200
    finally:
        token_client.close()
        anon.close()


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A11")
@pytest.mark.tc("TC-TEN-16-A12")
@pytest.mark.tc("TC-TEN-16-A13")
@pytest.mark.tc("TC-TEN-16-A14")
@pytest.mark.skip(reason="blocked: these cases run SQL as the API database role and the task forbids touching the database directly (row-level security is covered by tests/integration/test_tenant_*.py)")
def test_database_level_isolation_checks():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A15")
def test_super_admin_reads_only_path_tenant(superadmin, tenant_id, logins):
    names = set(tenant_usernames(superadmin, tenant_id))
    assert logins["admin"]["user"]["username"] in names
    assert "qa_b_admin" not in names


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A16")
def test_super_admin_alternating_tenants(superadmin, tenant_id, tenant_b_id):
    for _ in range(2):
        a = set(tenant_usernames(superadmin, tenant_id))
        b = set(tenant_usernames(superadmin, tenant_b_id))
        assert "qa_admin" in a and "qa_admin" not in b
        assert "qa_b_admin" in b and "qa_b_admin" not in a


@pytest.mark.api
@pytest.mark.tc("TC-TEN-16-A17")
def test_new_tenant_has_no_foreign_rows(superadmin, tmp_empty):
    students = superadmin.get(f"{BASE}/{tmp_empty.tenant_id}/students/").json()
    assert students["students"] == [] and students["total_count"] == 0
    assert tmp_tenants.tenant_users(superadmin, tmp_empty.tenant_id) == []


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A01")
@pytest.mark.tc("TC-TEN-17-A02")
@pytest.mark.tc("TC-TEN-17-A04")
@pytest.mark.skip(reason="blocked: the seeders write platform-wide public master data (role templates, plan menu links, locations) which the task forbids")
def test_public_seeders_write_platform_data():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A03")
def test_verify_permission_data_is_open(anon):
    response = anon.get("/auth/seed/verify-permission-data")
    assert response.status_code == 200
    assert set(response.json()) == {"role_templates", "academic_menu", "menu_actions", "permission_templates", "plan_access"}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A05")
@pytest.mark.tc("TC-TEN-17-A06")
def test_caste_seed_is_idempotent(tmp_main):
    admin = tmp_main.admin
    first = admin.post("/auth/seed/caste-data")
    assert first.status_code == 201
    assert first.json()["message"] == "Caste data seeded successfully"
    names = {c["name"] for c in admin.get("/masters/castes/", params={"limit": 100}).json()["items"]}
    assert {"General", "OBC", "SC", "ST", "EWS"} <= names
    second = admin.post("/auth/seed/caste-data")
    assert second.status_code == 201
    assert second.json()["details"]["total_castes"] == 0 and second.json()["details"]["total_sub_castes"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A07")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_caste_seed_denied_to_non_admin(role_clients, role):
    response = role_clients[role].post("/auth/seed/caste-data")
    assert response.status_code == 403
    assert detail_text(response) == "Only administrators can seed data"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A08")
def test_caste_seed_requires_token(anon):
    response = anon.post("/auth/seed/caste-data")
    assert response.status_code == 401
    assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A09")
def test_test_route_removed(anon):
    assert anon.get("/admin/role-mgmt/test/").status_code in (404, 405)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A10")
def test_debug_route_removed_for_staff(staff):
    response = staff.get("/admin/role-mgmt/debug-roles/")
    assert response.status_code in (404, 405)
    assert "debug_info" not in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A11")
def test_debug_route_removed_with_garbage_bearer():
    client = Api(token="garbage", tenant_header=QA_TENANT)
    try:
        response = client.get("/admin/role-mgmt/debug-roles/")
    finally:
        client.close()
    assert response.status_code in (404, 405)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A12")
def test_legacy_organisations_list_denied_to_everyone(admin, superadmin):
    for client in (admin, superadmin):
        response = client.get("/superadmin/organizations/")
        assert response.status_code == 403
        assert "cannot list organizations" in detail_text(response)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A13")
def test_legacy_organisation_item_routes_denied(admin):
    assert admin.get("/superadmin/organizations/1").status_code == 403
    assert admin.delete("/superadmin/organizations/1").status_code == 403
    assert admin.put("/superadmin/organizations/1", json={}).status_code in (403, 422)
    assert admin.post("/superadmin/organizations/", json={}).status_code in (403, 422)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-17-A14")
def test_legacy_organisation_uuid_id_422(admin):
    assert admin.get(f"/superadmin/organizations/{uuid.uuid4()}").status_code == 422
