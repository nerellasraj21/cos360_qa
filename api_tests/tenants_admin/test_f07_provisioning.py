import uuid
from datetime import date

import pytest

from api_tests.auth.helpers import (
    TEMP_STAFF_PASSWORD,
    detail_text,
    fresh_login,
    rand_phone,
    role_id_map,
    set_password,
)
from api_tests.support import login, unique
from api_tests.tenants_admin import tmp_tenants
from api_tests.tenants_admin.conftest import MISSING_AUTH, ROLES, SA_REQUIRED

BAD_NAME = "client_name must be 2-63 characters of lowercase letters, digits, hyphen or underscore"
ALLOWLIST = {
    "/dashboard",
    "/students",
    "/students/admission",
    "/students/attendance",
    "/students/studenttransport",
    "/students/studentdocuments",
    "/students/studentcertificates",
    "/fee",
    "/fee/my-fees",
    "/fee/my-receipts",
    "/exam",
    "/exam/exams",
    "/exam/marks",
    "/exam/hall-tickets",
    "/exam/results",
}


def total_permissions(superadmin, tenant_id):
    roles = superadmin.get(f"/super_admin/tenant-data/{tenant_id}/roles/").json()["roles"]
    return roles, sum(r["permission_count"] for r in roles)


def expected_default_year():
    today = date.today()
    start = today.year if today.month >= 6 else today.year - 1
    return f"{start}-{start + 1}"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A01")
def test_provision_with_admin(superadmin, tmp_main):
    if tmp_main.fresh:
        assert tmp_main.response.status_code == 201
        body = tmp_main.response.json()
        assert body["message"] == "Tenant created successfully"
        assert body["tenant"]["roles"] == 5
        assert body["tenant"]["permissions"] == 455
        assert body["tenant"]["role_menu_links"] == 243
        assert body["tenant"]["admin_user_id"]
        assert tmp_main.created["client_name"] == tmp_main.client_name
    roles, total = total_permissions(superadmin, tmp_main.tenant_id)
    system = {r["name"]: r["permission_count"] for r in roles if r["name"] in ("Admin", "Teacher", "Student", "Parent", "Staff")}
    assert set(system) == {"Admin", "Teacher", "Student", "Parent", "Staff"}
    assert system["Admin"] >= 276
    links = tmp_main.admin.get("/auth/permissions/").json()
    assert len(links) >= 240


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A02")
def test_default_academic_year(tmp_main):
    client = tmp_main.anon()
    try:
        years = client.get("/auth/academic-years").json()
    finally:
        client.close()
    assert len(years) >= 1
    assert expected_default_year() in [y["title"] for y in years]
    assert any(y["is_active"] for y in years)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A03")
def test_provisioned_admin_can_log_in(tmp_main):
    data = tmp_main.admin_login()
    assert data["role"]["name"] == "Admin"
    assert sum(len(a) for a in data["permissions"].values()) >= 276
    assert set(data["permissions"]["role_management"]) == {"create", "read", "update", "delete", "list"}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A04")
def test_five_system_roles(tmp_main):
    roles = tmp_main.admin.get("/admin/role-mgmt/roles/").json()["roles"]
    system = {r["name"]: r for r in roles if r["is_system_role"]}
    assert set(system) == {"Admin", "Parent", "Staff", "Student", "Teacher"}
    for role in system.values():
        assert role["is_system_role"] is True and role["is_custom_role"] is False


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A05")
def test_provision_without_body_equivalent(superadmin, tmp_empty):
    assert tmp_users(superadmin, tmp_empty) == []


def tmp_users(superadmin, tenant):
    return tmp_tenants.tenant_users(superadmin, tenant.tenant_id)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A06")
def test_name_is_stripped_and_lowercased(tmp_edge):
    assert tmp_edge.client_name == tmp_edge.client_name.strip().lower()
    if tmp_edge.fresh:
        assert tmp_edge.created["client_name"] == tmp_edge.client_name


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A07")
def test_one_character_name_400(superadmin, full_plan):
    response = superadmin.post("/super_admin/system/tenants/", params={"client_name": "a", "plan_id": full_plan})
    assert response.status_code == 400
    assert detail_text(response) == BAD_NAME


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A08")
@pytest.mark.parametrize("name", ["-abc", "ab c"])
def test_malformed_names_400(superadmin, full_plan, name):
    response = superadmin.post("/super_admin/system/tenants/", params={"client_name": name, "plan_id": full_plan})
    assert response.status_code == 400
    assert detail_text(response) == BAD_NAME


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A09")
def test_64_character_name_400_and_63_accepted(superadmin, full_plan, tmp_edge):
    response = superadmin.post(
        "/super_admin/system/tenants/", params={"client_name": "q" * 64, "plan_id": full_plan}
    )
    assert response.status_code == 400
    assert detail_text(response) == BAD_NAME
    assert len(tmp_edge.client_name) == 63
    client = tmp_edge.anon()
    try:
        assert client.get("/auth/academic-years").status_code == 200
    finally:
        client.close()


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A10")
@pytest.mark.parametrize("name", ["qa_school_b", "QA_SCHOOL_B"])
def test_existing_tenant_409(superadmin, full_plan, name, tenant_b):
    response = superadmin.post("/super_admin/system/tenants/", params={"client_name": name, "plan_id": full_plan})
    assert response.status_code == 409
    assert detail_text(response) == "Tenant already exists"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A11")
