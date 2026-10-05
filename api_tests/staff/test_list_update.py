import uuid

import pytest

from api_tests.staff.helpers import (
    TEMP_PASSWORD,
    email_address,
    expected_status,
    granted,
    phone_number,
    rand_past_date,
    staff_payload,
)
from api_tests.support import QA_TENANT, Api, unique

ENROLL = "/staff/enrollment"
LIST_CALLS = [
    ("list", "/staff/enrollments"),
    ("list", "/staff/"),
    ("list", "/staff/by-designation"),
]


def ids(items):
    return [item["id"] for item in items]


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A01")
def test_enrollments_list_includes_active_and_inactive(admin, make_staff):
    active = make_staff()
    inactive = make_staff(is_active=False)
    response = admin.get("/staff/enrollments")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()}
    assert active["id"] in items and inactive["id"] in items
    assert items[inactive["id"]]["is_active"] is False
    for item in (items[active["id"]], items[inactive["id"]]):
        assert "designation_id" in item and "qualifications" in item and "photo_url" in item
        assert item["created_at"] is None


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A02")
def test_enrollment_detail(admin, make_staff):
    staff = make_staff(current_salary="1234.50")
    admin.post(f"/staff/{staff['id']}/qualifications", json={"level": "PhD", "name": "Ph.D", "percentage": 80})
    response = admin.get(f"{ENROLL}/{staff['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["current_salary"] == "1234.50"
    assert data["qualifications"][0]["percentage"] == "80.00"
    assert data["user_id"] == staff["user_id"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A03")
def test_enrollment_detail_unknown_and_malformed(admin):
    response = admin.get(f"{ENROLL}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Staff not found"
    assert admin.get(f"{ENROLL}/abc").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A04")
def test_staff_list_shape(admin, make_staff, make_designation):
    designation = make_designation()
    staff = make_staff(designation_id=designation["id"])
    response = admin.get("/staff/")
    assert response.status_code == 200
    item = next(i for i in response.json() if i["id"] == staff["id"])
    assert item["designation_obj"] == {"id": designation["id"], "title": designation["title"]}
    assert "designation_id" not in item


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A05")
def test_staff_list_gender_filter(admin, make_staff):
    female = make_staff(gender="Female")
    male = make_staff(gender="Male")
    response = admin.get("/staff/", params={"gender": "Female"})
    assert response.status_code == 200
    assert all(item["gender"] == "Female" for item in response.json())
    assert female["id"] in ids(response.json()) and male["id"] not in ids(response.json())


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A05")
def test_staff_list_unknown_gender_is_rejected(admin):
    assert admin.get("/staff/", params={"gender": "Unknown"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A06")
def test_staff_list_ignores_is_active_and_paging(admin, make_staff):
    active = make_staff()
    inactive = make_staff(is_active=False)
    response = admin.get("/staff/", params={"is_active": "true", "skip": 0, "limit": 1})
    assert response.status_code == 200
    assert active["id"] in ids(response.json()) and inactive["id"] in ids(response.json())
    assert len(response.json()) >= 2


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A07")
def test_by_designation_filter(admin, make_staff, make_designation):
    one = make_designation()
    two = make_designation()
    mine = make_staff(designation_id=one["id"])
    other = make_staff(designation_id=two["id"])
    response = admin.get("/staff/by-designation", params={"designation_id": one["id"]})
    assert response.status_code == 200
    assert ids(response.json()) == [mine["id"]]
    assert other["id"] not in ids(response.json())


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A08")
def test_by_designation_without_unknown_and_malformed(admin, make_staff):
    staff = make_staff()
    assert staff["id"] in ids(admin.get("/staff/by-designation").json())
    assert admin.get("/staff/by-designation", params={"designation_id": str(uuid.uuid4())}).json() == []
    assert admin.get("/staff/by-designation", params={"designation_id": "abc"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A09")
def test_by_designation_does_not_leak_password_hash(admin, make_staff, make_designation):
    designation = make_designation()
    make_staff(designation_id=designation["id"])
    response = admin.get("/staff/by-designation", params={"designation_id": designation["id"]})
    assert response.status_code == 200
    assert "password_hash" not in response.text
    assert all("user" not in item for item in response.json())


@pytest.mark.api
@pytest.mark.parametrize(
    "role",
    [
        pytest.param("admin", marks=pytest.mark.tc("TC-STF-06-A10")),
        pytest.param("staff", marks=pytest.mark.tc("TC-STF-06-A10")),
        pytest.param("teacher", marks=pytest.mark.tc("TC-STF-06-A11")),
        pytest.param("student", marks=pytest.mark.tc("TC-STF-06-A11")),
        pytest.param("parent", marks=pytest.mark.tc("TC-STF-06-A11")),
    ],
)
def test_staff_read_endpoints_role_matrix(role_clients, logins, make_staff, role):
    staff = make_staff()
    client = role_clients[role]
    for action, path in LIST_CALLS:
        assert client.get(path).status_code == expected_status(logins, role, "staff", action), path
    assert client.get(f"{ENROLL}/{staff['id']}").status_code == expected_status(logins, role, "staff", "read")


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A12")
def test_staff_read_endpoints_require_token(anon):
    for path in ["/staff/enrollments", "/staff/", "/staff/by-designation", f"{ENROLL}/{uuid.uuid4()}"]:
        assert anon.get(path).status_code == 401, path


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A13")
def test_staff_read_tenant_isolation(tenant_b, make_staff, make_designation):
    designation = make_designation()
    staff = make_staff(designation_id=designation["id"])
    assert staff["id"] not in ids(tenant_b.get("/staff/enrollments").json())
    assert staff["id"] not in ids(tenant_b.get("/staff/").json())
    assert staff["id"] not in ids(tenant_b.get("/staff/by-designation").json())
    assert tenant_b.get("/staff/by-designation", params={"designation_id": designation["id"]}).json() == []
    assert tenant_b.get(f"{ENROLL}/{staff['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STF-06-A14")
def test_staff_read_foreign_tenant_header(b_header_client):
    for path in ["/staff/enrollments", "/staff/", "/staff/by-designation"]:
        assert b_header_client.get(path).status_code == 403, path


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A01")
def test_patch_changes_only_sent_field(admin, make_staff):
    staff = make_staff(department="Arts", last_name="Rao")
    before = admin.get(f"{ENROLL}/{staff['id']}").json()
    response = admin.patch(f"{ENROLL}/{staff['id']}", json={"department": "Science"})
    assert response.status_code == 200
    after = response.json()
    assert after["department"] == "Science"
    for key in before:
        if key != "department":
            assert after[key] == before[key], key


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A02")
def test_deactivate_keeps_row_in_list(admin, make_staff):
    staff = make_staff()
    response = admin.patch(f"{ENROLL}/{staff['id']}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    listed = {i["id"]: i for i in admin.get("/staff/enrollments").json()}
    assert listed[staff["id"]]["is_active"] is False
    assert admin.patch(f"{ENROLL}/{staff['id']}", json={"is_active": True}).json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A03")
@pytest.mark.parametrize(
    "payload",
    [{"first_name": ""}, {"email": None}, {"phone": " "}, {"address": ""}],
    ids=["first_name", "email", "phone", "address"],
)
def test_patch_mandatory_fields_cannot_be_cleared(admin, make_staff, payload):
    staff = make_staff()
    response = admin.patch(f"{ENROLL}/{staff['id']}", json=payload)
    assert response.status_code == 422
    assert "mandatory and cannot be empty" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A04")
@pytest.mark.parametrize(
    "payload",
    [{"email": "bad"}, {"gender": "male"}, {"account_type": "Fixed"}],
    ids=["email", "gender", "account_type"],
)
def test_patch_invalid_values(admin, make_staff, payload):
    staff = make_staff()
    assert admin.patch(f"{ENROLL}/{staff['id']}", json=payload).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A05")
def test_patch_unknown_designation(admin, make_staff):
    staff = make_staff()
    response = admin.patch(f"{ENROLL}/{staff['id']}", json={"designation_id": str(uuid.uuid4())})
    assert response.status_code == 400
    assert response.json()["detail"] == "Data integrity violation - check for duplicate values or invalid references"


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A06")
def test_patch_duplicate_email(admin, make_staff):
    first = make_staff(email=email_address())
    second = make_staff(email=email_address())
    response = admin.patch(f"{ENROLL}/{second['id']}", json={"email": first["_body"]["email"]})
    assert response.status_code == 400
    assert response.json()["detail"] == "Data integrity violation - check for duplicate values or invalid references"
    assert admin.get(f"{ENROLL}/{second['id']}").json()["email"] == second["_body"]["email"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A07")
def test_patch_role_id_is_dropped(admin, make_staff, logins):
    staff = make_staff()
    response = admin.patch(f"{ENROLL}/{staff['id']}", json={"role_id": logins["admin"]["role"]["id"]})
    assert response.status_code == 200
    user = admin.get(f"/admin/users/{staff['user_id']}").json()
    assert user["role_id"] == logins["staff"]["role"]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A08")
def test_email_edit_does_not_change_login(admin, make_staff, academic_year_id):
    old = email_address()
    new = email_address()
    staff = make_staff(email=old)
    assert admin.patch(f"{ENROLL}/{staff['id']}", json={"email": new}).status_code == 200
    client = Api(tenant_header=QA_TENANT)
    try:
        body = {"password": TEMP_PASSWORD, "academic_year_id": academic_year_id}
        assert client.post("/auth/login", json={"username": old, **body}).status_code == 200
        assert client.post("/auth/login", json={"username": new, **body}).status_code == 401
    finally:
        client.close()
    assert admin.get(f"/admin/users/{staff['user_id']}").json()["username"] == old


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A09")
def test_patch_null_clears_optional_field(admin, make_staff):
    staff = make_staff(last_name="Rao")
    response = admin.patch(f"{ENROLL}/{staff['id']}", json={"last_name": None})
    assert response.status_code == 200
    assert response.json()["last_name"] is None


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A10")
def test_patch_salary_as_string_and_number(admin, make_staff):
    staff = make_staff()
    as_string = admin.patch(f"{ENROLL}/{staff['id']}", json={"current_salary": "60000.50"})
    as_number = admin.patch(f"{ENROLL}/{staff['id']}", json={"current_salary": 60000.5})
    assert as_string.status_code == 200 and as_number.status_code == 200
    assert as_string.json()["current_salary"] == "60000.50"
    assert admin.get(f"{ENROLL}/{staff['id']}").json()["current_salary"] == "60000.50"


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A11")
def test_patch_unknown_id(admin):
    response = admin.patch(f"{ENROLL}/{uuid.uuid4()}", json={"department": "X"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Staff not found"


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A12")
def test_delete_removes_attendance_and_qualifications(admin, make_staff):
    staff = make_staff()
    attendance = []
    for status in ("absent", "late"):
        row = admin.post("/staff/attendance", json={"staff_id": staff["id"], "date": rand_past_date(1960, 1975), "status": status})
        assert row.status_code == 200
        attendance.append(row.json()["id"])
    for name in ("B.Sc", "M.Sc"):
        admin.post(f"/staff/{staff['id']}/qualifications", json={"level": "Graduation", "name": name})
    response = admin.delete(f"{ENROLL}/{staff['id']}")
    assert response.status_code == 200
    assert response.json() == {"detail": "Staff enrollment deleted successfully"}
    assert admin.get(f"{ENROLL}/{staff['id']}").status_code == 404
    for attendance_id in attendance:
        assert admin.get(f"/staff/attendance/{attendance_id}").status_code == 404
    assert admin.get(f"/staff/{staff['id']}/qualifications").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A13")
def test_login_survives_staff_deletion(admin, make_staff, academic_year_id):
    staff = make_staff()
    assert admin.delete(f"{ENROLL}/{staff['id']}").status_code == 200
    client = Api(tenant_header=QA_TENANT)
    try:
        response = client.post(
            "/auth/login",
            json={"username": staff["phone"], "password": TEMP_PASSWORD, "academic_year_id": academic_year_id},
        )
    finally:
        client.close()
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A14")
def test_reenrolling_deleted_staff_email_fails(admin, make_staff):
    email = email_address()
    staff = make_staff(email=email)
    assert admin.delete(f"{ENROLL}/{staff['id']}").status_code == 200
    response = admin.post(ENROLL, json=staff_payload(email=email))
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Error creating staff enrollment")


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A15")
def test_delete_unknown_id(admin):
    assert admin.delete(f"{ENROLL}/{uuid.uuid4()}").status_code == 404


@pytest.mark.api
@pytest.mark.parametrize(
    "role",
    [
        pytest.param("staff", marks=pytest.mark.tc("TC-STF-07-A16")),
        pytest.param("teacher", marks=pytest.mark.tc("TC-STF-07-A17")),
        pytest.param("student", marks=pytest.mark.tc("TC-STF-07-A17")),
        pytest.param("parent", marks=pytest.mark.tc("TC-STF-07-A17")),
    ],
)
def test_patch_and_delete_denied_for_non_admin(role_clients, logins, make_staff, role):
    assert not granted(logins, role, "staff", "update") and not granted(logins, role, "staff", "delete")
    staff = make_staff(department="Original")
    client = role_clients[role]
    assert client.patch(f"{ENROLL}/{staff['id']}", json={"department": "Hacked"}).status_code == 403
    assert client.delete(f"{ENROLL}/{staff['id']}").status_code == 403
    assert role_clients["admin"].get(f"{ENROLL}/{staff['id']}").json()["department"] == "Original"


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A18")
def test_admin_patch_and_delete(admin, make_staff):
    staff = make_staff()
    assert admin.patch(f"{ENROLL}/{staff['id']}", json={"department": unique("d")}).status_code == 200
    assert admin.delete(f"{ENROLL}/{staff['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A19")
def test_patch_and_delete_require_token(anon):
    target = f"{ENROLL}/{uuid.uuid4()}"
    assert anon.patch(target, json={"department": "x"}).status_code == 401
    assert anon.delete(target).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STF-07-A20")
def test_patch_and_delete_tenant_isolation(admin, tenant_b, make_staff):
    staff = make_staff(department="Original")
    patch = tenant_b.patch(f"{ENROLL}/{staff['id']}", json={"department": "Hacked"})
    assert patch.status_code == 404 and patch.json()["detail"] == "Staff not found"
    assert tenant_b.delete(f"{ENROLL}/{staff['id']}").status_code == 404
    assert admin.get(f"{ENROLL}/{staff['id']}").json()["department"] == "Original"
