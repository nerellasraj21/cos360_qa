import os
import uuid

import pytest

from api_tests.auth.helpers import (
    claims_of,
    create_staff_user,
    detail_text,
    fresh_login,
    grant_permission,
    rand_phone,
)
from api_tests.support import QA_TENANT, Api, unique
from api_tests.tenants_admin.conftest import MISSING_AUTH, NON_ADMIN, ROLES, denied_text

USER_KEYS = {
    "id",
    "username",
    "email",
    "is_active",
    "role_id",
    "role_name",
    "entity_type",
    "entity_id",
    "entity_name",
    "entity_details",
    "created_at",
    "updated_at",
}


@pytest.fixture(scope="module")
def five_users(admin, role_ids):
    tag = unique("tenusr_")
    created = []
    for index in range(5):
        email = f"{tag}{index}@example.com"
        response = admin.post(
            "/staff/enrollment",
            json={
                "first_name": f"Usr{index}",
                "email": email,
                "phone": rand_phone(),
                "address": "x",
                "role_id": role_ids["Staff"],
            },
        )
        assert response.status_code in (200, 201), response.text
        created.append(response.json())
    yield tag, created
    for item in created:
        admin.delete(f"/staff/enrollment/{item['id']}")
        admin.patch(f"/admin/users/{item['user_id']}", json={"is_active": False})


@pytest.fixture
def temp_user(new_staff):
    return new_staff("Staff")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A01")
