import pytest

from api_tests.auth.helpers import (
    MISSING_AUTH,
    TEMP_STUDENT_PASSWORD,
    create_family,
    fresh_login,
    grant_permission,
    role_id_map,
    set_password,
)
from api_tests.support import QA_B_TENANT, Cleanup

STUDENT_FIELDS = {
    "student_id",
    "user_id",
    "first_name",
    "last_name",
    "date_of_birth",
    "gender",
    "email",
    "admission_number",
    "class_name",
    "section_name",
    "is_active",
    "profile_photo_url",
    "attendance_percentage",
    "total_certificates",
    "total_documents",
}
STAFF_FIELDS = {
    "staff_id",
    "user_id",
    "first_name",
    "last_name",
    "email",
    "phone",
    "designation",
    "employee_id",
    "date_of_joining",
    "is_active",
    "profile_photo_url",
}
PARENT_FIELDS = {
    "parent_id",
    "user_id",
    "name",
    "email",
    "phone",
    "occupation",
    "relation_to_student",
    "profile_photo_url",
    "children",
}
CHILD_FIELDS = {"student_id", "first_name", "last_name", "admission_number", "class_name", "section_name", "is_active"}


@pytest.fixture(scope="module")
def profile_grants(admin, role_ids):
    stack = Cleanup()
    for role in ("Student", "Staff", "Parent", "Teacher", "Admin"):
        grant_permission(admin, stack, role_ids[role], "profile", "read_own")
        grant_permission(admin, stack, role_ids[role], "profile", "update_own")
    yield
    stack.run()


@pytest.fixture
def student_session(new_family, api_client, profile_grants):
    family = new_family()
    data = family.student_login()
    return family, data, api_client(token=data["access_token"])


@pytest.fixture
def staff_session(new_staff, api_client, profile_grants):
    user = new_staff("Staff")
    data = user.activate()
    return user, data, api_client(token=data["access_token"])


@pytest.fixture
def parent_session(new_family, api_client, profile_grants):
    family = new_family()
    data = family.father_login()
    return family, data, api_client(token=data["access_token"])


@pytest.fixture
def ungranted_client(new_staff, custom_role, api_client):
    role = custom_role()
    user = new_staff("Staff", role_id=role["id"])
    return api_client(token=user.login_data()["access_token"])


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A01")
def test_student_reads_own_profile(student_session):
    family, data, client = student_session
    response = client.get("/profile/student/me")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == STUDENT_FIELDS
    assert body["student_id"] == family.student_id
    assert body["admission_number"] == family.admission_number
    assert body["profile_photo_url"] is None


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A02")
def test_staff_reads_own_profile(staff_session):
    user, data, client = staff_session
    response = client.get("/profile/staff/me")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == STAFF_FIELDS
    assert body["staff_id"] == user.staff_id
    assert body["email"] == user.username
    assert body["phone"] == user.phone


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A03")
def test_parent_reads_profile_with_children(admin, cleanup, year_id, api_client, profile_grants):
    first = create_family(admin, cleanup, year_id)
    second = create_family(admin, cleanup, year_id, class_id=first.class_id, father_email=first.father_email)
    client = api_client(token=first.father_login()["access_token"])
    response = client.get("/profile/parent/me")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == PARENT_FIELDS
    assert len(body["children"]) == 2
    for child in body["children"]:
        assert set(child) == CHILD_FIELDS
    assert {c["student_id"] for c in body["children"]} == {first.student_id, second.student_id}


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A04")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher", "student", "parent"])
@pytest.mark.parametrize("kind", ["student", "staff", "parent"])
def test_unlinked_users_get_404_on_every_profile(role_clients, profile_grants, role, kind):
    response = role_clients[role].get(f"/profile/{kind}/me")
    assert response.status_code == 404
    assert response.json()["detail"] == f"{kind.capitalize()} profile not found"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A04")
def test_linked_user_only_matches_own_endpoint(student_session, staff_session, parent_session):
    for (_, _, client), own in ((student_session, "student"), (staff_session, "staff"), (parent_session, "parent")):
        for kind in ("student", "staff", "parent"):
            response = client.get(f"/profile/{kind}/me")
            assert response.status_code == (200 if kind == own else 404)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A05")
@pytest.mark.parametrize("kind", ["student", "staff", "parent"])
def test_profile_read_without_grant_403(ungranted_client, kind):
    response = ungranted_client.get(f"/profile/{kind}/me")
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "permission_denied"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A06")
def test_student_email_update_changes_login_email(student_session, year_id):
    family, _, client = student_session
    response = client.put("/profile/student/me", json={"email": "new.student@example.com"})
    assert response.status_code == 200
    assert response.json()["email"] == "new.student@example.com"
    assert client.get("/profile/student/me").json()["email"] == "new.student@example.com"
    assert fresh_login("new.student@example.com", "Str0ng#Pass26", year_id).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A07")
