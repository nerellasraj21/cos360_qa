import os

import pytest

from api_tests.auth.helpers import claims_of, detail_text
from api_tests.support import Api
from api_tests.tenants_admin.conftest import MISSING_AUTH, ROLES, SA_REQUIRED, denied_text


def sa_username() -> str:
    return os.environ["QA_SUPERADMIN_USER"]


def sa_password() -> str:
    return os.environ["QA_SUPERADMIN_PASSWORD"]


def sa_login_response(client: Api, username: str | None = None, password: str | None = None):
    return client.post(
        "/super_admin/auth/login", json={"username": username or sa_username(), "password": password or sa_password()}
    )


@pytest.mark.api
@pytest.mark.tc("TC-TEN-01-A01")
def test_setup_status_without_token(bare):
    response = bare.get("/super_admin/setup/status")
    assert response.status_code == 200
    body = response.json()
    assert body["system_status"] == "initialized"
    assert sorted(body["tables_exist"]) == ["super_admin_audit", "super_admin_users"]
    assert body["missing_tables"] == []
    assert body["super_admin_count"] >= 1
    assert body["ready_for_login"] is True


@pytest.mark.api
@pytest.mark.tc("TC-TEN-01-A02")
def test_initialize_without_environment_password_400(bare):
    response = bare.post("/super_admin/setup/initialize")
    assert response.status_code == 400
    assert detail_text(response) == "Set SUPER_ADMIN_INITIAL_PASSWORD in the server environment before running setup"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-01-A03")
@pytest.mark.skip(reason="blocked: the test API runs without SUPER_ADMIN_INITIAL_PASSWORD, so the 409 branch is unreachable and the server cannot be restarted")
def test_initialize_when_super_admin_exists_409():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-01-A04")
@pytest.mark.skip(reason="blocked: needs an empty throwaway database and the creation of a super admin, which the task forbids")
def test_initialize_on_empty_database():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-01-A05")
@pytest.mark.skip(reason="blocked: depends on TC-TEN-01-A04 (needs the creation of a super admin)")
def test_first_login_after_initialize():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-01-A06")
def test_setup_status_open_to_tenant_admin(admin):
    response = admin.get("/super_admin/setup/status")
    assert response.status_code == 200
    assert response.json()["system_status"] == "initialized"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A01")
def test_super_admin_login_shape(bare):
    response = sa_login_response(bare)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 86400
    assert body["user_type"] == "super_admin"
    assert body["access_token"] and body["refresh_token"]
    claims = claims_of(body["access_token"])
    assert claims["user_type"] == "super_admin"
    assert claims["token_type"] == "access"
    assert set(claims["permissions"]) == {"system_admin", "tenant_management", "plan_management"}
    assert "role" not in claims and "tenant_id" not in claims
    refresh = claims_of(body["refresh_token"])
    assert refresh["token_type"] == "refresh" and "sub" in refresh


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A02")
def test_wrong_password_401_then_counter_reset(bare):
    wrong = sa_login_response(bare, password="definitely-wrong-1")
    try:
        assert wrong.status_code == 401
        assert detail_text(wrong) == "Invalid credentials"
    finally:
        assert sa_login_response(bare).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A03")
def test_unknown_username_401(bare):
    response = sa_login_response(bare, username="no_such_superadmin", password="whatever-1")
    assert response.status_code == 401
    assert detail_text(response) == "Invalid credentials"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A04")
@pytest.mark.tc("TC-TEN-02-A05")
@pytest.mark.tc("TC-TEN-02-A06")
@pytest.mark.skip(reason="blocked: needs a throwaway super admin and the task forbids creating super admins; failing five logins on the shared QA account would lock it")
def test_lockout_and_deactivation_flow():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A07")
def test_profile_with_access_token(superadmin):
    response = superadmin.get("/super_admin/auth/profile")
    assert response.status_code == 200
    assert response.json()["username"] == sa_username()


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A08")
def test_refresh_token_not_a_bearer(bare):
    body = sa_login_response(bare).json()
    client = Api(token=body["refresh_token"])
    try:
        response = client.get("/super_admin/auth/profile")
    finally:
        client.close()
    assert response.status_code == 401
    assert detail_text(response) == "Invalid token type"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A09")
