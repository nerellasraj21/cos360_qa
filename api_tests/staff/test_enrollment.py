import uuid

import pytest

from api_tests.staff.helpers import (
    TEMP_PASSWORD,
    email_address,
    granted,
    phone_number,
    remove_staff,
    staff_payload,
)
from api_tests.support import QA_B_TENANT, QA_TENANT, Api, unique

ENROLL = "/staff/enrollment"


def enroll(admin, cleanup, **overrides):
    body = staff_payload(**overrides)
    response = admin.post(ENROLL, json=body)
    if response.status_code == 200:
        cleanup.add(remove_staff, admin, response.json())
    return body, response


def names_in_list(admin, name):
    return [s for s in admin.get("/staff/enrollments").json() if s["first_name"] == name]


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A01")
def test_minimal_enrollment(admin, cleanup, logins):
    body, response = enroll(admin, cleanup)
    assert response.status_code == 200
    data = response.json()
    assert data["qualifications"] == []
    assert data["is_active"] is True
    user = admin.get(f"/admin/users/{data['user_id']}").json()
    assert user["username"] == body["phone"]
    assert user["role_name"] == "Staff"
    assert user["role_id"] == logins["staff"]["role"]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A02")
def test_full_enrollment_echoes_fields(admin, cleanup, make_designation):
    designation = make_designation()
    email = email_address()
    payload = {
        "last_name": "Nair",
        "email": email,
        "gender": "Male",
        "date_of_birth": "1988-04-05",
        "joining_date": "2020-06-01",
        "qualification": "B.Ed",
        "experience_years": 7,
        "designation_id": designation["id"],
        "department": "Science",
        "work_org": "Old School",
        "work_from_date": "2012-01-01",
        "work_to_date": "2019-12-31",
        "subjects_dealt": "Maths",
        "work_remarks": "good",
        "bank_name": "SBI",
        "bank_branch": "MG Road",
        "account_number": "1234567890",
        "ifsc_code": "SBIN0000001",
        "account_holder_name": "Kiran Nair",
        "account_type": "Savings",
        "last_drawn_salary": "40000.00",
        "current_salary": "50000.00",
        "pf_account_number": "AP/HYD/12345",
        "uan_number": "123456789012",
    }
    body, response = enroll(admin, cleanup, **payload)
    assert response.status_code == 200
    data = response.json()
    for key, value in payload.items():
        if key in ("last_drawn_salary", "current_salary"):
            continue
        assert data[key] == value, key
    assert data["current_salary"] == "50000.00"
    assert data["last_drawn_salary"] == "40000.00"
    user = admin.get(f"/admin/users/{data['user_id']}").json()
    assert user["username"] == email
    assert user["email"] == email


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A03")
@pytest.mark.parametrize("missing", ["first_name", "phone", "address"])
def test_missing_required_field(admin, missing):
    body = staff_payload()
    del body[missing]
    response = admin.post(ENROLL, json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", missing]


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A04")
@pytest.mark.parametrize("field", ["phone", "address"])
def test_empty_required_field(admin, field):
    response = admin.post(ENROLL, json=staff_payload(**{field: ""}))
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A05")
def test_invalid_email(admin):
    assert admin.post(ENROLL, json=staff_payload(email="kiran@")).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A06")
def test_gender_conversion_and_rejection(admin, cleanup):
    _, ok = enroll(admin, cleanup, gender="female")
    assert ok.status_code == 200
    assert ok.json()["gender"] == "Female"
    name = unique("stf_g_")
    bad = admin.post(ENROLL, json=staff_payload(first_name=name, gender="Unknown"))
    assert bad.status_code == 400
    assert bad.json()["detail"] == "Invalid gender value: Unknown. Must be 'Male', 'Female', or 'Other'"
    assert names_in_list(admin, name) == []


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A07")
def test_invalid_account_type(admin):
    assert admin.post(ENROLL, json=staff_payload(account_type="Fixed")).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A08")
def test_enroll_with_teacher_role(admin, cleanup, logins):
    _, response = enroll(admin, cleanup, role_id=logins["teacher"]["role"]["id"])
    assert response.status_code == 200
    user = admin.get(f"/admin/users/{response.json()['user_id']}").json()
    assert user["role_id"] == logins["teacher"]["role"]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A09")
def test_staff_create_holder_can_create_admin_login(role_client, admin, logins):
    client = role_client([("staff", "create")])
    body = staff_payload(role_id=logins["admin"]["role"]["id"])
    response = client.post(ENROLL, json=body)
    assert response.status_code == 200
    created = response.json()
    try:
        user = admin.get(f"/admin/users/{created['user_id']}").json()
        assert user["role_name"] == "Admin"
    finally:
        admin.delete(f"{ENROLL}/{created['id']}")
        admin.patch(f"/admin/users/{created['user_id']}", json={"is_active": False})
        admin.put(f"/admin/users/{created['user_id']}/role", json={"role_id": logins["staff"]["role"]["id"]})


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A10")
@pytest.mark.skip(reason="the QA tenant has a Staff role and the shared role cannot be removed")
def test_missing_default_staff_role():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A11")
def test_unknown_role_id(admin):
    name = unique("stf_r_")
    response = admin.post(ENROLL, json=staff_payload(first_name=name, role_id=str(uuid.uuid4())))
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Error creating staff enrollment")
    assert names_in_list(admin, name) == []


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A12")
def test_unknown_designation_id_rolls_back(admin):
    name = unique("stf_d_")
    email = email_address()
    response = admin.post(ENROLL, json=staff_payload(first_name=name, email=email, designation_id=str(uuid.uuid4())))
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Error creating staff enrollment")
    assert names_in_list(admin, name) == []
    again = admin.post(ENROLL, json=staff_payload(first_name=name, email=email))
    assert again.status_code == 200
    admin.delete(f"{ENROLL}/{again.json()['id']}")
    admin.patch(f"/admin/users/{again.json()['user_id']}", json={"is_active": False})


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A13")
def test_duplicate_email_rejected(admin, cleanup):
    email = email_address()
    enroll(admin, cleanup, email=email)
    name = unique("stf_dup_")
    response = admin.post(ENROLL, json=staff_payload(first_name=name, email=email))
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Error creating staff enrollment")
    assert names_in_list(admin, name) == []


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A14")
def test_duplicate_phone_without_email(admin, cleanup):
    phone = phone_number()
    enroll(admin, cleanup, phone=phone)
    response = admin.post(ENROLL, json=staff_payload(phone=phone))
    assert response.status_code == 500


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A15")
def test_same_email_in_two_tenants(admin, tenant_b, cleanup):
    email = email_address()
    _, a = enroll(admin, cleanup, email=email)
    assert a.status_code == 200
    response = tenant_b.post(ENROLL, json=staff_payload(email=email))
    assert response.status_code == 200, response.text
    created = response.json()
    cleanup.add(tenant_b.patch, f"/admin/users/{created['user_id']}", json={"is_active": False})
    cleanup.add(tenant_b.delete, f"{ENROLL}/{created['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A16")
def test_first_name_length_boundary(admin, cleanup):
    ok = "stf" + unique("")[:8] + "n" * 89
    assert len(ok) == 100
    _, response = enroll(admin, cleanup, first_name=ok)
    assert response.status_code == 200
    bad = admin.post(ENROLL, json=staff_payload(first_name=ok + "n"))
    assert bad.status_code == 500


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A17")
def test_phone_length_boundary(admin, cleanup):
    ok = "9" + "".join(str(uuid.uuid4().int % 10) for _ in range(14))
    assert len(ok) == 15
    _, response = enroll(admin, cleanup, phone=ok)
    assert response.status_code == 200
    bad = admin.post(ENROLL, json=staff_payload(phone=ok + "1"))
    assert bad.status_code == 500


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A18")
def test_salary_boundary(admin, cleanup):
    _, ok = enroll(admin, cleanup, current_salary="99999999.99")
    assert ok.status_code == 200
    assert ok.json()["current_salary"] == "99999999.99"
    bad = admin.post(ENROLL, json=staff_payload(current_salary="100000000"))
    assert bad.status_code == 500


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A19")
def test_unvalidated_fields_accepted(admin, cleanup):
    _, response = enroll(admin, cleanup, experience_years=-1, uan_number="abc", pf_account_number="x")
    assert response.status_code == 200
    data = response.json()
    assert (data["experience_years"], data["uan_number"], data["pf_account_number"]) == (-1, "abc", "x")


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A20")
def test_whitespace_phone_not_trimmed(admin, cleanup):
    padded = f"  {phone_number()}  "
    _, response = enroll(admin, cleanup, phone=padded)
    assert response.status_code == 200
    assert response.json()["phone"] == padded
    user = admin.get(f"/admin/users/{response.json()['user_id']}").json()
    assert user["username"] == padded


@pytest.mark.api
@pytest.mark.parametrize(
    "role",
    [
        pytest.param("staff", marks=pytest.mark.tc("TC-STF-02-A21")),
        pytest.param("teacher", marks=pytest.mark.tc("TC-STF-02-A22")),
        pytest.param("student", marks=pytest.mark.tc("TC-STF-02-A22")),
        pytest.param("parent", marks=pytest.mark.tc("TC-STF-02-A22")),
    ],
)
def test_enroll_denied_for_non_admin_roles(role_clients, logins, role):
    assert not granted(logins, role, "staff", "create")
    name = unique("stf_den_")
    response = role_clients[role].post(ENROLL, json=staff_payload(first_name=name))
    assert response.status_code == 403
    assert names_in_list(role_clients["admin"], name) == []


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A23")
def test_enroll_requires_token(anon):
    assert anon.post(ENROLL, json=staff_payload()).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A24")
def test_enrollment_tenant_isolation(admin, tenant_b, b_header_client, cleanup):
    body, response = enroll(admin, cleanup)
    created = response.json()
    in_b = tenant_b.get("/staff/enrollments").json()
    assert created["id"] not in [s["id"] for s in in_b]
    assert tenant_b.get(f"{ENROLL}/{created['id']}").status_code == 404
    assert b_header_client.get("/staff/enrollments").status_code == 403
    assert b_header_client.post(ENROLL, json=staff_payload()).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STF-02-A25")
def test_created_row_shape(admin, cleanup):
    _, response = enroll(admin, cleanup)
    assert response.status_code == 200
    data = response.json()
    for key in ("id", "user_id", "photo_url", "qualifications"):
        assert key in data
    assert data["photo_url"] is None
    assert data["created_at"] is None and data["updated_at"] is None


def first_login(username, year_id, password=TEMP_PASSWORD, tenant=QA_TENANT):
    client = Api(tenant_header=tenant)
    try:
        return client.post(
            "/auth/login", json={"username": username, "password": password, "academic_year_id": year_id}
        )
    finally:
        client.close()


def set_password(token, new="Newpass@123", confirm=None):
    client = Api(tenant_header=QA_TENANT)
    try:
        return client.post(
            "/auth/staff/set-password",
            json={
                "change_password_token": token,
                "new_password": new,
                "confirm_password": new if confirm is None else confirm,
            },
        )
    finally:
        client.close()


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A01")
def test_first_login_with_email(make_staff, academic_year_id):
    staff = make_staff(email=email_address())
    response = first_login(staff["_login"], academic_year_id)
    assert response.status_code == 200
    data = response.json()
    assert data["requires_password_change"] is True
    assert data["change_password_token"]
    assert "access_token" not in data


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A02")
def test_first_login_with_phone_only(make_staff, academic_year_id):
    staff = make_staff()
    response = first_login(staff["phone"], academic_year_id)
    assert response.status_code == 200
    assert response.json()["requires_password_change"] is True


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A03")
def test_set_password_returns_full_login(make_staff, academic_year_id):
    staff = make_staff()
    token = first_login(staff["phone"], academic_year_id).json()["change_password_token"]
    response = set_password(token)
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == staff["id"]
    assert data["role"]["name"] == "Staff"
    assert data["access_token"] and data["refresh_token"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A04")
def test_change_token_is_single_use(make_staff, academic_year_id):
    staff = make_staff()
    token = first_login(staff["phone"], academic_year_id).json()["change_password_token"]
    assert set_password(token).status_code == 200
    assert set_password(token).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A05")
def test_set_password_mismatch(make_staff, academic_year_id):
    staff = make_staff()
    token = first_login(staff["phone"], academic_year_id).json()["change_password_token"]
    response = set_password(token, confirm="Different@123")
    assert response.status_code == 400
    assert response.json()["detail"] == "Passwords do not match"


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A06")
def test_set_password_too_short(make_staff, academic_year_id):
    staff = make_staff()
    token = first_login(staff["phone"], academic_year_id).json()["change_password_token"]
    assert set_password(token, new="short12").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A07")
def test_set_password_bad_token(anon):
    assert set_password("not-a-token").status_code == 401
    assert set_password("a.b.c").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A08")
def test_new_password_replaces_temporary(make_staff, academic_year_id):
    staff = make_staff()
    token = first_login(staff["phone"], academic_year_id).json()["change_password_token"]
    assert set_password(token).status_code == 200
    after = first_login(staff["phone"], academic_year_id, password="Newpass@123")
    assert after.status_code == 200
    assert "requires_password_change" not in after.json() or not after.json()["requires_password_change"]
    assert after.json()["access_token"]
    assert first_login(staff["phone"], academic_year_id).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A09")
def test_admin_role_is_not_forced_to_change_password(admin, logins, academic_year_id, cleanup):
    body = staff_payload(role_id=logins["admin"]["role"]["id"])
    response = admin.post(ENROLL, json=body)
    assert response.status_code == 200
    created = response.json()
    staff_role = logins["staff"]["role"]["id"]
    cleanup.add(admin.put, f"/admin/users/{created['user_id']}/role", json={"role_id": staff_role})
    cleanup.add(remove_staff, admin, created)
    login = first_login(body["phone"], academic_year_id)
    assert login.status_code == 200
    assert login.json().get("access_token")
    assert not login.json().get("requires_password_change")


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A10")
def test_inactive_staff_flag_does_not_block_login(admin, make_staff, academic_year_id):
    staff = make_staff()
    assert admin.patch(f"{ENROLL}/{staff['id']}", json={"is_active": False}).status_code == 200
    assert first_login(staff["phone"], academic_year_id).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A11")
def test_inactive_user_cannot_log_in(admin, make_staff, academic_year_id):
    staff = make_staff()
    assert admin.patch(f"/admin/users/{staff['user_id']}", json={"is_active": False}).status_code == 200
    assert first_login(staff["phone"], academic_year_id).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A12")
def test_login_requires_valid_academic_year(make_staff):
    staff = make_staff()
    client = Api(tenant_header=QA_TENANT)
    missing = client.post("/auth/login", json={"username": staff["phone"], "password": TEMP_PASSWORD})
    wrong = client.post(
        "/auth/login",
        json={"username": staff["phone"], "password": TEMP_PASSWORD, "academic_year_id": str(uuid.uuid4())},
    )
    client.close()
    assert missing.status_code == 422
    assert wrong.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-STF-03-A13")
def test_login_isolated_between_tenants(make_staff, academic_year_id, tenant_b):
    staff = make_staff(email=email_address())
    other = first_login(staff["_login"], tenant_b.academic_year_id, tenant=QA_B_TENANT)
    assert other.status_code == 401
    assert first_login(staff["_login"], academic_year_id).status_code == 200