def test_student_update_drops_unknown_fields(student_session):
    _, _, client = student_session
    before = client.get("/profile/student/me").json()
    response = client.put(
        "/profile/student/me", json={"email": "a.student@example.com", "phone": "9999999999", "address": "x"}
    )
    assert response.status_code == 200
    after = response.json()
    assert after["email"] == "a.student@example.com"
    assert {k: v for k, v in after.items() if k != "email"} == {k: v for k, v in before.items() if k != "email"}


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A08")
def test_staff_update_email_and_phone_keep_login(admin, staff_session):
    user, _, client = staff_session
    response = client.put("/profile/staff/me", json={"email": "s2@example.com", "phone": "9123456780"})
    assert response.status_code == 200
    assert response.json()["email"] == "s2@example.com"
    assert response.json()["phone"] == "9123456780"
    account = admin.get(f"/admin/users/{user.user_id}").json()
    assert account["username"] == user.username
    assert account["email"] == user.username


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A09")
def test_staff_logs_in_with_new_phone(staff_session, year_id):
    user, _, client = staff_session
    assert client.put("/profile/staff/me", json={"phone": "9123456781"}).status_code == 200
    response = fresh_login("9123456781", user.password, year_id)
    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.user_id


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A10")
def test_parent_update_occupation_only(parent_session):
    _, _, client = parent_session
    before = client.get("/profile/parent/me").json()
    response = client.put("/profile/parent/me", json={"occupation": "Engineer"})
    assert response.status_code == 200
    body = response.json()
    assert body["occupation"] == "Engineer"
    assert body["email"] == before["email"] and body["phone"] == before["phone"]


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A11")
@pytest.mark.parametrize("kind", ["student", "staff", "parent"])
def test_empty_update_changes_nothing(student_session, staff_session, parent_session, kind):
    client = {"student": student_session, "staff": staff_session, "parent": parent_session}[kind][2]
    before = client.get(f"/profile/{kind}/me").json()
    response = client.put(f"/profile/{kind}/me", json={})
    assert response.status_code == 200
    assert response.json() == before


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A12")
def test_email_format_not_validated(student_session):
    _, _, client = student_session
    response = client.put("/profile/student/me", json={"email": "not-an-email"})
    assert response.status_code == 200
    assert client.get("/profile/student/me").json()["email"] == "not-an-email"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A13")
@pytest.mark.parametrize("kind", ["student", "staff", "parent"])
def test_profile_update_without_grant_403(ungranted_client, kind):
    response = ungranted_client.put(f"/profile/{kind}/me", json={})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "permission_denied"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A14")
@pytest.mark.parametrize("kind", ["student", "staff", "parent"])
def test_profile_requires_token(anon, kind):
    for response in (anon.get(f"/profile/{kind}/me"), anon.put(f"/profile/{kind}/me", json={})):
        assert response.status_code == 401
        assert response.json()["detail"] == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A15")
@pytest.mark.skip(reason="blocked: profile_audit_logs rows cannot be read through the API and the database must not be touched")
def test_profile_audit_rows():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A16")
def test_email_over_100_characters_rejected(student_session):
    _, _, client = student_session
    before = client.get("/profile/student/me").json()["email"]
    response = client.put("/profile/student/me", json={"email": "e" * 92 + "@example.com"})
    assert not response.is_success
    assert client.get("/profile/student/me").json()["email"] == before


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A17")
def test_students_of_two_tenants_see_own_records(student_session, tenant_b, cleanup, year_id):
    family, _, client = student_session
    other = create_family(tenant_b, cleanup, tenant_b.academic_year_id)
    roles_b = role_id_map(tenant_b)
    grant_permission(tenant_b, cleanup, roles_b["Student"], "profile", "read_own")
    first = fresh_login(
        other.admission_number, TEMP_STUDENT_PASSWORD, tenant_b.academic_year_id, tenant=QA_B_TENANT
    ).json()
    done = set_password(first["change_password_token"], "Password#11", tenant=QA_B_TENANT).json()
    from api_tests.support import Api

    other_client = Api(token=done["access_token"])
    try:
        theirs = other_client.get("/profile/student/me")
    finally:
        other_client.close()
    assert theirs.status_code == 200
    mine = client.get("/profile/student/me").json()
    assert theirs.json()["student_id"] == other.student_id
    assert mine["student_id"] == family.student_id
    assert mine["student_id"] != theirs.json()["student_id"]


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-10-A18")
@pytest.mark.skip(reason="blocked: a student cannot exist without an admission through the API")
def test_student_without_admission():
    pass
