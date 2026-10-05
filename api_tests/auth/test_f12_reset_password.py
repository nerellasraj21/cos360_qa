import pytest

from api_tests.auth.helpers import PERMISSION_DENIED_PREFIX, detail_text, fresh_login


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-12-A01")
@pytest.mark.parametrize("path", ["/auth/forgot-password", "/auth/reset-password"])
def test_no_self_service_reset_routes(anon, path):
    response = anon.post(path, json={"username": "x"})
    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-12-A02")
def test_admin_reset_then_login_without_challenge(admin, new_staff, year_id):
    user = new_staff("Staff")
    user.activate()
    response = admin.post(f"/admin/users/{user.user_id}/reset-password", json={"new_password": "Reset#2026"})
    assert response.status_code == 200
    login = fresh_login(user.username, "Reset#2026", year_id)
    assert login.status_code == 200
    body = login.json()
    assert body["access_token"]
    assert body.get("requires_password_change") is not True


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-12-A03")
def test_old_password_fails_after_reset(admin, new_staff, year_id):
    user = new_staff("Staff")
    user.activate()
    old = user.password
    assert admin.post(f"/admin/users/{user.user_id}/reset-password", json={"new_password": "Reset#2026"}).status_code == 200
    response = fresh_login(user.username, old, year_id)
    assert response.status_code == 401
    assert detail_text(response) == "Invalid Credentials"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-12-A04")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_reset_denied_for_non_admin(role_clients, new_staff, role, logins):
    user = new_staff("Staff")
    response = role_clients[role].post(f"/admin/users/{user.user_id}/reset-password", json={"new_password": "Reset#2026"})
    assert response.status_code == 403
    expected = (
        f"{PERMISSION_DENIED_PREFIX}: {logins[role]['role']['name']} cannot update user_management. "
        "Contact administrator to configure permissions."
    )
    assert detail_text(response) == expected
