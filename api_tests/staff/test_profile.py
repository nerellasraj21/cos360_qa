import pytest

from api_tests.staff.helpers import email_address, granted
from api_tests.support import QA_TENANT, Api

PROFILE = "/profile/staff/me"
GRANTS = [("profile", "read_own"), ("profile", "update_own")]


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A01")
def test_profile_without_designation(role_client):
    client = role_client(GRANTS)
    response = client.get(PROFILE)
    assert response.status_code == 200
    data = response.json()
    assert data["staff_id"] == client.staff["id"]
    assert data["user_id"] == client.staff["user_id"]
    assert data["first_name"] == client.staff["first_name"]
    assert data["employee_id"] is None and data["profile_photo_url"] is None
    assert data["designation"] is None and data["is_active"] is True
    assert set(data) == {
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


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A02")
def test_profile_with_designation(role_client, make_designation):
    designation = make_designation()
    client = role_client(GRANTS, designation_id=designation["id"])
    response = client.get(PROFILE)
    assert response.status_code == 200
    assert response.json()["designation"] == designation["title"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A03")
def test_update_profile_email_and_phone(role_client, admin):
    client = role_client(GRANTS)
    new_email = email_address()
    new_phone = "9" + client.staff["phone"][1:][::-1]
    response = client.put(PROFILE, json={"email": new_email, "phone": new_phone})
    assert response.status_code == 200
    assert response.json()["email"] == new_email and response.json()["phone"] == new_phone
    stored = admin.get(f"/staff/enrollment/{client.staff['id']}").json()
    assert stored["email"] == new_email and stored["phone"] == new_phone
    assert admin.get(f"/admin/users/{client.staff['user_id']}").json()["username"] == client.staff["_login"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A04")
def test_update_profile_with_designation(role_client, make_designation):
    designation = make_designation()
    client = role_client(GRANTS, designation_id=designation["id"])
    response = client.put(PROFILE, json={"phone": "9000000099"})
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A04")
def test_update_profile_with_designation_still_saves_the_change(role_client, admin, make_designation):
    designation = make_designation()
    client = role_client(GRANTS, designation_id=designation["id"])
    client.put(PROFILE, json={"phone": "9000000098"})
    assert admin.get(f"/staff/enrollment/{client.staff['id']}").json()["phone"] == "9000000098"


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A05")
def test_empty_update_changes_nothing(role_client, admin):
    client = role_client(GRANTS)
    before = admin.get(f"/staff/enrollment/{client.staff['id']}").json()
    response = client.put(PROFILE, json={})
    assert response.status_code == 200
    after = admin.get(f"/staff/enrollment/{client.staff['id']}").json()
    assert (after["email"], after["phone"]) == (before["email"], before["phone"])


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A06")
def test_profile_email_is_not_validated(role_client):
    client = role_client(GRANTS)
    valid = client.staff["_login"]
    try:
        response = client.put(PROFILE, json={"email": "not-an-email"})
        assert response.status_code == 200
        assert response.json()["email"] == "not-an-email"
    finally:
        client.put(PROFILE, json={"email": valid})


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A06")
def test_invalid_profile_email_does_not_break_staff_list(role_client, admin):
    client = role_client(GRANTS)
    valid = client.staff["_login"]
    try:
        assert client.put(PROFILE, json={"email": "not-an-email"}).status_code == 200
        assert admin.get("/staff/enrollments").status_code == 200
        assert admin.get(f"/staff/enrollment/{client.staff['id']}").status_code == 200
    finally:
        client.put(PROFILE, json={"email": valid})


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A07")
def test_profile_duplicate_email_fails(role_client, make_staff, admin):
    other = make_staff(email=email_address())
    client = role_client(GRANTS)
    before = admin.get(f"/staff/enrollment/{client.staff['id']}").json()["email"]
    response = client.put(PROFILE, json={"email": other["_body"]["email"]})
    assert response.status_code >= 400
    assert admin.get(f"/staff/enrollment/{client.staff['id']}").json()["email"] == before


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A08")
def test_profile_for_user_without_staff_row(role_client, admin):
    client = role_client(GRANTS)
    assert admin.delete(f"/staff/enrollment/{client.staff['id']}").status_code == 200
    response = client.get(PROFILE)
    assert response.status_code == 404
    assert response.json()["detail"] == "Staff profile not found"


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A09")
def test_default_staff_role_has_no_profile_grant(role_clients, logins):
    assert not granted(logins, "staff", "profile", "read_own")
    response = role_clients["staff"].get(PROFILE)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "permission_denied"


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A10")
def test_read_own_without_update_own(role_client):
    client = role_client([("profile", "read_own")])
    assert client.get(PROFILE).status_code == 200
    assert client.put(PROFILE, json={"phone": "9000000097"}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A11")
@pytest.mark.parametrize("role", ["student", "parent"])
def test_student_and_parent_profile(role_clients, logins, role):
    expected = 404 if granted(logins, role, "profile", "read_own") else 403
    assert role_clients[role].get(PROFILE).status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A12")
def test_profile_requires_token(anon):
    assert anon.get(PROFILE).status_code == 401
    assert anon.put(PROFILE, json={}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A13")
def test_profile_foreign_tenant_header(role_client):
    client = role_client(GRANTS)
    foreign = Api(token=client.token, tenant_header="qa_school_b")
    try:
        assert foreign.get(PROFILE).status_code == 403
    finally:
        foreign.close()
    own = Api(token=client.token, tenant_header=QA_TENANT)
    try:
        assert own.get(PROFILE).status_code == 200
    finally:
        own.close()


@pytest.mark.api
@pytest.mark.tc("TC-STF-12-A14")
@pytest.mark.skip(reason="asserts profile_audit_logs rows in the database; the API tests have no database access")
def test_profile_view_writes_audit_row():
    pass
