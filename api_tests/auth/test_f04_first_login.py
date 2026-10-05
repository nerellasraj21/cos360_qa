import pytest

from api_tests.auth.helpers import (
    STRONG_PASSWORD,
    TEMP_PARENT_PASSWORD,
    TEMP_STAFF_PASSWORD,
    TEMP_STUDENT_PASSWORD,
    claims_of,
    detail_text,
    fresh_login,
    mint,
    rand_phone,
    role_id_map,
    set_password,
)
from api_tests.support import QA_B_TENANT, QA_TENANT, unique

CHALLENGE_KEYS = {"requires_password_change", "change_password_token", "message", "academic_year_id", "academic_year_title"}


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A01")
def test_staff_first_login_returns_challenge(new_staff):
    user = new_staff("Staff")
    body = user.login_response().json()
    assert CHALLENGE_KEYS <= set(body)
    assert body["requires_password_change"] is True
    assert body["message"] == "Please set a new password to continue"
    assert "access_token" not in body and "refresh_token" not in body


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A02")
@pytest.mark.parametrize("role_name", ["Teacher", "Student", "Parent"])
def test_other_roles_get_challenge(new_staff, role_name):
    user = new_staff(role_name)
    body = user.login_response().json()
    assert body["requires_password_change"] is True
    assert "access_token" not in body
    assert claims_of(body["change_password_token"])["role"] == role_name


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A02")
def test_admitted_student_and_parents_get_challenge(new_family, year_id):
    family = new_family()
    for username, password, role in (
        (family.admission_number, TEMP_STUDENT_PASSWORD, "Student"),
        (family.father_email, TEMP_PARENT_PASSWORD, "Parent"),
        (family.mother_username, TEMP_PARENT_PASSWORD, "Parent"),
    ):
        body = fresh_login(username, password, year_id).json()
        assert body["requires_password_change"] is True
        assert claims_of(body["change_password_token"])["role"] == role


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A03")
def test_admin_role_user_is_never_challenged(new_staff):
    user = new_staff("Admin")
    body = user.login_response().json()
    assert "requires_password_change" not in body or body["requires_password_change"] is not True
    assert body["access_token"]
    assert body["role"]["name"] == "Admin"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A04")
def test_challenge_token_claims(new_staff):
    user = new_staff("Staff")
    token = user.challenge()
    claims = claims_of(token)
    assert claims["token_type"] == "change_password"
    for key in ("sub", "username", "role", "tenant_id", "client_name", "academic_year_id", "academic_year_title"):
        assert key in claims
    assert claims["client_name"] == QA_TENANT
    import time

    remaining = claims["exp"] - time.time()
    assert 14 * 60 <= remaining <= 15 * 60 + 10


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A05")
def test_challenge_token_is_not_a_bearer_token(new_staff, api_client):
    user = new_staff("Staff")
    token = user.challenge()
    client = api_client(token=token, tenant_header=QA_TENANT)
    response = client.get("/profile/staff/me")
    assert response.status_code == 401
    assert detail_text(response) == "Invalid token type"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A05")
@pytest.mark.xfail(
    strict=True,
    reason="AUTH-NONACCESS-400: a change-password token sent as bearer without a cschema header gets 400 Tenant must be specified instead of 401",
)
def test_challenge_token_as_bearer_without_header_is_401(new_staff, api_client):
    user = new_staff("Staff")
    token = user.challenge()
    response = api_client(token=token).get("/profile/staff/me")
    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A06")
def test_set_password_returns_full_login_payload(new_staff):
    user = new_staff("Staff")
    token = user.challenge()
    response = set_password(token, "TenCharPw#1")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Password updated successfully"
    for key in ("access_token", "refresh_token", "menu", "permissions", "entity_id", "role", "user"):
        assert key in body
    assert body["entity_id"] == user.staff_id


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A07")
def test_old_temporary_password_stops_working(new_staff, year_id):
    user = new_staff("Staff")
    user.activate()
    response = fresh_login(user.username, TEMP_STAFF_PASSWORD, year_id)
    assert response.status_code == 401
    assert detail_text(response) == "Invalid Credentials"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A08")
