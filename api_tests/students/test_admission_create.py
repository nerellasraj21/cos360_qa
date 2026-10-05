import re

import pytest

from api_tests.students import helpers as h
from api_tests.support import QA_TENANT, Api, items_of, unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]
NUMBER = re.compile(r"^\d{3,}$")


def nested_loc(response):
    return [".".join(str(p) for p in err["loc"]) for err in response.json()["detail"]]


def attempt(admin, body, cleanup):
    response = h.post_admission(admin, body)
    if response.status_code == 201:
        cleanup.delete_later(admin, f"/students/admission/{response.json()['id']}")
    return response


def fetch(admin, student_id):
    response = admin.get(f"/students/admission/id/{student_id}")
    assert response.status_code == 200, response.text
    return response.json()


def stable_preview(admin, **params):
    last = None
    for _ in range(6):
        first = admin.get("/students/admission/next-admission-number", params=params)
        second = admin.get("/students/admission/next-admission-number", params=params)
        assert first.status_code == 200 and second.status_code == 200
        if first.json() == second.json():
            return first.json()
        last = first.json()
    return last


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A01")
def test_preview_regular_shape(admin):
    response = admin.get("/students/admission/next-admission-number")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"next_number", "format", "type", "note"}
    assert NUMBER.match(body["next_number"])
    assert body["format"] == "{SEQ:03d}"
    assert body["type"] == "regular"
    assert body["note"].startswith("Preview only")


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A02")
def test_preview_pre_primary_shape(admin):
    response = admin.get("/students/admission/next-admission-number", params={"type": "pre_primary"})
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "{YEAR}{SEQ:04d}"
    assert body["type"] == "pre_primary"
    assert re.match(rf"^{h.today().year}\d{{4}}$", body["next_number"])


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A03")
def test_preview_type_defaults_to_regular(admin):
    default = admin.get("/students/admission/next-admission-number").json()
    explicit = admin.get("/students/admission/next-admission-number", params={"type": "regular"}).json()
    assert default["type"] == explicit["type"] == "regular"
    assert default["format"] == explicit["format"]


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A04")
@pytest.mark.parametrize("value", ["primary", ""])
def test_preview_rejects_unknown_type(admin, value):
    response = admin.get("/students/admission/next-admission-number", params={"type": value})
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A05")
def test_preview_reserves_nothing_and_advances_after_create(admin, make_admission):
    before = stable_preview(admin)
    again = admin.get("/students/admission/next-admission-number").json()
    assert NUMBER.match(again["next_number"])
    created = make_admission()
    assert NUMBER.match(created.number)
    after = admin.get("/students/admission/next-admission-number").json()
    assert after["next_number"] != before["next_number"]


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A06")
@pytest.mark.parametrize("role,status", [("admin", 200), ("staff", 200), ("teacher", 403), ("student", 403), ("parent", 403)])
def test_preview_permission_matrix(role_clients, role, status):
    assert role_clients[role].get("/students/admission/next-admission-number").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A07")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 403), ("parent", 403)]
)
def test_admission_types_dropdown_matrix(role_clients, role, status):
    response = role_clients[role].get("/students/admission/admission-types/dropdown")
    assert response.status_code == status
    if status == 200:
        assert response.json() == [
            {"value": "pre_primary", "label": "Pre Primary Admission"},
            {"value": "regular", "label": "Regular Admission"},
        ]


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A08")
@pytest.mark.parametrize("path", ["/students/admission/next-admission-number", "/students/admission/admission-types/dropdown"])
def test_preview_requires_token(anon, path):
    assert anon.get(path).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A09")
