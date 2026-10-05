import os

import pytest

from api_tests.auth.helpers import TEMP_STAFF_PASSWORD, claims_of, detail_text, fresh_login, post_login, role_id_map, set_password
from api_tests.support import QA_B_TENANT, QA_TENANT, Api, unique


def qa_password(role: str) -> str:
    return os.environ[f"QA_{role.upper()}_PASSWORD"]


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A01")
def test_admin_login_shape(logins, year_id):
    body = fresh_login(logins["admin"]["user"]["username"], qa_password("admin"), year_id).json()
    assert body["role"]["name"] == "Admin"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 86400
    assert body["client_name"] == QA_TENANT
    assert body["tenant_id"] == logins["admin"]["tenant_id"]
    assert set(body["user"]) == {"id", "username", "email", "is_active"}
    assert "password" not in str(body["user"]).lower()
    for key in ("menu", "permissions", "entity_id", "academic_year_id", "academic_year_title", "access_token", "refresh_token"):
        assert key in body


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A02")
@pytest.mark.parametrize("role_name", ["Staff", "Teacher"])
def test_staff_and_teacher_entity_is_staff_id(new_staff, role_name):
    user = new_staff(role_name)
    body = user.activate()
    assert body["role"]["name"] == role_name
    assert body["entity_id"] == user.staff_id


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A02")
def test_student_and_parent_entity_ids(new_family, admin):
    family = new_family()
    student = family.student_login()
    assert student["role"]["name"] == "Student"
    assert student["entity_id"] == family.student_id
    father = family.father_login()
    assert father["role"]["name"] == "Parent"
    assert father["entity_id"]
    links = admin.get(f"/student-parent-links/parent/{father['entity_id']}/students")
    assert links.status_code == 200
    assert family.student_id in str(links.json())


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A03")
def test_admin_without_staff_row_has_null_entity(logins):
    assert logins["admin"]["entity_id"] is None


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A04")
def test_login_with_email(logins, year_id):
    email = logins["admin"]["user"]["email"]
    assert email
    response = fresh_login(email, qa_password("admin"), year_id)
    assert response.status_code == 200
    assert response.json()["user"]["id"] == logins["admin"]["user"]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A05")
def test_login_with_staff_phone(new_staff, year_id):
    user = new_staff("Staff")
    user.activate()
    response = fresh_login(user.phone, user.password, year_id)
    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.user_id


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A06")
def test_login_with_admission_number(new_family, year_id):
    family = new_family()
    body = family.student_login()
    assert body["role"]["name"] == "Student"
    again = fresh_login(family.admission_number, "Str0ng#Pass26", year_id)
    assert again.status_code == 200
    assert again.json()["role"]["name"] == "Student"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A07")
def test_wrong_password_401(anon, logins, year_id):
    response = post_login(anon, logins["admin"]["user"]["username"], "not-the-password", year_id)
    assert response.status_code == 401
    assert detail_text(response) == "Invalid Credentials"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A08")
def test_unknown_user_same_body_as_wrong_password(anon, logins, year_id):
    wrong = post_login(anon, logins["admin"]["user"]["username"], "not-the-password", year_id)
    unknown = post_login(anon, "nobody_" + unique(), "not-the-password", year_id)
    assert unknown.status_code == 401
    assert unknown.json() == wrong.json()


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A09")
def test_deactivated_user_cannot_login(admin, anon, new_staff, year_id):
    user = new_staff("Staff")
    user.activate()
    assert admin.patch(f"/admin/users/{user.user_id}", json={"is_active": False}).status_code == 200
    response = post_login(anon, user.username, user.password, year_id)
    assert response.status_code == 401
    assert detail_text(response) == "Invalid Credentials"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A10")
def test_username_is_case_and_space_sensitive(anon, logins, year_id):
    name = logins["admin"]["user"]["username"]
    assert post_login(anon, name.upper(), qa_password("admin"), year_id).status_code == 401
    assert post_login(anon, name + " ", qa_password("admin"), year_id).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A11")