def test_new_password_logs_in_without_challenge(new_staff, year_id):
    user = new_staff("Staff")
    user.activate("Brand#New2026")
    body = fresh_login(user.username, "Brand#New2026", year_id).json()
    assert body.get("access_token")
    assert body.get("requires_password_change") is not True


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A09")
def test_replaying_the_token_is_rejected(new_staff):
    user = new_staff("Staff")
    token = user.challenge()
    assert set_password(token, STRONG_PASSWORD).status_code == 200
    again = set_password(token, "Another#Pass77")
    assert again.status_code == 400
    assert detail_text(again) == "Password has already been set. Please log in with your password."


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A10")
def test_mismatch_checked_before_token():
    response = set_password("not-a-token", "Password#11", confirm="Password#22")
    assert response.status_code == 400
    assert detail_text(response) == "Passwords do not match"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A11")
def test_short_password_422(new_staff):
    user = new_staff("Staff")
    token = user.challenge()
    response = set_password(token, "short7!")
    assert response.status_code == 422
    assert "new_password" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A12")
def test_eight_character_password_accepted(new_staff):
    user = new_staff("Staff")
    token = user.challenge()
    assert set_password(token, "Eight#8!").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A13")
def test_garbage_token_401():
    response = set_password("garbage-token", "Password#11")
    assert response.status_code == 401
    assert detail_text(response) == "Invalid or expired change-password token. Please login again."


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A14")
def test_expired_token_401(new_staff):
    user = new_staff("Staff")
    claims = claims_of(user.challenge())
    claims.pop("exp")
    claims.pop("token_type")
    old = mint(claims, token_type="change_password", expires_in=-16 * 60)
    response = set_password(old, "Password#11")
    assert response.status_code == 401
    assert detail_text(response) == "Invalid or expired change-password token. Please login again."


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A15")
def test_deactivated_after_challenge_401(admin, new_staff):
    user = new_staff("Staff")
    token = user.challenge()
    assert admin.patch(f"/admin/users/{user.user_id}", json={"is_active": False}).status_code == 200
    response = set_password(token, "Password#11")
    assert response.status_code == 401
    assert detail_text(response) == "Invalid Credentials"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A16")
def test_deactivated_tenant_after_challenge_401(tmp_main, cleanup):
    admin = tmp_main.admin
    role_id = role_id_map(admin)["Staff"]
    email = f"{unique('auth_')}@example.com"
    made = admin.post(
        "/staff/enrollment",
        json={"first_name": "T", "email": email, "phone": rand_phone(), "address": "x", "role_id": role_id},
    )
    assert made.status_code in (200, 201), made.text
    cleanup.add(admin.patch, f"/admin/users/{made.json()['user_id']}", json={"is_active": False})
    cleanup.add(admin.delete, f"/staff/enrollment/{made.json()['id']}")
    year = tmp_main.year_id
    token = fresh_login(email, TEMP_STAFF_PASSWORD, year, tenant=tmp_main.client_name).json()["change_password_token"]
    tmp_main.set_active(False)
    try:
        response = set_password(token, "Password#11", tenant=tmp_main.client_name)
        assert response.status_code == 401
        assert detail_text(response) == "Invalid connection"
    finally:
        tmp_main.set_active(True)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A17")
def test_header_is_not_compared_to_token_tenant(new_staff, tenant_b):
    user = new_staff("Staff")
    token = user.challenge()
    response = set_password(token, "Password#11", tenant=QA_B_TENANT)
    assert response.status_code == 200
    assert response.json()["client_name"] == QA_TENANT


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A18")
def test_challenge_with_wrong_year_400(new_staff):
    import uuid

    user = new_staff("Staff")
    response = fresh_login(user.username, TEMP_STAFF_PASSWORD, str(uuid.uuid4()))
    assert response.status_code == 400
    assert detail_text(response) == "Invalid academic year"
    assert "change_password_token" not in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-04-A19")
@pytest.mark.parametrize("role_name", ["Staff", "Teacher", "Student", "Parent"])
def test_set_password_works_for_each_forced_role(new_staff, role_name):
    user = new_staff(role_name)
    body = user.activate()
    assert body["role"]["name"] == role_name
    assert body["access_token"]
