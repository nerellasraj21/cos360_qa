import pytest

from api_tests.auth.helpers import (
    MISSING_AUTH,
    TEMP_STAFF_PASSWORD,
    detail_text,
    fresh_login,
    grant_permission,
    role_id_map,
    set_password,
)
from api_tests.support import QA_B_TENANT, Api, Cleanup, unique

OLD = "Str0ng#Pass26"
NEW = "NewPass#2026"


@pytest.fixture(scope="module")
def profile_grants(admin, role_ids):
    stack = Cleanup()
    for role in ("Student", "Staff", "Parent", "Teacher", "Admin"):
        grant_permission(admin, stack, role_ids[role], "profile", "update_own")
    yield
    stack.run()


def body_for(current=OLD, new=NEW, confirm=None):
    return {"current_password": current, "new_password": new, "confirm_password": confirm if confirm is not None else new}


@pytest.fixture
def staff_session(new_staff, api_client, profile_grants):
    user = new_staff("Staff")
    data = user.activate()
    return user, data, api_client(token=data["access_token"])


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A01")
def test_admin_changes_password(new_staff, api_client, profile_grants):
    user = new_staff("Admin")
    client = api_client(token=user.activate()["access_token"])
    response = client.post("/profile/change-password", json=body_for(current=user.password))
    assert response.status_code == 200
    assert response.json() == {"message": "Password changed successfully", "success": True}


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A02")
def test_old_password_stops_new_works(staff_session, year_id):
    user, _, client = staff_session
    assert client.post("/profile/change-password", json=body_for()).status_code == 200
    old = fresh_login(user.username, OLD, year_id)
    assert old.status_code == 401
    assert detail_text(old) == "Invalid Credentials"
    assert fresh_login(user.username, NEW, year_id).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A03")
@pytest.mark.parametrize("role_name", ["Staff", "Teacher"])
def test_staff_and_teacher_change_password(new_staff, api_client, profile_grants, role_name):
    user = new_staff(role_name)
    client = api_client(token=user.activate()["access_token"])
    assert client.post("/profile/change-password", json=body_for()).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A03")
def test_student_and_parent_change_password(new_family, api_client, profile_grants):
    family = new_family()
    student = api_client(token=family.student_login()["access_token"])
    assert student.post("/profile/change-password", json=body_for()).status_code == 200
    parent = api_client(token=family.mother_login()["access_token"])
    assert parent.post("/profile/change-password", json=body_for()).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A04")
def test_wrong_current_password_400(staff_session):
    _, _, client = staff_session
    response = client.post("/profile/change-password", json=body_for(current="wrong-current-1"))
    assert response.status_code == 400
    assert detail_text(response) == "Current password is incorrect"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A05")
def test_mismatch_400(staff_session):
    _, _, client = staff_session
    response = client.post("/profile/change-password", json=body_for(confirm="Different#2026"))
    assert response.status_code == 400
    assert detail_text(response) == "New password and confirmation do not match"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A06")
def test_mismatch_wins_over_wrong_current(staff_session):
    _, _, client = staff_session
    response = client.post("/profile/change-password", json=body_for(current="wrong-current-1", confirm="Different#2026"))
    assert response.status_code == 400
    assert detail_text(response) == "New password and confirmation do not match"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A07")
def test_seven_character_passwords_422(staff_session):
    _, _, client = staff_session
    response = client.post("/profile/change-password", json=body_for(new="Seven#7", confirm="Seven#7"))
    assert response.status_code == 422
    assert "new_password" in response.text and "confirm_password" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A08")
def test_eight_character_password_200(staff_session):
    _, _, client = staff_session
    assert client.post("/profile/change-password", json=body_for(new="Eight#8!")).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A09")
def test_empty_current_password_422(staff_session):
    _, _, client = staff_session
    response = client.post("/profile/change-password", json=body_for(current=""))
    assert response.status_code == 422
    assert "current_password" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A10")
def test_reusing_current_password_allowed(staff_session):
    _, _, client = staff_session
    assert client.post("/profile/change-password", json=body_for(new=OLD)).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A11")
def test_change_password_without_grant_403(new_staff, custom_role, api_client):
    role = custom_role()
    user = new_staff("Staff", role_id=role["id"])
    client = api_client(token=user.login_data()["access_token"])
    response = client.post("/profile/change-password", json=body_for(current=TEMP_STAFF_PASSWORD))
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "permission_denied"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A12")
def test_change_password_requires_token(anon):
    response = anon.post("/profile/change-password", json=body_for())
    assert response.status_code == 401
    assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A13")
def test_tokens_survive_password_change(staff_session, api_client):
    user, data, client = staff_session
    assert client.post("/profile/change-password", json=body_for()).status_code == 200
    assert client.get("/auth/available-resources").status_code == 200
    anon = Api(tenant_header="qa_school")
    try:
        assert anon.post("/auth/refresh", json={"refresh_token": data["refresh_token"]}).status_code == 200
    finally:
        anon.close()


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A14")
@pytest.mark.skip(reason="blocked: profile_audit_logs rows cannot be read through the API and the database must not be touched")
def test_change_password_audit_row():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-11-A15")
def test_password_change_is_tenant_scoped(admin, tenant_b, cleanup, year_id, profile_grants):
    tag = unique("auth_")
    email = f"{tag}@example.com"
    made = {}
    for key, client, role_map in (("a", admin, role_id_map(admin)), ("b", tenant_b, role_id_map(tenant_b))):
        response = client.post(
            "/staff/enrollment",
            json={
                "first_name": key + tag,
                "email": email,
                "phone": "9" + ("3" if key == "a" else "4") * 9,
                "address": "x",
                "role_id": role_map["Staff"],
            },
        )
        assert response.status_code in (200, 201), response.text
        cleanup.add(client.delete, f"/staff/enrollment/{response.json()['id']}")
        cleanup.add(client.patch, f"/admin/users/{response.json()['user_id']}", json={"is_active": False})
        made[key] = response.json()
    first_a = fresh_login(email, TEMP_STAFF_PASSWORD, year_id).json()
    done_a = set_password(first_a["change_password_token"], "Passw0rd#A1").json()
    first_b = fresh_login(email, TEMP_STAFF_PASSWORD, tenant_b.academic_year_id, tenant=QA_B_TENANT).json()
    set_password(first_b["change_password_token"], "Passw0rd#B1", tenant=QA_B_TENANT)
    client_a = Api(token=done_a["access_token"])
    try:
        response = client_a.post(
            "/profile/change-password", json=body_for(current="Passw0rd#A1", new="Passw0rd#A2")
        )
    finally:
        client_a.close()
    assert response.status_code == 200
    assert fresh_login(email, "Passw0rd#B1", tenant_b.academic_year_id, tenant=QA_B_TENANT).status_code == 200
    assert fresh_login(email, "Passw0rd#A1", year_id).status_code == 401
