import time

import pytest

from api_tests.auth.helpers import claims_of, detail_text, mint
from api_tests.support import QA_B_TENANT, QA_TENANT, Api


@pytest.fixture
def session_user(new_staff):
    user = new_staff("Staff")
    data = user.activate()
    return user, data


@pytest.fixture
def refresh_client():
    client = Api(tenant_header=QA_TENANT)
    yield client
    client.close()


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A01")
def test_refresh_issues_new_tokens(session_user, refresh_client):
    _, data = session_user
    time.sleep(1.2)
    response = refresh_client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] != data["access_token"]
    assert body["refresh_token"] != data["refresh_token"]
    assert body["expires_in"] == 86400
    assert body["token_type"] == "bearer"
    assert body["academic_year_id"] == data["academic_year_id"]
    assert body["academic_year_title"] == data["academic_year_title"]
    assert "tenant_id" not in body and "client_name" not in body


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A02")
def test_new_access_token_works(session_user, refresh_client, api_client):
    _, data = session_user
    body = refresh_client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]}).json()
    assert api_client(token=body["access_token"]).get("/auth/available-resources").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A03")
def test_new_access_token_claims(session_user, refresh_client):
    _, data = session_user
    time.sleep(1.2)
    body = refresh_client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]}).json()
    old, new = claims_of(data["access_token"]), claims_of(body["access_token"])
    for key in ("sub", "tenant_id", "client_name", "academic_year_id", "academic_year_title", "role"):
        assert new[key] == old[key]
    assert new["exp"] > old["exp"]


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A04")
def test_refresh_token_is_not_rotated(session_user, refresh_client):
    _, data = session_user
    assert refresh_client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]}).status_code == 200
    assert refresh_client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A05")
def test_role_change_visible_after_refresh(admin, role_ids, session_user, refresh_client):
    user, data = session_user
    changed = admin.put(f"/admin/users/{user.user_id}/role", json={"role_id": role_ids["Teacher"]})
    assert changed.status_code == 200, changed.text
    body = refresh_client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]}).json()
    assert claims_of(body["access_token"])["role"] == "Teacher"
    assert claims_of(data["access_token"])["role"] == "Staff"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A06")
def test_deactivated_user_cannot_refresh(admin, session_user, refresh_client):
    user, data = session_user
    assert admin.patch(f"/admin/users/{user.user_id}", json={"is_active": False}).status_code == 200
    response = refresh_client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert response.status_code == 401
    assert detail_text(response) == "Account is inactive. Please contact the administrator."


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A07")
def test_refresh_after_logout_rejected(session_user, refresh_client, api_client):
    _, data = session_user
    out = api_client(token=data["access_token"]).post("/auth/logout", json={"refresh_token": data["refresh_token"]})
    assert out.status_code == 200
    response = refresh_client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert response.status_code == 401
    assert detail_text(response) == "Refresh token has been invalidated. Please login again."


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A08")
def test_refresh_with_access_token_401(session_user, refresh_client):
    _, data = session_user
    response = refresh_client.post("/auth/refresh", json={"refresh_token": data["access_token"]})
    assert response.status_code == 401
    assert detail_text(response) == "Invalid token type"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A09")
def test_refresh_with_random_string_401(refresh_client):
    response = refresh_client.post("/auth/refresh", json={"refresh_token": "not-a-jwt-at-all"})
    assert response.status_code == 401
    assert detail_text(response) == "Invalid refresh token"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A10")
def test_expired_refresh_token_401(session_user, refresh_client):
    _, data = session_user
    claims = claims_of(data["refresh_token"])
    claims.pop("exp")
    claims.pop("token_type")
    expired = mint(claims, token_type="refresh", expires_in=-60)
    response = refresh_client.post("/auth/refresh", json={"refresh_token": expired})
    assert response.status_code == 401
    assert detail_text(response) == "Invalid refresh token"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A11")
def test_refresh_with_other_tenant_header_403(session_user, tenant_b):
    _, data = session_user
    client = Api(tenant_header=QA_B_TENANT)
    try:
        response = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
    finally:
        client.close()
    assert response.status_code == 403
    assert detail_text(response) == "Tenant does not match your session"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A12")
def test_refresh_token_without_tenant_claim(session_user, refresh_client):
    user, data = session_user
    token = mint({"sub": user.user_id, "username": user.username, "role": "Staff"}, token_type="refresh", expires_in=3600)
    response = refresh_client.post("/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401
    assert detail_text(response) == "Your session is out of date. Please log in again."


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A13")
def test_refresh_without_header_rejected(session_user):
    _, data = session_user
    client = Api()
    try:
        response = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
    finally:
        client.close()
    assert response.status_code >= 400
    assert "access_token" not in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A14")
def test_refresh_body_requires_token(refresh_client):
    response = refresh_client.post("/auth/refresh", json={})
    assert response.status_code == 422
    assert "refresh_token" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A15")
def test_super_admin_refresh_token_rejected(superadmin, refresh_client):
    import os

    anon = Api()
    try:
        login = anon.post(
            "/super_admin/auth/login",
            json={"username": os.environ["QA_SUPERADMIN_USER"], "password": os.environ["QA_SUPERADMIN_PASSWORD"]},
        ).json()
    finally:
        anon.close()
    response = refresh_client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 401
    assert detail_text(response) == "Your session is out of date. Please log in again."


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A16")
def test_expired_access_token_401(session_user, api_client):
    _, data = session_user
    claims = claims_of(data["access_token"])
    claims.pop("exp")
    claims.pop("token_type")
    expired = mint(claims, token_type="access", expires_in=-60)
    response = api_client(token=expired).get("/auth/available-resources")
    assert response.status_code == 401
    assert detail_text(response) == "Invalid token"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-08-A17")
def test_refresh_for_deactivated_tenant_404(tmp_main):
    data = tmp_main.admin_login()
    tmp_main.set_active(False)
    try:
        client = tmp_main.anon()
        try:
            response = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
        finally:
            client.close()
        assert response.status_code == 404
        assert detail_text(response) == f"Tenant '{tmp_main.client_name}' not found or inactive"
    finally:
        tmp_main.set_active(True)
