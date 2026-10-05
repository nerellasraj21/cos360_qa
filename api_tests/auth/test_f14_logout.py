import time

import pytest

from api_tests.auth.helpers import MISSING_AUTH, claims_of, detail_text, fresh_login, mint
from api_tests.support import QA_TENANT, Api

LOGOUT_BODY = {"message": "Logout successful", "instructions": {"clear_tokens": True, "clear_menu": True, "redirect_to": "/login"}}


@pytest.fixture
def session(new_staff, api_client):
    user = new_staff("Staff")
    data = user.activate()
    return user, data, api_client(token=data["access_token"])


def refresh(token: str):
    client = Api(tenant_header=QA_TENANT)
    try:
        return client.post("/auth/refresh", json={"refresh_token": token})
    finally:
        client.close()


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A01")
def test_logout_with_both_tokens(session):
    _, data, client = session
    response = client.post("/auth/logout", json={"refresh_token": data["refresh_token"]})
    assert response.status_code == 200
    assert response.json() == LOGOUT_BODY


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A02")
def test_access_token_blacklisted_after_logout(session):
    _, data, client = session
    client.post("/auth/logout", json={"refresh_token": data["refresh_token"]})
    response = client.get("/auth/available-resources")
    assert response.status_code == 401
    assert detail_text(response) == "Token has been invalidated. Please login again."


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A03")
def test_refresh_token_blacklisted_after_logout(session):
    _, data, client = session
    client.post("/auth/logout", json={"refresh_token": data["refresh_token"]})
    response = refresh(data["refresh_token"])
    assert response.status_code == 401
    assert detail_text(response) == "Refresh token has been invalidated. Please login again."


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A04")
def test_logout_with_access_token_only_keeps_refresh_valid(session):
    _, data, client = session
    assert client.post("/auth/logout").status_code == 200
    assert refresh(data["refresh_token"]).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A05")
def test_logout_with_expired_access_and_valid_refresh(session, api_client):
    _, data, _ = session
    claims = claims_of(data["access_token"])
    claims.pop("exp")
    claims.pop("token_type")
    expired = mint(claims, token_type="access", expires_in=-60)
    response = api_client(token=expired).post("/auth/logout", json={"refresh_token": data["refresh_token"]})
    assert response.status_code == 200
    assert refresh(data["refresh_token"]).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A06")
def test_logout_without_any_token_401(anon):
    response = anon.post("/auth/logout")
    assert response.status_code == 401
    assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A07")
def test_logout_with_garbage_bearer_401(api_client):
    response = api_client(token="garbage", tenant_header=QA_TENANT).post("/auth/logout")
    assert response.status_code == 401
    assert detail_text(response) == "Invalid token"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A08")
def test_logout_with_garbage_tokens_401(api_client):
    response = api_client(token="garbage", tenant_header=QA_TENANT).post("/auth/logout", json={"refresh_token": "garbage"})
    assert response.status_code == 401
    assert detail_text(response) == "Invalid or expired token"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A09")
def test_logout_is_idempotent(session):
    _, data, client = session
    body = {"refresh_token": data["refresh_token"]}
    first = client.post("/auth/logout", json=body)
    second = Api(token=data["access_token"])
    try:
        again = second.post("/auth/logout", json=body)
    finally:
        second.close()
    assert first.status_code == 200
    assert again.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A10")
@pytest.mark.skip(reason="blocked: public.token_blacklist rows cannot be read through the API and the database must not be touched")
def test_blacklist_row_stores_hash_only():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A11")
def test_other_session_of_same_user_survives(new_staff, api_client):
    user = new_staff("Staff")
    first = user.activate()
    time.sleep(1.2)
    second = user.login_data()
    assert first["access_token"] != second["access_token"]
    one = api_client(token=first["access_token"])
    assert one.post("/auth/logout", json={"refresh_token": first["refresh_token"]}).status_code == 200
    assert api_client(token=second["access_token"]).get("/auth/available-resources").status_code == 200
    assert refresh(second["refresh_token"]).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A12")
def test_staff_logout_does_not_affect_admin(session, admin):
    _, data, client = session
    client.post("/auth/logout", json={"refresh_token": data["refresh_token"]})
    assert admin.get("/auth/available-resources").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A13")
@pytest.mark.parametrize("role_name", ["Admin", "Staff", "Teacher"])
def test_logout_for_staff_based_roles(new_staff, api_client, role_name):
    user = new_staff(role_name)
    data = user.activate()
    response = api_client(token=data["access_token"]).post("/auth/logout", json={"refresh_token": data["refresh_token"]})
    assert response.status_code == 200
    assert response.json() == LOGOUT_BODY


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A13")
def test_logout_for_student_and_parent(new_family, api_client):
    family = new_family()
    for data in (family.student_login(), family.father_login()):
        response = api_client(token=data["access_token"]).post("/auth/logout", json={"refresh_token": data["refresh_token"]})
        assert response.status_code == 200
        assert response.json() == LOGOUT_BODY


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A14")
def test_login_after_logout_gets_new_tokens(session, year_id, api_client):
    user, data, client = session
    client.post("/auth/logout", json={"refresh_token": data["refresh_token"]})
    time.sleep(1.2)
    again = fresh_login(user.username, user.password, year_id)
    assert again.status_code == 200
    body = again.json()
    assert body["access_token"] != data["access_token"]
    assert api_client(token=body["access_token"]).get("/auth/available-resources").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-14-A14")
def test_login_in_same_second_after_logout_works(session, year_id, api_client):
    user, data, client = session
    client.post("/auth/logout", json={"refresh_token": data["refresh_token"]})
    again = fresh_login(user.username, user.password, year_id)
    assert again.status_code == 200
    assert api_client(token=again.json()["access_token"]).get("/auth/available-resources").status_code == 200