def test_unknown_plan_404(superadmin):
    response = superadmin.post(
        "/super_admin/system/tenants/", params={"client_name": "qa_tmp_" + unique("u"), "plan_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404
    assert detail_text(response) == "Plan not found or inactive"
    names = [t["client_name"] for t in tmp_tenants.tmp_tenant_rows(superadmin)]
    assert not [n for n in names if n.startswith("qa_tmp_u")]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A11")
def test_deactivated_plan_404(superadmin):
    plan = tmp_tenants.make_plan(superadmin)
    superadmin.put(f"/super_admin/plans/{plan['id']}", params={"is_active": "false"})
    response = superadmin.post("/super_admin/system/tenants/", params={"client_name": "qa_tmp_" + unique("d"), "plan_id": plan["id"]})
    assert detail_text(response) == "Plan not found or inactive"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A12")
def test_plan_without_resources_409(superadmin):
    plan = tmp_tenants.make_plan(superadmin)
    name = "qa_tmp_" + unique("r")
    response = superadmin.post("/super_admin/system/tenants/", params={"client_name": name, "plan_id": plan["id"]})
    assert response.status_code == 409
    assert detail_text(response) == "The tenant's plan has no resources configured"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A13")
def test_username_without_password_400(superadmin, full_plan):
    response = superadmin.post(
        "/super_admin/system/tenants/",
        params={"client_name": "qa_tmp_" + unique("g"), "plan_id": full_plan},
        json={"username": "someone", "email": "someone@example.com", "password": ""},
    )
    assert response.status_code == 400
    assert detail_text(response) == "admin_username and admin_password go together"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A14")
def test_body_without_password_key_422(superadmin, full_plan):
    response = superadmin.post(
        "/super_admin/system/tenants/",
        params={"client_name": "qa_tmp_" + unique("g"), "plan_id": full_plan},
        json={"username": "someone", "email": "someone@example.com"},
    )
    assert response.status_code == 422
    assert "password" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A15")
def test_empty_credentials_create_no_admin(superadmin, tmp_empty):
    if tmp_empty.fresh:
        assert tmp_empty.response.status_code == 201
        assert tmp_empty.created["admin_user_id"] is None
    assert tmp_users(superadmin, tmp_empty) == []


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A16")
def test_missing_or_malformed_parameters_422(superadmin, full_plan):
    assert superadmin.post("/super_admin/system/tenants/", params={"plan_id": full_plan}).status_code == 422
    assert (
        superadmin.post("/super_admin/system/tenants/", params={"client_name": "qa_tmp_x", "plan_id": "abc"}).status_code
        == 422
    )


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A17")
def test_short_admin_password_accepted(tmp_edge):
    data = login(tmp_edge.admin_username, tmp_edge.admin_password, tmp_edge.client_name)
    assert data["role"]["name"] == "Admin"
    assert tmp_edge.admin_password == "abc"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A18")
@pytest.mark.skip(reason="blocked: users.password_hash cannot be read through the API and the database must not be touched")
def test_admin_password_is_bcrypt_hash():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A19")
def test_same_username_allowed_in_two_tenants(admin, tmp_main, cleanup):
    email = f"{unique('tenadm_')}@example.com"
    ids = []
    for client in (admin, tmp_main.admin):
        role_id = role_id_map(client)["Staff"]
        made = client.post(
            "/staff/enrollment",
            json={"first_name": "T", "email": email, "phone": rand_phone(), "address": "x", "role_id": role_id},
        )
        assert made.status_code in (200, 201), made.text
        cleanup.add(client.patch, f"/admin/users/{made.json()['user_id']}", json={"is_active": False})
        cleanup.add(client.delete, f"/staff/enrollment/{made.json()['id']}")
        ids.append(made.json()["user_id"])
    assert ids[0] != ids[1]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A20")
@pytest.mark.parametrize("role", ROLES)
def test_provisioning_denied_to_tenant_roles(role_clients, full_plan, role):
    response = role_clients[role].post("/super_admin/system/tenants/", params={"client_name": "a", "plan_id": full_plan})
    assert response.status_code == 403
    assert detail_text(response) == SA_REQUIRED


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A21")
def test_provisioning_requires_token(bare, full_plan):
    response = bare.post("/super_admin/system/tenants/", params={"client_name": "a", "plan_id": full_plan})
    assert response.status_code == 401
    assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A22")
@pytest.mark.skip(reason="blocked: super_admin_audit rows cannot be read through the API and the database must not be touched")
def test_provisioning_audit_row():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A23")
def test_new_tenant_users_not_visible_in_qa_school(admin, tmp_main):
    names = {u["username"] for u in admin.get("/admin/users/?limit=100").json()["users"]}
    assert tmp_main.admin_username not in names
    assert admin.get("/admin/users/", params={"search": tmp_main.admin_username}).json()["users"] == []


@pytest.mark.api
@pytest.mark.tc("TC-TEN-07-A24")
def test_student_menu_in_new_tenant_is_limited(tmp_main, cleanup):
    admin = tmp_main.admin
    role_id = role_id_map(admin)["Student"]
    email = f"{unique('tenadm_')}@example.com"
    made = admin.post(
        "/staff/enrollment",
        json={"first_name": "T", "email": email, "phone": rand_phone(), "address": "x", "role_id": role_id},
    )
    assert made.status_code in (200, 201), made.text
    cleanup.add(admin.patch, f"/admin/users/{made.json()['user_id']}", json={"is_active": False})
    cleanup.add(admin.delete, f"/staff/enrollment/{made.json()['id']}")
    first = fresh_login(email, TEMP_STAFF_PASSWORD, tmp_main.year_id, tenant=tmp_main.client_name).json()
    done = set_password(first["change_password_token"], "Password#11", tenant=tmp_main.client_name).json()

    def walk(items):
        for item in items:
            yield item
            yield from walk(item.get("children") or [])

    paths = {i["path"] for i in walk(done["menu"]) if i.get("path")}
    assert paths and paths <= ALLOWLIST
