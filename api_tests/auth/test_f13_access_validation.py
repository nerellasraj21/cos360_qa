import uuid

import pytest

from api_tests.auth.helpers import MISSING_AUTH, detail_text

UNRESOLVED = "Could not resolve resource from endpoint or menu item"
NOT_FOUND = "User not found or inactive"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A01")
def test_admin_has_access_to_fee_categories(admin, logins):
    response = admin.post(
        "/auth/validate-access",
        json={"user_id": logins["admin"]["user"]["id"], "endpoint": "/api/v1/fee/categories"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_access"] is True
    assert body["resource"] == "fee_categories"
    assert body["action"] == "list"
    assert body["user_role"] == "Admin"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A02")
def test_user_without_grant_is_denied(admin, new_staff, custom_role):
    role = custom_role()
    user = new_staff("Staff", role_id=role["id"])
    response = admin.post(
        "/auth/validate-access", json={"user_id": user.user_id, "endpoint": "/api/v1/fee/categories"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_access"] is False
    assert body["reason"].startswith(f"Access denied: {role['name']} cannot list fee_categories")


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A03")
def test_menu_item_resolution(admin, logins):
    response = admin.post(
        "/auth/validate-access", json={"user_id": logins["admin"]["user"]["id"], "menu_item": "fee_categories"}
    )
    body = response.json()
    assert response.status_code == 200
    assert body["has_access"] is True
    assert body["action"] == "read"
    assert body["resource"] == "fee_categories"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A04")
def test_unresolvable_endpoint(admin, logins):
    response = admin.post(
        "/auth/validate-access", json={"user_id": logins["admin"]["user"]["id"], "endpoint": "/api/v1/nothing/here"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_access"] is False
    assert body["reason"] == UNRESOLVED


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A05")
def test_random_user_not_found(admin):
    response = admin.post(
        "/auth/validate-access", json={"user_id": str(uuid.uuid4()), "endpoint": "/api/v1/fee/categories"}
    )
    assert response.status_code == 200
    assert response.json()["has_access"] is False
    assert response.json()["reason"] == NOT_FOUND


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A06")
def test_deactivated_user_not_found(admin, new_staff):
    user = new_staff("Staff")
    assert admin.patch(f"/admin/users/{user.user_id}", json={"is_active": False}).status_code == 200
    response = admin.post("/auth/validate-access", json={"user_id": user.user_id, "endpoint": "/api/v1/fee/categories"})
    assert response.json()["reason"] == NOT_FOUND
    assert response.json()["has_access"] is False


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A07")
def test_bogus_action_422(admin, logins):
    response = admin.post(
        "/auth/validate-access",
        json={"user_id": logins["admin"]["user"]["id"], "endpoint": "/api/v1/fee/categories", "action": "bogus"},
    )
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A08")
def test_any_authenticated_user_may_ask(staff, logins):
    response = staff.post(
        "/auth/validate-access",
        json={"user_id": logins["admin"]["user"]["id"], "endpoint": "/api/v1/fee/categories"},
    )
    assert response.status_code == 200
    assert response.json()["has_access"] is True


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A09")
def test_validate_endpoint_access(admin, logins):
    user_id = logins["admin"]["user"]["id"]
    response = admin.post(
        "/auth/validate-endpoint-access", params={"user_id": user_id, "endpoint": "/api/v1/fee/types"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "has_access": True,
        "user_id": user_id,
        "endpoint": "/api/v1/fee/types",
        "action": "read",
        "http_method": "GET",
    }


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A10")
def test_validate_menu_access_denied_for_student(admin, new_staff, custom_role, logins):
    response = admin.post(
        "/auth/validate-menu-access", params={"user_id": logins["student"]["user"]["id"], "menu_item": "fee_categories"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_access"] is False
    assert body["menu_item"] == "fee_categories"
    assert body["action"] == "read"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A11")
def test_available_resources_totals(admin):
    response = admin.get("/auth/available-resources")
    assert response.status_code == 200
    body = response.json()
    assert body["total_resources"] == len(body["resources"])
    assert body["total_actions"] == 9 == len(body["actions"])


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A12")
def test_validation_endpoints_require_token(anon):
    uid = str(uuid.uuid4())
    calls = [
        anon.post("/auth/validate-access", json={"user_id": uid, "endpoint": "/api/v1/fee/types"}),
        anon.post("/auth/validate-endpoint-access", params={"user_id": uid, "endpoint": "/api/v1/fee/types"}),
        anon.post("/auth/validate-menu-access", params={"user_id": uid, "menu_item": "fee_categories"}),
        anon.get("/auth/available-resources"),
    ]
    for response in calls:
        assert response.status_code == 401
        assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A13")
def test_user_of_other_tenant_not_found(admin, tenant_b):
    other = tenant_b.get("/admin/users/").json()["users"][0]["id"]
    response = admin.post("/auth/validate-access", json={"user_id": other, "endpoint": "/api/v1/fee/categories"})
    assert response.status_code == 200
    assert response.json()["has_access"] is False
    assert response.json()["reason"] == NOT_FOUND


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-13-A14")
def test_neither_endpoint_nor_menu(admin, logins):
    response = admin.post("/auth/validate-access", json={"user_id": logins["admin"]["user"]["id"]})
    assert response.status_code == 200
    assert response.json()["has_access"] is False
    assert response.json()["reason"] == UNRESOLVED
