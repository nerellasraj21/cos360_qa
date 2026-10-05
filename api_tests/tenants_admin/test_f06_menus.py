import uuid

import pytest

from api_tests.auth.helpers import TEMP_STAFF_PASSWORD, detail_text, fresh_login, rand_phone
from api_tests.support import unique
from api_tests.tenants_admin.conftest import MISSING_AUTH, NON_ADMIN, ROLES, denied_text


def top_level_menu(admin):
    menus = admin.get("/auth/menus/").json()
    return next(m for m in menus if m["level"] == "L0" and m["url"] == "/dashboard")


def make_role_user(tmp_main, cleanup, role):
    admin = tmp_main.admin
    email = f"{unique('tenadm_')}@example.com"
    made = admin.post(
        "/staff/enrollment",
        json={"first_name": "T", "email": email, "phone": rand_phone(), "address": "x", "role_id": role["id"]},
    )
    assert made.status_code in (200, 201), made.text
    cleanup.add(admin.patch, f"/admin/users/{made.json()['user_id']}", json={"is_active": False})
    cleanup.add(admin.delete, f"/staff/enrollment/{made.json()['id']}")
    return email


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A01")
@pytest.mark.tc("TC-TEN-06-A02")
@pytest.mark.skip(reason="blocked: POST /auth/menus/ writes to the shared menu catalog, which the task forbids modifying, and menu rows have no delete endpoint")
def test_admin_creates_menu_and_child():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A03")
def test_create_menu_without_level_422(admin):
    response = admin.post("/auth/menus/", json={"name": "tenadm_nolevel", "path": "/x", "icon": "i", "order": 1})
    assert response.status_code == 422
    assert "level" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A04")
def test_create_menu_with_unknown_parent_rejected(admin):
    name = unique("tenadm_")
    response = admin.post(
        "/auth/menus/", json={"name": name, "url": "/" + name, "level": "L1", "parent_id": str(uuid.uuid4())}
    )
    assert response.status_code == 400
    assert name not in [m["name"] for m in admin.get("/auth/menus/").json()]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A05")
def test_create_menu_with_long_level_rejected(admin):
    name = unique("tenadm_")
    response = admin.post("/auth/menus/", json={"name": name, "url": "/" + name, "level": "L10"})
    assert not response.is_success
    assert name not in [m["name"] for m in admin.get("/auth/menus/").json()]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A06")
def test_create_menu_with_51_character_name_rejected(admin):
    name = "tenadm_" + "z" * 44
    response = admin.post("/auth/menus/", json={"name": name, "url": "/x", "level": "L0"})
    assert not response.is_success
    assert name not in [m["name"] for m in admin.get("/auth/menus/").json()]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A07")
def test_list_menus_shape(admin):
    response = admin.get("/auth/menus/")
    assert response.status_code == 200
    menus = response.json()
    assert len(menus) >= 70
    for menu in menus:
        assert {"id", "name", "url", "level", "parent_id"} <= set(menu)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A08")
def test_catalog_is_shared_between_tenants(admin, tenant_b):
    mine = {m["id"] for m in admin.get("/auth/menus/").json()}
    theirs = {m["id"] for m in tenant_b.get("/auth/menus/").json()}
    assert mine == theirs


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A09")
@pytest.mark.parametrize("role", ROLES)
def test_menu_catalog_matrix(role_clients, logins, role):
    list_response = role_clients[role].get("/auth/menus/")
    if role == "admin":
        assert list_response.status_code == 200
    else:
        create_response = role_clients[role].post("/auth/menus/", json={"name": "x", "level": "L0"})
        assert list_response.status_code == 403
        assert detail_text(list_response) == denied_text(logins[role]["role"]["name"], "list", "menu_management")
        assert create_response.status_code == 403
        assert detail_text(create_response) == denied_text(logins[role]["role"]["name"], "create", "menu_management")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A10")