def test_list_users_shape(admin, superadmin, tenant_id):
    response = admin.get("/admin/users/")
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1 and body["limit"] == 50
    assert set(body) == {"users", "total", "page", "limit", "total_pages"}
    counted = superadmin.get(f"/super_admin/tenant-data/{tenant_id}/users/", params={"limit": 1}).json()["total_count"]
    assert abs(body["total"] - counted) <= 5
    for user in body["users"]:
        assert set(user) == USER_KEYS
        assert user["created_at"] is None and user["updated_at"] is None


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A01")
def test_list_sorted_by_username(admin, five_users):
    tag, _ = five_users
    names = [u["username"] for u in admin.get("/admin/users/", params={"search": tag}).json()["users"]]
    assert names == sorted(names)
    assert len(names) == 5


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A02")
def test_role_filter(admin):
    body = admin.get("/admin/users/", params={"role": "Student", "limit": 100}).json()
    assert body["users"] and all(u["role_name"] == "Student" for u in body["users"])


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A03")
def test_unknown_role_filter_empty(admin):
    body = admin.get("/admin/users/", params={"role": "NoSuchRole"}).json()
    assert body["users"] == [] and body["total"] == 0 and body["total_pages"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A04")
def test_inactive_filter(admin, temp_user):
    assert admin.patch(f"/admin/users/{temp_user.user_id}", json={"is_active": False}).status_code == 200
    body = admin.get("/admin/users/", params={"is_active": "false", "limit": 100}).json()
    assert body["users"] and all(u["is_active"] is False for u in body["users"])
    assert temp_user.user_id in [u["id"] for u in admin.get("/admin/users/", params={"is_active": "false", "search": temp_user.username}).json()["users"]]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A05")
def test_search_is_case_insensitive(admin, five_users):
    tag, _ = five_users
    lower = admin.get("/admin/users/", params={"search": tag.lower()}).json()
    upper = admin.get("/admin/users/", params={"search": tag.upper()}).json()
    assert lower["total"] == upper["total"] == 5
    assert [u["id"] for u in lower["users"]] == [u["id"] for u in upper["users"]]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A06")
def test_search_does_not_match_names(admin, new_family):
    family = new_family()
    body = admin.get("/admin/users/", params={"search": f"Kid{family.tag}"}).json()
    assert body["users"] == []


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A07")
def test_percent_search_matches_everything(admin):
    for _ in range(5):
        everything = admin.get("/admin/users/", params={"limit": 1}).json()["total"]
        wildcard = admin.get("/admin/users/", params={"search": "%", "limit": 1}).json()["total"]
        if wildcard == everything:
            break
    assert wildcard == everything


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A08")
def test_second_page_of_two(admin, five_users):
    tag, _ = five_users
    everything = [u["id"] for u in admin.get("/admin/users/", params={"search": tag}).json()["users"]]
    page = admin.get("/admin/users/", params={"search": tag, "limit": 2, "page": 2}).json()
    assert [u["id"] for u in page["users"]] == everything[2:4]
    assert page["total_pages"] == 3 and page["total"] == 5 and page["page"] == 2


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A09")
def test_page_beyond_the_last(admin, five_users):
    tag, _ = five_users
    body = admin.get("/admin/users/", params={"search": tag, "page": 99}).json()
    assert body["users"] == [] and body["total"] == 5


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A10")
@pytest.mark.parametrize("params", [{"page": 0}, {"limit": 0}, {"limit": 101}])
def test_pagination_bounds_422(admin, params):
    assert admin.get("/admin/users/", params=params).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A10")
def test_limit_100_accepted(admin):
    assert admin.get("/admin/users/", params={"limit": 100}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A11")
def test_entity_resolution(admin, new_family, new_staff):
    family = new_family()
    staff = new_staff("Staff")
    student = admin.get("/admin/users/", params={"search": family.admission_number}).json()["users"][0]
    assert student["entity_type"] == "student" and student["entity_id"] == family.student_id
    assert student["entity_name"].startswith(f"Kid{family.tag}")
    assert {"date_of_birth", "gender", "aadhar_number", "nationality"} <= set(student["entity_details"])
    parent = admin.get("/admin/users/", params={"search": family.father_email}).json()["users"][0]
    assert parent["entity_type"] == "parent" and parent["entity_id"]
    assert {"phone", "occupation", "relation", "aadhar_number"} <= set(parent["entity_details"])
    person = admin.get("/admin/users/", params={"search": staff.username}).json()["users"][0]
    assert person["entity_type"] == "staff" and person["entity_id"] == staff.staff_id
    assert {"designation", "joining_date", "phone", "qualification", "experience_years"} <= set(person["entity_details"])


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A12")
def test_single_student_user_details(admin, new_family):
    family = new_family()
    listed = admin.get("/admin/users/", params={"search": family.admission_number}).json()["users"][0]
    response = admin.get(f"/admin/users/{listed['id']}")
    assert response.status_code == 200
    details = response.json()["entity_details"]
    assert {"caste", "community", "mother_tongue"} <= set(details)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A13")
def test_unknown_user_404(admin):
    uid = str(uuid.uuid4())
    response = admin.get(f"/admin/users/{uid}")
    assert response.status_code == 404
    assert detail_text(response) == f"User with ID {uid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A14")
def test_malformed_user_id_422(admin):
    assert admin.get("/admin/users/abc").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A15")
def test_patch_username_and_email(admin, temp_user):
    username = unique("tenadm_ren_")
    response = admin.patch(
        f"/admin/users/{temp_user.user_id}", json={"username": username, "email": f"{username}@example.com"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == username and body["email"] == f"{username}@example.com"
    assert admin.get(f"/admin/users/{temp_user.user_id}").json()["username"] == username


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A16")
def test_patch_username_taken_400(admin, temp_user, logins):
    taken = logins["staff"]["user"]["username"]
    response = admin.patch(f"/admin/users/{temp_user.user_id}", json={"username": taken})
    assert response.status_code == 400
    assert detail_text(response) == f"Username '{taken}' already exists"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A17")
def test_patch_email_taken_400(admin, temp_user, logins):
    taken = logins["staff"]["user"]["email"]
    response = admin.patch(f"/admin/users/{temp_user.user_id}", json={"email": taken})
    assert response.status_code == 400
    assert detail_text(response) == f"Email '{taken}' already exists"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A18")
def test_patch_empty_or_unchanged(admin, temp_user):
    before = admin.get(f"/admin/users/{temp_user.user_id}").json()
    empty = admin.patch(f"/admin/users/{temp_user.user_id}", json={})
    same = admin.patch(
        f"/admin/users/{temp_user.user_id}", json={"username": before["username"], "email": before["email"]}
    )
    assert empty.status_code == 200 and same.status_code == 200
    for response in (empty, same):
        assert response.json()["username"] == before["username"]
        assert response.json()["email"] == before["email"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A19")
@pytest.mark.parametrize(
    "body", [{"username": "ab"}, {"username": "u" * 51}, {"email": "bad"}], ids=["short", "long", "email"]
)
def test_patch_validation_422(admin, temp_user, body):
    assert admin.patch(f"/admin/users/{temp_user.user_id}", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A20")
def test_deactivation_blocks_login_and_refresh(admin, temp_user, year_id):
    data = temp_user.activate()
    assert admin.patch(f"/admin/users/{temp_user.user_id}", json={"is_active": False}).status_code == 200
    login = fresh_login(temp_user.username, temp_user.password, year_id)
    assert login.status_code == 401
    assert detail_text(login) == "Invalid Credentials"
    client = Api(tenant_header=QA_TENANT)
    try:
        refreshed = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
    finally:
        client.close()
    assert refreshed.status_code == 401
    assert detail_text(refreshed) == "Account is inactive. Please contact the administrator."


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A21")
def test_reactivation_restores_login(admin, temp_user, year_id):
    temp_user.activate()
    admin.patch(f"/admin/users/{temp_user.user_id}", json={"is_active": False})
    assert admin.patch(f"/admin/users/{temp_user.user_id}", json={"is_active": True}).status_code == 200
    assert fresh_login(temp_user.username, temp_user.password, year_id).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A22")
def test_username_unique_per_tenant(admin, temp_user, tenant_b):
    other_tenant_name = os.environ["QA_B_ADMIN_USER"]
    assert any(
        u["username"] == other_tenant_name for u in tenant_b.get("/admin/users/", params={"search": other_tenant_name}).json()["users"]
    )
    original = temp_user.username
    response = admin.patch(f"/admin/users/{temp_user.user_id}", json={"username": other_tenant_name})
    try:
        assert response.status_code == 200
    finally:
        admin.patch(f"/admin/users/{temp_user.user_id}", json={"username": original})


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A23")
def test_admin_can_deactivate_itself(new_staff, api_client):
    user = new_staff("Admin")
    data = user.activate()
    client = api_client(token=data["access_token"])
    response = client.patch(f"/admin/users/{data['user']['id']}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A24")
def test_role_change(admin, temp_user, role_ids):
    response = admin.put(f"/admin/users/{temp_user.user_id}/role", json={"role_id": role_ids["Teacher"]})
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "User role updated successfully"
    assert body["user_id"] == temp_user.user_id
    assert body["old_role"] == {"id": role_ids["Staff"], "name": "Staff"}
    assert body["new_role"] == {"id": role_ids["Teacher"], "name": "Teacher"}
    assert admin.get(f"/admin/users/{temp_user.user_id}").json()["role_name"] == "Teacher"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A25")
def test_old_token_keeps_old_role_until_refresh(admin, temp_user, role_ids):
    data = temp_user.activate()
    admin.put(f"/admin/users/{temp_user.user_id}/role", json={"role_id": role_ids["Teacher"]})
    client = Api(tenant_header=QA_TENANT)
    try:
        refreshed = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]}).json()
    finally:
        client.close()
    assert claims_of(data["access_token"])["role"] == "Staff"
    assert claims_of(refreshed["access_token"])["role"] == "Teacher"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A26")
def test_role_change_unknown_role_or_user_404(admin, temp_user, role_ids):
    rid, uid = str(uuid.uuid4()), str(uuid.uuid4())
    bad_role = admin.put(f"/admin/users/{temp_user.user_id}/role", json={"role_id": rid})
    assert bad_role.status_code == 404
    assert detail_text(bad_role) == f"Role with ID {rid} not found"
    bad_user = admin.put(f"/admin/users/{uid}/role", json={"role_id": role_ids["Teacher"]})
    assert bad_user.status_code == 404
    assert detail_text(bad_user) == f"User with ID {uid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A27")
def test_role_change_malformed_role_422(admin, temp_user):
    assert admin.put(f"/admin/users/{temp_user.user_id}/role", json={"role_id": "abc"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A28")
def test_reset_password_response(admin, temp_user):
    response = admin.post(f"/admin/users/{temp_user.user_id}/reset-password", json={"new_password": "Reset#2026"})
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == f"Password reset successfully for user {temp_user.username}"
    assert body["user_id"] == temp_user.user_id and body["username"] == temp_user.username


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A29")
def test_login_after_reset(admin, temp_user, year_id):
    temp_user.activate()
    old = temp_user.password
    admin.post(f"/admin/users/{temp_user.user_id}/reset-password", json={"new_password": "Reset#2026"})
    fresh = fresh_login(temp_user.username, "Reset#2026", year_id)
    assert fresh.status_code == 200
    assert fresh.json().get("requires_password_change") is not True
    assert fresh_login(temp_user.username, old, year_id).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A30")
def test_reset_password_length_boundary(admin, temp_user):
    url = f"/admin/users/{temp_user.user_id}/reset-password"
    assert admin.post(url, json={"new_password": "short7!"}).status_code == 422
    assert admin.post(url, json={"new_password": "Eight#8!"}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A31")
def test_reset_unknown_user_404(admin):
    uid = str(uuid.uuid4())
    response = admin.post(f"/admin/users/{uid}/reset-password", json={"new_password": "Reset#2026"})
    assert response.status_code == 404
    assert detail_text(response) == f"User with ID {uid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A32")
def test_tokens_survive_admin_reset(admin, temp_user, api_client):
    data = temp_user.activate()
    admin.post(f"/admin/users/{temp_user.user_id}/reset-password", json={"new_password": "Reset#2026"})
    assert api_client(token=data["access_token"]).get("/auth/available-resources").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A33")
def test_filter_options(admin, role_ids):
    response = admin.get("/admin/users/filters/options")
    assert response.status_code == 200
    body = response.json()
    assert body["available_roles"] == sorted(body["available_roles"], key=str.lower)
    assert {"Admin", "Teacher", "Staff", "Student", "Parent"} <= set(body["available_roles"])
    assert body["default_limit"] == 50 and body["max_limit"] == 100
    assert body["active_status_options"] == [True, False]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A34")
@pytest.mark.parametrize("role", ROLES)
def test_list_and_options_matrix(role_clients, logins, role):
    for path in ("/admin/users/", "/admin/users/filters/options"):
        response = role_clients[role].get(path)
        if role == "admin":
            assert response.status_code == 200
        else:
            assert response.status_code == 403
            assert detail_text(response) == denied_text(logins[role]["role"]["name"], "list", "user_management")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A35")
@pytest.mark.parametrize("role", ROLES)
def test_single_user_matrix(role_clients, logins, role, temp_user):
    response = role_clients[role].get(f"/admin/users/{temp_user.user_id}")
    if role == "admin":
        assert response.status_code == 200
    else:
        assert response.status_code == 403
        assert detail_text(response) == denied_text(logins[role]["role"]["name"], "read", "user_management")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A36")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_update_matrix_denied(role_clients, logins, role, temp_user, role_ids):
    client = role_clients[role]
    expected = denied_text(logins[role]["role"]["name"], "update", "user_management")
    calls = [
        client.patch(f"/admin/users/{temp_user.user_id}", json={"is_active": True}),
        client.put(f"/admin/users/{temp_user.user_id}/role", json={"role_id": role_ids["Staff"]}),
        client.post(f"/admin/users/{temp_user.user_id}/reset-password", json={"new_password": "Reset#2026"}),
    ]
    for response in calls:
        assert response.status_code == 403
        assert detail_text(response) == expected


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A36")
def test_update_endpoints_allowed_for_admin(admin, temp_user, role_ids):
    assert admin.patch(f"/admin/users/{temp_user.user_id}", json={"is_active": True}).status_code == 200
    assert admin.put(f"/admin/users/{temp_user.user_id}/role", json={"role_id": role_ids["Staff"]}).status_code == 200
    assert admin.post(f"/admin/users/{temp_user.user_id}/reset-password", json={"new_password": "Reset#2026"}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A37")
def test_no_create_or_delete_endpoint(admin, temp_user):
    assert admin.post("/admin/users/", json={"username": "nobody"}).status_code == 405
    assert admin.delete(f"/admin/users/{temp_user.user_id}").status_code == 405


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A38")
def test_every_user_endpoint_requires_token(anon, role_ids):
    uid = str(uuid.uuid4())
    calls = [
        anon.get("/admin/users/"),
        anon.get(f"/admin/users/{uid}"),
        anon.patch(f"/admin/users/{uid}", json={}),
        anon.put(f"/admin/users/{uid}/role", json={"role_id": role_ids["Staff"]}),
        anon.post(f"/admin/users/{uid}/reset-password", json={"new_password": "Reset#2026"}),
        anon.get("/admin/users/filters/options"),
    ]
    for response in calls:
        assert response.status_code == 401
        assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A39")
def test_users_of_other_tenant_invisible(admin, tenant_b):
    foreign = tenant_b.get("/admin/users/", params={"limit": 100}).json()["users"]
    assert foreign
    uid = foreign[0]["id"]
    response = admin.get(f"/admin/users/{uid}")
    assert response.status_code == 404
    assert detail_text(response) == f"User with ID {uid} not found"
    mine = {u["id"] for u in admin.get("/admin/users/", params={"limit": 100}).json()["users"]}
    assert not (mine & {u["id"] for u in foreign})


@pytest.mark.api
@pytest.mark.tc("TC-TEN-13-A40")
def test_custom_role_with_list_and_read_only(admin, cleanup, custom_role, year_id, api_client, temp_user):
    role = custom_role()
    grant_permission(admin, cleanup, role["id"], "user_management", "list")
    grant_permission(admin, cleanup, role["id"], "user_management", "read")
    user = create_staff_user(admin, cleanup, year_id, role_id=role["id"])
    client = api_client(token=user.login_data()["access_token"])
    assert client.get("/admin/users/").status_code == 200
    assert client.get(f"/admin/users/{temp_user.user_id}").status_code == 200
    assert client.patch(f"/admin/users/{temp_user.user_id}", json={"is_active": True}).status_code == 403