def test_same_username_in_two_tenants(admin, tenant_b, cleanup, year_id):
    tag = unique("auth_")
    email = f"{tag}@example.com"
    ids_b = role_id_map(tenant_b)
    roles_a = role_id_map(admin)
    staff_a = admin.post(
        "/staff/enrollment",
        json={"first_name": "A" + tag, "email": email, "phone": "9" + "1" * 9, "address": "x", "role_id": roles_a["Staff"]},
    )
    assert staff_a.status_code in (200, 201), staff_a.text
    cleanup.add(admin.delete, f"/staff/enrollment/{staff_a.json()['id']}")
    cleanup.add(admin.patch, f"/admin/users/{staff_a.json()['user_id']}", json={"is_active": False})
    staff_b = tenant_b.post(
        "/staff/enrollment",
        json={"first_name": "B" + tag, "email": email, "phone": "9" + "2" * 9, "address": "x", "role_id": ids_b["Staff"]},
    )
    assert staff_b.status_code in (200, 201), staff_b.text
    cleanup.add(tenant_b.delete, f"/staff/enrollment/{staff_b.json()['id']}")
    cleanup.add(tenant_b.patch, f"/admin/users/{staff_b.json()['user_id']}", json={"is_active": False})
    first_a = fresh_login(email, TEMP_STAFF_PASSWORD, year_id).json()
    assert set_password(first_a["change_password_token"], "Passw0rd#A1").status_code == 200
    first_b = fresh_login(email, TEMP_STAFF_PASSWORD, tenant_b.academic_year_id, tenant=QA_B_TENANT).json()
    assert set_password(first_b["change_password_token"], "Passw0rd#B2", tenant=QA_B_TENANT).status_code == 200
    assert fresh_login(email, "Passw0rd#A1", year_id).status_code == 200
    assert fresh_login(email, "Passw0rd#B2", year_id).status_code == 401
    assert fresh_login(email, "Passw0rd#B2", tenant_b.academic_year_id, tenant=QA_B_TENANT).status_code == 200
    assert fresh_login(email, "Passw0rd#A1", tenant_b.academic_year_id, tenant=QA_B_TENANT).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A12")
def test_access_token_claims(logins):
    claims = claims_of(logins["admin"]["access_token"])
    for key in ("sub", "username", "role", "tenant_id", "client_name", "academic_year_id", "academic_year_title", "exp"):
        assert key in claims
    assert claims["token_type"] == "access"
    assert claims["role"] == "Admin"
    assert claims["client_name"] == QA_TENANT
    assert "permissions" not in claims
    assert "user_type" not in claims


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A13")
def test_body_client_name_matching_header(anon, logins, year_id):
    response = post_login(
        anon, logins["admin"]["user"]["username"], qa_password("admin"), year_id, client_name=QA_TENANT
    )
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A14")
def test_body_client_name_of_other_tenant_400(anon, logins, year_id, tenant_b):
    response = post_login(
        anon, logins["admin"]["user"]["username"], qa_password("admin"), year_id, client_name=QA_B_TENANT
    )
    assert response.status_code == 400
    assert detail_text(response) == "Tenant does not match the request"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A15")
def test_body_client_name_unknown_401(anon, logins, year_id):
    response = post_login(
        anon, logins["admin"]["user"]["username"], qa_password("admin"), year_id, client_name="no_such_school"
    )
    assert response.status_code == 401
    assert detail_text(response) == "Invalid connection"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A16")
def test_empty_credentials_401(anon, year_id):
    response = post_login(anon, "", "", year_id)
    assert response.status_code == 401
    assert detail_text(response) == "Invalid Credentials"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A17")
def test_missing_password_422(anon, year_id):
    response = anon.post("/auth/login", json={"username": "x", "academic_year_id": year_id})
    assert response.status_code == 422
    assert "password" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A18")
def test_no_lockout_after_ten_failures(anon, new_staff, year_id):
    user = new_staff("Staff")
    user.activate()
    for _ in range(10):
        assert post_login(anon, user.username, "wrong-password", year_id).status_code == 401
    assert post_login(anon, user.username, user.password, year_id).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A19")
def test_login_without_header_rejected(year_id):
    client = Api()
    try:
        response = post_login(client, "qa_admin", "x", year_id)
    finally:
        client.close()
    assert response.status_code >= 400
    assert "access_token" not in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-03-A20")
def test_deactivated_user_keeps_access_token_but_cannot_refresh(admin, new_staff, year_id):
    user = new_staff("Staff")
    user.activate()
    data = user.login_data()
    client = Api(token=data["access_token"])
    anon = Api(tenant_header=QA_TENANT)
    try:
        assert admin.patch(f"/admin/users/{user.user_id}", json={"is_active": False}).status_code == 200
        assert client.get("/auth/available-resources").status_code == 200
        refreshed = anon.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
        assert refreshed.status_code == 401
    finally:
        client.close()
        anon.close()