def test_preview_tenant_isolation(admin, tenant_b, make_admission, tenant_b_name):
    before = stable_preview(tenant_b)
    make_admission()
    after = stable_preview(tenant_b)
    assert NUMBER.match(after["next_number"])
    assert after == before
    assert admin.get("/students/admission/next-admission-number", headers={"cschema": tenant_b_name}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A10")
def test_blank_numbers_are_generated_and_distinct(make_admission):
    first = make_admission()
    second = make_admission()
    assert NUMBER.match(first.number) and NUMBER.match(second.number)
    assert first.number != second.number


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A11")
def test_manual_number_conflicts(admin, academic_year_id, klass, make_admission, cleanup):
    number = unique("stu_n")
    make_admission(admission_number=number)
    duplicate = attempt(admin, h.admission_payload(academic_year_id, klass, admission_number=number), cleanup)
    assert duplicate.status_code == 422
    assert duplicate.json()["detail"]["message"] == f"Admission number '{number}' is already in use"
    login_clash = attempt(admin, h.admission_payload(academic_year_id, klass, admission_number="qa_admin"), cleanup)
    assert login_clash.status_code == 422
    assert login_clash.json()["detail"]["message"] == "Admission number 'qa_admin' is already in use as a login"


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A12")
def test_manual_number_becomes_username(make_admission):
    number = unique("stu_m").upper()
    created = make_admission(admission_number=number)
    assert created.data["admission_number"] == number
    data = h.set_first_password(QA_TENANT, number, h.STUDENT_DEFAULT_PASSWORD)
    assert data["user"]["username"] == number


@pytest.mark.api
@pytest.mark.tc("TC-STU-02-A13")
def test_pre_primary_number_uses_admission_year(make_admission):
    created = make_admission(admission_type="pre_primary", admission_date="2025-06-01")
    assert created.number.startswith("2025")
    assert created.data["admission_type"] == "pre_primary"


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A01")
def test_minimal_admission_defaults(admin, academic_year_id, klass, cleanup):
    body = {
        "academic_year_id": academic_year_id,
        "admitted_class_id": klass["id"],
        "address_line1": "1 Minimal Road",
        "student": {
            "first_name": unique("stu_min"),
            "last_name": "",
            "date_of_birth": None,
            "father": {"phone": "9876543210", "relation_to_student": "Father"},
            "mother": {"relation_to_student": "Mother"},
        },
    }
    response = attempt(admin, body, cleanup)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["admission_date"] == h.iso(h.today())
    assert data["admission_type"] == "regular"
    assert NUMBER.match(data["admission_number"])
    full = fetch(admin, data["student"]["id"])
    assert full["student"]["last_name"] == ""
    assert full["student"]["date_of_birth"] == "1900-01-01"
    assert full["student"]["mother"]["name"] == "Mother"


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A01")
def test_omitted_date_of_birth_is_defaulted(admin, academic_year_id, klass, cleanup):
    body = h.admission_payload(academic_year_id, klass)
    del body["student"]["date_of_birth"]
    response = attempt(admin, body, cleanup)
    assert response.status_code == 201, response.text
    assert fetch(admin, response.json()["student"]["id"])["student"]["date_of_birth"] == "1900-01-01"


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A02")
def test_full_admission_echoes_fields(admin, academic_year_id, klass, cleanup):
    tag = unique("stu_full")
    body = h.admission_payload(
        academic_year_id,
        klass,
        tag=tag,
        address_line2="Near Park",
        city="Hyderabad",
        is_previous_school=True,
        previous_school_name="Old School",
        previous_class="UKG",
        previous_school_remark="Good",
        student={
            "aadhar_number": "123456789012",
            "apaar_number": "210987654321",
            "caste": "OC",
            "community": "General",
            "nationality": "Indian",
            "mother_tongue": "Hindi",
            "identification_marks": "Mole on chin",
            "primary_phone": "9123456780",
            "guardian": {
                "name": f"{tag} Guardian",
                "email": f"{tag}.guardian@example.com",
                "phone": "9123456781",
                "relation_to_student": "Guardian",
            },
        },
    )
    response = attempt(admin, body, cleanup)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["address_line2"] == "Near Park"
    assert created["city"] == "Hyderabad"
    assert created["is_previous_school"] is True
    assert created["previous_school_name"] == "Old School"
    assert created["previous_class"] == "UKG"
    assert created["previous_school_remark"] == "Good"
    full = fetch(admin, created["student"]["id"])
    student = full["student"]
    assert student["aadhar_number"] == "123456789012"
    assert student["apaar_number"] == "210987654321"
    assert student["primary_phone"] == "9123456780"
    assert student["mother_tongue"] == "Hindi"
    assert student["identification_marks"] == "Mole on chin"
    assert student["father"]["name"] == f"{tag} Father"
    assert student["mother"]["name"] == f"{tag} Mother"
    assert student["guardian"]["name"] == f"{tag} Guardian"


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A02")
@pytest.mark.xfail(strict=True, reason="STU-BUG-2: POST /students/admission/ response has student.father, mother and guardian null")
def test_create_response_carries_parents(admin, academic_year_id, klass, cleanup):
    response = attempt(admin, h.admission_payload(academic_year_id, klass), cleanup)
    assert response.status_code == 201
    student = response.json()["student"]
    assert student["father"] is not None
    assert student["mother"] is not None


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A03")
def test_primary_student_becomes_pre_primary(admin, academic_year_id, klass, cleanup):
    body = h.admission_payload(academic_year_id, klass, student={"is_primary": "primary"})
    del body["admission_type"]
    response = attempt(admin, body, cleanup)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["admission_type"] == "pre_primary"
    assert data["admission_number"].startswith(str(h.today().year))


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A04")
def test_explicit_regular_wins_over_primary(admin, academic_year_id, klass, cleanup):
    body = h.admission_payload(academic_year_id, klass, admission_type="regular", student={"is_primary": "primary"})
    response = attempt(admin, body, cleanup)
    assert response.status_code == 201, response.text
    assert response.json()["admission_type"] == "regular"
    assert NUMBER.match(response.json()["admission_number"])


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A05")
@pytest.mark.parametrize(
    "field",
    ["academic_year_id", "admitted_class_id", "address_line1", "student.first_name", "student.father", "student.mother"],
)
def test_missing_required_field_is_422(admin, academic_year_id, klass, cleanup, field):
    body = h.admission_payload(academic_year_id, klass)
    target = body
    parts = field.split(".")
    for part in parts[:-1]:
        target = target[part]
    del target[parts[-1]]
    response = attempt(admin, body, cleanup)
    assert response.status_code == 422
    assert any(loc.endswith(parts[-1]) for loc in nested_loc(response))


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A05")
def test_missing_father_phone_is_422(admin, academic_year_id, klass, cleanup):
    body = h.admission_payload(academic_year_id, klass)
    del body["student"]["father"]["phone"]
    response = attempt(admin, body, cleanup)
    assert response.status_code == 422
    assert "father.phone is required" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A06")
def test_blank_first_name_is_400(admin, academic_year_id, klass, cleanup):
    body = h.admission_payload(academic_year_id, klass, student={"first_name": "   "})
    response = attempt(admin, body, cleanup)
    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "Student first name is required"


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A07")
def test_blank_address_is_422(admin, academic_year_id, klass, cleanup):
    response = attempt(admin, h.admission_payload(academic_year_id, klass, address_line1=""), cleanup)
    assert response.status_code == 422


BOUNDARY_CASES = [
    ("student", "aadhar_number", 11, 422),
    ("student", "aadhar_number", 12, 201),
    ("student", "aadhar_number", 13, 422),
    ("student", "apaar_number", 11, 422),
    ("student", "apaar_number", 12, 201),
    ("student", "apaar_number", 13, 422),
    ("student", "primary_phone", 9, 422),
    ("student", "primary_phone", 10, 201),
    ("student", "primary_phone", 11, 422),
    ("father", "aadhar_number", 11, 422),
    ("father", "aadhar_number", 12, 201),
    ("father", "aadhar_number", 13, 422),
]


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A08")
@pytest.mark.parametrize("owner,field,length,status", BOUNDARY_CASES)
def test_digit_length_boundaries(admin, academic_year_id, klass, cleanup, owner, field, length, status):
    body = h.admission_payload(academic_year_id, klass)
    value = "7" * length
    if owner == "student":
        body["student"][field] = value
    else:
        body["student"]["father"][field] = value
    assert attempt(admin, body, cleanup).status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A09")
@pytest.mark.parametrize("offset,status", [(1, 400), (0, 201), (-1, 201)])
def test_admission_date_bounds(admin, academic_year_id, klass, cleanup, offset, status):
    from datetime import timedelta

    body = h.admission_payload(academic_year_id, klass, admission_date=h.iso(h.today() + timedelta(days=offset)))
    response = attempt(admin, body, cleanup)
    assert response.status_code == status, response.text
    if status == 400:
        assert response.json()["detail"]["message"] == "Admission date cannot be in the future"


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A10")
def test_same_parent_email_is_400(admin, academic_year_id, klass, cleanup):
    tag = unique("stu_same")
    body = h.admission_payload(academic_year_id, klass, tag=tag)
    body["student"]["mother"]["email"] = body["student"]["father"]["email"]
    response = attempt(admin, body, cleanup)
    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "Father and mother cannot have the same email address"


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A11")
def test_parent_email_of_staff_user_is_422(admin, academic_year_id, klass, cleanup):
    body = h.admission_payload(academic_year_id, klass)
    body["student"]["father"]["email"] = "qa_staff@example.com"
    response = attempt(admin, body, cleanup)
    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "Email qa_staff@example.com is already registered to a Staff, not a parent"


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A12")
@pytest.mark.parametrize("which,value", [("salary", "2l_4l"), ("email", "abc")])
def test_invalid_parent_salary_and_email(admin, academic_year_id, klass, cleanup, which, value):
    body = h.admission_payload(academic_year_id, klass)
    if which == "salary":
        body["student"]["father"]["salary_range"] = value
    else:
        body["student"]["father"]["email"] = value
    assert attempt(admin, body, cleanup).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A13")
def test_father_name_not_enforced_by_api(admin, academic_year_id, klass, cleanup):
    body = h.admission_payload(academic_year_id, klass)
    del body["student"]["father"]["name"]
    response = attempt(admin, body, cleanup)
    assert response.status_code == 201, response.text
    assert fetch(admin, response.json()["student"]["id"])["student"]["father"]["name"] == "Father"


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A14")
@pytest.mark.skip(reason="needs a tenant without the Student and Parent roles; every provisioned QA tenant has them")
def test_missing_default_roles_is_422():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A15")
def test_student_first_login_requires_password_change(adm, academic_year_id):
    anon = Api(tenant_header=QA_TENANT)
    response = anon.post(
        "/auth/login",
        json={"username": adm.number, "password": h.STUDENT_DEFAULT_PASSWORD, "academic_year_id": academic_year_id},
    )
    anon.close()
    assert response.status_code == 200
    assert response.json()["requires_password_change"] is True


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A16")
def test_failed_admission_leaves_nothing_behind(admin, academic_year_id, klass, cleanup):
    tag = unique("stu_atomic")
    body = h.admission_payload(academic_year_id, klass, tag=tag)
    body["admitted_class_id"] = "00000000-0000-0000-0000-000000000001"
    response = attempt(admin, body, cleanup)
    assert response.status_code >= 400
    assert admin.get("/students/admission/search", params={"query": tag}).json() == []
    anon = Api(tenant_header=QA_TENANT)
    login = anon.post(
        "/auth/login",
        json={
            "username": f"{tag}.father@example.com",
            "password": h.PARENT_DEFAULT_PASSWORD,
            "academic_year_id": academic_year_id,
        },
    )
    anon.close()
    assert login.status_code in (400, 401, 404)


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A17")
@pytest.mark.skip(reason="needs a mandatory fee class mapping, which belongs to the FEE module fixtures")
def test_mandatory_fees_applied_on_admission():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A18")
@pytest.mark.tc("TC-STU-04-A10")
@pytest.mark.parametrize(
    "role,status", [("admin", 201), ("staff", 201), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_create_permission_matrix(role_clients, academic_year_id, klass, cleanup, admin, role, status):
    body = h.admission_payload(academic_year_id, klass)
    response = h.post_admission(role_clients[role], body)
    if response.status_code == 201:
        cleanup.delete_later(admin, f"/students/admission/{response.json()['id']}")
    assert response.status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A19")
def test_create_requires_token(anon, academic_year_id, klass):
    body = h.admission_payload(academic_year_id, klass)
    payload = {k: v for k, v in body.items() if not k.startswith("_")}
    assert anon.post("/students/admission/", json=payload).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A20")
def test_created_admission_invisible_to_other_tenant(admin, tenant_b, tenant_b_name, adm, academic_year_id, klass):
    listing = tenant_b.get("/students/admission/", params={"limit": 100})
    assert listing.status_code == 200
    assert adm.admission_id not in [i["id"] for i in items_of(listing)]
    assert tenant_b.get(f"/students/admission/id/{adm.student_id}").status_code == 404
    payload = {k: v for k, v in h.admission_payload(academic_year_id, klass).items() if not k.startswith("_")}
    assert admin.post("/students/admission/", json=payload, headers={"cschema": tenant_b_name}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-03-A21")
def test_unknown_fields_are_ignored(admin, academic_year_id, klass, cleanup):
    body = h.admission_payload(academic_year_id, klass)
    body["pincode"] = "500001"
    body["student"]["student_name"] = "Ignored Name"
    response = attempt(admin, body, cleanup)
    assert response.status_code == 201, response.text
    data = fetch(admin, response.json()["student"]["id"])
    assert "pincode" not in data
    assert data["student"]["first_name"] == body["student"]["first_name"]


@pytest.mark.api
@pytest.mark.tc("TC-STU-04-A01")
def test_parent_accounts_created_and_listed(admin, make_admission, academic_year_id):
    created = make_admission()
    parents = admin.get(f"/student-parent-links/student/{created.student_id}/parents")
    assert parents.status_code == 200
    emails = sorted(p["email"] for p in parents.json())
    assert emails == sorted([created.father_email, created.mother_email])
    anon = Api(tenant_header=QA_TENANT)
    for email in (created.father_email, created.mother_email):
        response = anon.post(
            "/auth/login",
            json={"username": email, "password": h.PARENT_DEFAULT_PASSWORD, "academic_year_id": academic_year_id},
        )
        assert response.status_code == 200
        assert response.json()["requires_password_change"] is True
    anon.close()


@pytest.mark.api
@pytest.mark.tc("TC-STU-04-A02")
def test_blank_parent_emails_use_fallback_usernames(make_admission, academic_year_id):
    created = make_admission(
        student={
            "father": {"name": "NoEmail Father", "email": None, "phone": "9876500001", "relation_to_student": "Father"},
            "mother": {"name": "NoEmail Mother", "email": None, "phone": "9876500002", "relation_to_student": "Mother"},
        }
    )
    for suffix in ("father", "mother"):
        data = h.set_first_password(
            QA_TENANT, f"{created.number}.{suffix}", h.PARENT_DEFAULT_PASSWORD, year_id=academic_year_id
        )
        assert data["user"]["username"] == f"{created.number}.{suffix}"
        assert data["role"]["name"] == "Parent"


@pytest.mark.api
@pytest.mark.tc("TC-STU-04-A03")
def test_sibling_reuses_parent_and_overwrites_fields(admin, make_admission):
    first = make_admission()
    second = make_admission(
        student={
            "father": {
                "name": "Changed Father",
                "email": first.father_email,
                "phone": "9000011111",
                "relation_to_student": "Father",
            },
            "mother": {
                "name": "Other Mother",
                "email": f"{unique('stu_sib')}@example.com",
                "phone": "9000022222",
                "relation_to_student": "Mother",
            },
        }
    )
    one = fetch(admin, first.student_id)["student"]["father"]
    two = fetch(admin, second.student_id)["student"]["father"]
    assert one["id"] == two["id"]
    assert one["phone"] == "9000011111"
    assert one["name"] == "Changed Father"
    kids = admin.get(f"/student-parent-links/parent/{one['id']}/students")
    assert kids.status_code == 200
    assert sorted(k["id"] for k in kids.json()) == sorted([first.student_id, second.student_id])


@pytest.mark.api
@pytest.mark.tc("TC-STU-04-A04")
def test_guardian_with_email_is_created(admin, make_admission):
    tag = unique("stu_gd")
    created = make_admission(
        student={
            "guardian": {
                "name": f"{tag} Guardian",
                "email": f"{tag}.guardian@example.com",
                "phone": "9123456700",
                "relation_to_student": "Guardian",
            }
        }
    )
    guardian = fetch(admin, created.student_id)["student"]["guardian"]
    assert guardian["email"] == f"{tag}.guardian@example.com"
    parents = admin.get(f"/student-parent-links/student/{created.student_id}/parents").json()
    assert len(parents) == 3


@pytest.mark.api
@pytest.mark.tc("TC-STU-04-A05")
def test_guardian_without_email_is_rejected(admin, academic_year_id, klass, cleanup):
    body = h.admission_payload(academic_year_id, klass)
    body["student"]["guardian"] = {"name": "No Email Guardian", "phone": "9123456701", "relation_to_student": "Guardian"}
    response = attempt(admin, body, cleanup)
    assert response.status_code == 422
    assert "guardian.email is required" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-STU-04-A06")
def test_guardian_email_reuses_existing_parent(admin, make_admission):
    tag = unique("stu_gr")
    guardian = {
        "name": f"{tag} Guardian",
        "email": f"{tag}.guardian@example.com",
        "phone": "9123456702",
        "relation_to_student": "Guardian",
    }
    first = make_admission(student={"guardian": guardian})
    second = make_admission(student={"guardian": guardian})
    one = fetch(admin, first.student_id)["student"]["guardian"]
    two = fetch(admin, second.student_id)["student"]["guardian"]
    assert one["id"] == two["id"]
    kids = admin.get(f"/student-parent-links/parent/{one['id']}/students").json()
    assert len(kids) == 2


@pytest.mark.api
@pytest.mark.tc("TC-STU-04-A07")
def test_mother_email_of_student_user_is_422(admin, academic_year_id, klass, cleanup):
    body = h.admission_payload(academic_year_id, klass)
    body["student"]["mother"]["email"] = "qa_student@example.com"
    response = attempt(admin, body, cleanup)
    assert response.status_code == 422
    assert response.json()["detail"]["details"]["rule"] == "email_role_conflict"


@pytest.mark.api
@pytest.mark.tc("TC-STU-04-A08")
def test_parent_login_and_set_password(adm, academic_year_id):
    data = h.set_first_password(QA_TENANT, adm.father_email, h.PARENT_DEFAULT_PASSWORD, year_id=academic_year_id)
    assert data["role"]["name"] == "Parent"
    assert data["access_token"]


@pytest.mark.api
@pytest.mark.tc("TC-STU-04-A09")
def test_my_children_returns_both_siblings(make_admission, cleanup, academic_year_id):
    first = make_admission()
    second = make_admission(
        student={
            "father": {"name": "Shared Father", "email": first.father_email, "phone": "9000033333", "relation_to_student": "Father"},
            "mother": {"name": "Other Mother", "email": f"{unique('stu_om')}@example.com", "phone": "9000044444", "relation_to_student": "Mother"},
        }
    )
    parent = h.parent_client(first.father_email, cleanup, academic_year_id)
    response = parent.get("/student-parent-links/my-children")
    assert response.status_code == 200
    ids = sorted(c["id"] for c in response.json())
    assert ids == sorted([first.student_id, second.student_id])


@pytest.mark.api
@pytest.mark.tc("TC-STU-04-A11")
def test_parent_email_in_other_tenant_is_independent(admin, tenant_b, make_admission, cleanup):
    email = f"{unique('stu_iso')}.father@example.com"
    klass_b = h.make_class(tenant_b, tenant_b.academic_year_id, cleanup)
    body_b = h.admission_payload(tenant_b.academic_year_id, klass_b)
    body_b["student"]["father"]["email"] = email
    created_b = h.post_admission(tenant_b, body_b)
    assert created_b.status_code == 201, created_b.text
    cleanup.delete_later(tenant_b, f"/students/admission/{created_b.json()['id']}")
    in_a = make_admission(student={"father": {"name": "A Father", "email": email, "phone": "9000055555", "relation_to_student": "Father"}})
    parent_a = fetch(admin, in_a.student_id)["student"]["father"]
    parent_b = tenant_b.get(f"/students/admission/id/{created_b.json()['student']['id']}").json()["student"]["father"]
    assert parent_a["id"] != parent_b["id"]
    assert parent_b["phone"] == "9876543210"
