import pytest

from api_tests.auth.helpers import PERMISSION_DENIED_PREFIX, TEMP_STAFF_PASSWORD, detail_text, fresh_login, rand_phone
from api_tests.support import unique
from api_tests.tenants_admin import tmp_tenants

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


def walk(items):
    for item in items:
        yield item
        yield from walk(item.get("children") or [])


def paths(menu):
    return {item["path"] for item in walk(menu) if item.get("path")}


def find(menu, path):
    return next((i for i in walk(menu) if i.get("path") == path), None)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-06-A01")
def test_admin_menu_has_administration_and_masters(logins):
    menu = logins["admin"]["menu"]
    assert find(menu, "/admin/users") is not None
    assert find(menu, "/settings/school") is not None
    names = {i["name"] for i in walk(menu)}
    assert "Masters" in names and "Administration" in names
    administration = next(i for i in menu if i["name"] == "Administration")
    child_paths = {c["path"] for c in administration["children"]}
    assert {"/admin/users", "/settings/school"} <= child_paths


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-06-A02")
@pytest.mark.tc("TC-AUTH-06-A03")
@pytest.mark.parametrize("role", ["student", "parent"])
def test_student_and_parent_menus_limited_to_allowlist(logins, role):
    menu = logins[role]["menu"]
    assert menu
    assert paths(menu) <= ALLOWLIST
    names = {i["name"] for i in walk(menu)}
    for forbidden in ("Masters", "Administration", "Transport", "Communication", "Reports"):
        assert forbidden not in names


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-06-A04")
@pytest.mark.parametrize("role", ["staff", "teacher"])
def test_staff_and_teacher_menu_subset_of_admin_with_links(admin, logins, role):
    admin_ids = {i["id"] for i in walk(logins["admin"]["menu"])}
    role_ids_in_menu = {i["id"] for i in walk(logins[role]["menu"])}
    assert role_ids_in_menu <= admin_ids
    role_id = logins[role]["role"]["id"]
    links = admin.get("/auth/permissions/").json()
    viewable = {link["menu_id"] for link in links if link["role_id"] == role_id and link["can_view"]}
    assert role_ids_in_menu <= viewable


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-06-A05")
def test_child_without_parent_link_is_dropped(tmp_main, cleanup):
    admin = tmp_main.admin
    menus = admin.get("/auth/menus/").json()
    by_id = {m["id"]: m for m in menus}
    child = next((m for m in menus if m["parent_id"] and by_id.get(m["parent_id"])), None)
    assert child is not None
    role = admin.post("/admin/role-mgmt/", json={"name": unique("auth_"), "description": "x"})
    assert role.status_code == 201, role.text
    role_id = role.json()["role"]["id"]
    cleanup.add(admin.delete, f"/admin/role-mgmt/{role_id}")
    link = admin.post("/auth/permissions/", json={"role_id": role_id, "menu_id": child["id"], "can_view": True})
    assert link.status_code == 201, link.text
    email = f"{unique('auth_')}@example.com"
    made = admin.post(
        "/staff/enrollment",
        json={"first_name": "T", "email": email, "phone": rand_phone(), "address": "x", "role_id": role_id},
    )
    assert made.status_code in (200, 201), made.text
    cleanup.add(admin.patch, f"/admin/users/{made.json()['user_id']}", json={"is_active": False})
    cleanup.add(admin.delete, f"/staff/enrollment/{made.json()['id']}")
    body = fresh_login(email, TEMP_STAFF_PASSWORD, tmp_main.year_id, tenant=tmp_main.client_name).json()
    assert body.get("access_token")
    assert body["menu"] == []


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-06-A06")
def test_siblings_sorted_by_display_order(logins):
    def check(items):
        orders = [i["display_order"] for i in items]
        assert orders == sorted(orders)
        for item in items:
            check(item.get("children") or [])

    check(logins["admin"]["menu"])
    check(logins["student"]["menu"])


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-06-A07")
def test_custom_role_without_links_has_empty_menu(new_staff, custom_role):
    role = custom_role()
    user = new_staff("Staff", role_id=role["id"])
    assert user.login_data()["menu"] == []


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-06-A08")
def test_plan_without_menus_removes_menu(superadmin, tmp_main, cleanup):
    plan = tmp_tenants.make_plan(superadmin, {"academic_years": ["read", "list"]})
    admin_before = fresh_login(tmp_main.admin_username, tmp_main.admin_password, tmp_main.year_id, tenant=tmp_main.client_name)
    assert admin_before.json()["menu"]
    cleanup.add(superadmin.put, f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": tmp_main.plan_id})
    changed = superadmin.put(f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": plan["id"]})
    assert changed.status_code == 200, changed.text
    after = fresh_login(tmp_main.admin_username, tmp_main.admin_password, tmp_main.year_id, tenant=tmp_main.client_name)
    assert after.status_code == 200
    assert after.json()["menu"] == []


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-06-A09")
def test_role_menu_links_are_tenant_scoped(admin, tenant_b):
    mine = admin.get("/auth/permissions/").json()
    theirs = tenant_b.get("/auth/permissions/").json()
    assert mine and theirs
    assert not ({l["role_id"] for l in mine} & {l["role_id"] for l in theirs})
    assert not ({l["id"] for l in mine} & {l["id"] for l in theirs})


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-06-A10")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher", "student", "parent"])
def test_menu_catalog_list_matrix(role_clients, role):
    response = role_clients[role].get("/auth/menus/")
    if role == "admin":
        assert response.status_code == 200
        assert {"id", "name", "url", "level", "parent_id"} <= set(response.json()[0])
    else:
        assert response.status_code == 403
        assert detail_text(response).startswith(PERMISSION_DENIED_PREFIX)
        assert "menu_management" in detail_text(response)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-06-A10")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_menu_catalog_create_denied_for_non_admin(role_clients, role):
    response = role_clients[role].post("/auth/menus/", json={"name": "x", "level": "L0"})
    assert response.status_code == 403
    assert "create menu_management" in detail_text(response)