def test_link_role_to_menu(tmp_main, custom_role):
    admin = tmp_main.admin
    role = custom_role(client=admin)
    menu = top_level_menu(admin)
    response = admin.post("/auth/permissions/", json={"role_id": role["id"], "menu_id": menu["id"]})
    assert response.status_code == 201
    body = response.json()
    assert body["role_id"] == role["id"] and body["menu_id"] == menu["id"]
    assert body["can_view"] is True
    assert body["can_edit"] is False


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A11")
def test_duplicate_link_400(tmp_main, custom_role):
    admin = tmp_main.admin
    role = custom_role(client=admin)
    payload = {"role_id": role["id"], "menu_id": top_level_menu(admin)["id"]}
    assert admin.post("/auth/permissions/", json=payload).status_code == 201
    assert admin.post("/auth/permissions/", json=payload).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A12")
def test_link_with_unknown_role_400(tmp_main):
    admin = tmp_main.admin
    response = admin.post(
        "/auth/permissions/", json={"role_id": str(uuid.uuid4()), "menu_id": top_level_menu(admin)["id"]}
    )
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A13")
def test_list_links_tenant_scoped(tmp_main, admin, custom_role):
    mine = tmp_main.admin
    role = custom_role(client=mine)
    link = mine.post("/auth/permissions/", json={"role_id": role["id"], "menu_id": top_level_menu(mine)["id"]}).json()
    links = mine.get("/auth/permissions/")
    assert links.status_code == 200
    assert link["id"] in [item["id"] for item in links.json()]
    other_roles = {item["role_id"] for item in admin.get("/auth/permissions/").json()}
    assert role["id"] not in other_roles
    assert not ({item["role_id"] for item in links.json()} & other_roles)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A14")
def test_linked_menu_appears_for_role_user(tmp_main, custom_role, cleanup):
    admin = tmp_main.admin
    role = custom_role(client=admin)
    menu = top_level_menu(admin)
    admin.post("/auth/permissions/", json={"role_id": role["id"], "menu_id": menu["id"]})
    email = make_role_user(tmp_main, cleanup, role)
    body = fresh_login(email, TEMP_STAFF_PASSWORD, tmp_main.year_id, tenant=tmp_main.client_name).json()
    assert [item["path"] for item in body["menu"]] == ["/dashboard"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A15")
def test_link_without_view_hides_menu(tmp_main, custom_role, cleanup):
    admin = tmp_main.admin
    role = custom_role(client=admin)
    menu = top_level_menu(admin)
    admin.post("/auth/permissions/", json={"role_id": role["id"], "menu_id": menu["id"], "can_view": False})
    email = make_role_user(tmp_main, cleanup, role)
    body = fresh_login(email, TEMP_STAFF_PASSWORD, tmp_main.year_id, tenant=tmp_main.client_name).json()
    assert body["menu"] == []


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A16")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_role_menu_link_matrix_denied(role_clients, logins, role, role_ids):
    name = logins[role]["role"]["name"]
    listed = role_clients[role].get("/auth/permissions/")
    created = role_clients[role].post("/auth/permissions/", json={"role_id": role_ids["Staff"], "menu_id": str(uuid.uuid4())})
    assert listed.status_code == 403
    assert detail_text(listed) == denied_text(name, "list", "permission_management")
    assert created.status_code == 403
    assert detail_text(created) == denied_text(name, "create", "permission_management")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A16")
def test_role_menu_link_list_allowed_for_admin(admin):
    assert admin.get("/auth/permissions/").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-06-A17")
def test_menu_endpoints_require_token(anon, role_ids):
    calls = [
        anon.get("/auth/menus/"),
        anon.post("/auth/menus/", json={"name": "x", "level": "L0"}),
        anon.get("/auth/permissions/"),
        anon.post("/auth/permissions/", json={"role_id": role_ids["Staff"], "menu_id": str(uuid.uuid4())}),
    ]
    for response in calls:
        assert response.status_code == 401
        assert detail_text(response) == MISSING_AUTH