def test_super_admin_refresh_token_on_tenant_refresh(bare, anon):
    body = sa_login_response(bare).json()
    response = anon.post("/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert response.status_code == 401
    assert detail_text(response) == "Your session is out of date. Please log in again."


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A10")
def test_super_admin_token_on_tenant_endpoint(superadmin, tenant_header_value, api_client):
    client = api_client(token=superadmin.token, tenant_header=tenant_header_value)
    response = client.get("/admin/users/")
    assert response.status_code == 403
    assert detail_text(response) == denied_text("None", "list", "user_management")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A11")
def test_super_admin_token_without_header(superadmin, api_client):
    client = api_client(token=superadmin.token)
    response = client.get("/admin/users/")
    assert response.status_code == 404
    assert detail_text(response) == "Tenant '' not found or inactive"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A12")
@pytest.mark.parametrize("role", ROLES)
def test_tenant_roles_denied_on_super_admin_profile(role_clients, role):
    response = role_clients[role].get("/super_admin/auth/profile")
    assert response.status_code == 403
    assert detail_text(response) == SA_REQUIRED


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A13")
def test_super_admin_profile_requires_token(bare):
    response = bare.get("/super_admin/auth/profile")
    assert response.status_code == 401
    assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A14")
def test_tenant_admin_credentials_rejected(bare):
    response = sa_login_response(bare, username=os.environ["QA_ADMIN_USER"], password=os.environ["QA_ADMIN_PASSWORD"])
    assert response.status_code == 401
    assert detail_text(response) == "Invalid credentials"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A15")
@pytest.mark.skip(reason="blocked: super_admin_audit rows cannot be read through the API and the database must not be touched")
def test_login_writes_audit_row():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-02-A16")
def test_login_without_password_422(bare):
    response = bare.post("/super_admin/auth/login", json={"username": sa_username()})
    assert response.status_code == 422
    assert "password" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A01")
@pytest.mark.skip(reason="blocked: creating a super admin is forbidden by the task rules (no delete endpoint exists)")
def test_register_super_admin_created():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A02")
def test_register_duplicate_username_400(superadmin):
    response = superadmin.post(
        "/super_admin/auth/register",
        json={"username": sa_username(), "email": "zz_new_unused@example.com", "full_name": "Dup Name", "password": "Passw0rd#12"},
    )
    assert response.status_code == 400
    assert detail_text(response) == "Username already exists"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A03")
def test_register_duplicate_email_400(superadmin):
    email = superadmin.get("/super_admin/auth/profile").json()["email"]
    response = superadmin.post(
        "/super_admin/auth/register",
        json={"username": "qa_tmp_never_created", "email": email, "full_name": "Dup Name", "password": "Passw0rd#12"},
    )
    assert response.status_code == 400
    assert detail_text(response) == "Email already exists"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A04")
@pytest.mark.parametrize(
    "body,field",
    [
        ({"username": "ab", "email": "a@example.com", "full_name": "Valid Name", "password": "Passw0rd#12"}, "username"),
        ({"username": "valid_name", "email": "a@example.com", "full_name": "Valid Name", "password": "short7!"}, "password"),
        ({"username": "valid_name", "email": "x", "full_name": "Valid Name", "password": "Passw0rd#12"}, "email"),
    ],
)
def test_register_validation_422(superadmin, body, field):
    response = superadmin.post("/super_admin/auth/register", json=body)
    assert response.status_code == 422
    assert field in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A05")
@pytest.mark.skip(reason="blocked: depends on TC-TEN-03-A01 (creating a super admin is forbidden)")
def test_registered_super_admin_can_login():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A06")
def test_register_denied_for_tenant_admin_and_anonymous(admin, bare):
    body = {"username": "qa_tmp_never", "email": "n@example.com", "full_name": "Never Made", "password": "Passw0rd#12"}
    denied = admin.post("/super_admin/auth/register", json=body)
    assert denied.status_code == 403
    assert detail_text(denied) == SA_REQUIRED
    anonymous = bare.post("/super_admin/auth/register", json=body)
    assert anonymous.status_code == 401
    assert detail_text(anonymous) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A07")
def test_profile_returns_own_account(superadmin):
    body = superadmin.get("/super_admin/auth/profile").json()
    assert body["username"] == sa_username()
    for key in (
        "id",
        "email",
        "full_name",
        "is_active",
        "last_login_at",
        "password_changed_at",
        "created_at",
        "updated_at",
        "failed_login_attempts",
        "account_locked_until",
        "requires_password_change",
    ):
        assert key in body
    assert "password" not in body and "password_hash" not in body


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A08")
def test_profile_update_full_name_and_restore(superadmin, serial_guard):
    before = superadmin.get("/super_admin/auth/profile").json()
    try:
        response = superadmin.put("/super_admin/auth/profile", json={"full_name": "QA Second"})
        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == "QA Second"
        assert body["updated_at"] >= before["updated_at"]
    finally:
        superadmin.put("/super_admin/auth/profile", json={"full_name": before["full_name"]})
    assert superadmin.get("/super_admin/auth/profile").json()["full_name"] == before["full_name"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A09")
@pytest.mark.skip(reason="blocked: needs a second super admin whose email can be taken, and creating super admins is forbidden")
def test_profile_update_with_taken_email():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A10")
@pytest.mark.skip(reason="blocked: deactivating the shared QA super admin would lock the suite out and a throwaway one cannot be created")
def test_super_admin_deactivates_itself():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A11")
@pytest.mark.tc("TC-TEN-03-A12")
@pytest.mark.skip(reason="blocked: a successful password change would alter the shared QA super admin and a throwaway one cannot be created")
def test_super_admin_change_password_success():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A13")
def test_change_password_wrong_current_400(superadmin):
    response = superadmin.post(
        "/super_admin/auth/change-password", json={"current_password": "wrong-current-1", "new_password": "Brand#New9"}
    )
    assert response.status_code == 400
    assert detail_text(response) == "Current password is incorrect"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A14")
def test_change_password_short_new_password_422(superadmin):
    response = superadmin.post(
        "/super_admin/auth/change-password", json={"current_password": "wrong-current-1", "new_password": "short7!"}
    )
    assert response.status_code == 422
    assert "new_password" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A15")
@pytest.mark.parametrize("role", ROLES)
def test_super_admin_account_endpoints_denied_to_tenant_roles(role_clients, role):
    client = role_clients[role]
    calls = [
        client.post(
            "/super_admin/auth/register",
            json={"username": "qa_tmp_never", "email": "n@example.com", "full_name": "Never Made", "password": "Passw0rd#12"},
        ),
        client.get("/super_admin/auth/profile"),
        client.put("/super_admin/auth/profile", json={}),
        client.post("/super_admin/auth/change-password", json={"current_password": "x", "new_password": "Brand#New9"}),
    ]
    for response in calls:
        assert response.status_code == 403
        assert detail_text(response) == SA_REQUIRED


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A16")
@pytest.mark.skip(reason="blocked: super_admin_audit rows cannot be read through the API and the database must not be touched")
def test_super_admin_audit_rows():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-03-A08")
def test_profile_empty_body_changes_nothing(superadmin, serial_guard):
    before = superadmin.get("/super_admin/auth/profile").json()
    response = superadmin.put("/super_admin/auth/profile", json={})
    assert response.status_code == 200
    after = response.json()
    for key in ("username", "email", "full_name", "is_active"):
        assert after[key] == before[key]
