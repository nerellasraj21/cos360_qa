from datetime import timedelta

import pytest

from api_tests.students import helpers as h
from api_tests.support import QA_TENANT, Api, unique

UNKNOWN = "00000000-0000-0000-0000-000000000001"


class Edit:
    pass


@pytest.fixture(scope="module")
def ed(admin, academic_year_id, klass):
    from api_tests.support import Cleanup

    stack = Cleanup()
    fx = Edit()
    guardian = {
        "name": "Edit Guardian",
        "email": f"{unique('stu_eg')}@example.com",
        "phone": "9123400001",
        "relation_to_student": "Guardian",
    }
    fx.e1 = h.create_admission(admin, academic_year_id, klass, stack, student={"guardian": guardian})
    father = {"name": "Sibling Father", "email": fx.e1.father_email, "phone": "9000000301", "relation_to_student": "Father"}
    fx.e2 = h.create_admission(admin, academic_year_id, klass, stack, student={"father": father})
    fx.e3 = h.create_admission(admin, academic_year_id, klass, stack)
    fx.e4 = h.create_admission(admin, academic_year_id, klass, stack)
    yield fx
    stack.run()


def can_login(username, password, academic_year_id):
    anon = Api(tenant_header=QA_TENANT)
    try:
        response = anon.post(
            "/auth/login", json={"username": username, "password": password, "academic_year_id": academic_year_id}
        )
        return response.status_code == 200
    finally:
        anon.close()


def patch(admin, student_id, **body):
    return admin.patch(f"/students/admission/{student_id}", json=body)


def full(admin, student_id):
    response = admin.get(f"/students/admission/id/{student_id}")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A01")
def test_patch_first_name_only(admin, ed):
    before = full(admin, ed.e3.student_id)
    new = unique("stu_nf")
    response = patch(admin, ed.e3.student_id, first_name=new)
    assert response.status_code == 200
    assert response.json()["student"]["first_name"] == new
    after = full(admin, ed.e3.student_id)
    assert after["student"]["first_name"] == new
    assert after["student"]["last_name"] == before["student"]["last_name"]
    assert after["address_line1"] == before["address_line1"]
    assert after["admission_number"] == before["admission_number"]


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A02")
def test_patch_parent_fields(admin, ed):
    mother_email = f"{unique('stu_me')}@example.com"
    response = patch(
        admin,
        ed.e1.student_id,
        father_phone="9000000201",
        mother_email=mother_email,
        guardian_name="Renamed Guardian",
    )
    assert response.status_code == 200, response.text
    student = full(admin, ed.e1.student_id)["student"]
    assert student["father"]["phone"] == "9000000201"
    assert student["mother"]["email"] == mother_email
    assert student["guardian"]["name"] == "Renamed Guardian"


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A03")
def test_patch_admission_number(admin, ed, academic_year_id):
    taken = patch(admin, ed.e4.student_id, admission_number=ed.e3.number)
    assert taken.status_code == 422
    assert taken.json()["detail"]["message"] == f"Admission number '{ed.e3.number}' is already in use"
    original = ed.e4.number
    blank = patch(admin, ed.e4.student_id, admission_number="  ")
    assert blank.status_code == 200
    assert blank.json()["admission_number"] == original
    free = unique("stu_free")
    renamed = patch(admin, ed.e4.student_id, admission_number=free)
    assert renamed.status_code == 200
    assert renamed.json()["admission_number"] == free
    anon = Api(tenant_header=QA_TENANT)
    old_login = anon.post(
        "/auth/login",
        json={"username": original, "password": h.STUDENT_DEFAULT_PASSWORD, "academic_year_id": academic_year_id},
    )
    anon.close()
    assert old_login.status_code == 200
    patch(admin, ed.e4.student_id, admission_number=original)


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A04")
@pytest.mark.parametrize("offset,status", [(None, 400), (1, 400), (0, 200)])
def test_patch_admission_date(admin, ed, offset, status):
    value = None if offset is None else h.iso(h.today() + timedelta(days=offset))
    response = patch(admin, ed.e3.student_id, admission_date=value)
    assert response.status_code == status
    if status == 200:
        assert response.json()["admission_date"] == value


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A05")
@pytest.mark.parametrize("field", ["first_name", "father_name", "father_phone"])
def test_patch_blank_required_fields(admin, ed, field):
    response = patch(admin, ed.e3.student_id, **{field: ""})
    assert response.status_code == 400
    assert response.json()["detail"]["details"]["field"] == field


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A06")
@pytest.mark.parametrize("field", ["academic_year_id", "admitted_class_id"])
def test_patch_required_ids_cannot_be_null(admin, ed, field):
    assert patch(admin, ed.e3.student_id, **{field: None}).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A07")
def test_patch_null_date_of_birth_becomes_placeholder(admin, ed):
    response = patch(admin, ed.e3.student_id, date_of_birth=None)
    assert response.status_code == 200
    assert full(admin, ed.e3.student_id)["student"]["date_of_birth"] == "1900-01-01"


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A08")
def test_patch_father_email_equal_to_mother(admin, ed):
    response = patch(admin, ed.e3.student_id, father_email=ed.e3.mother_email)
    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "Father and mother cannot have the same email address"


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A09")
@pytest.mark.parametrize("body", [{"aadhar_number": "abc"}, {"primary_phone": "1"}])
def test_patch_validates_formats(admin, ed, body):
    assert patch(admin, ed.e3.student_id, **body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A10")
def test_patch_guardian_without_link_creates_nothing(admin, ed):
    response = patch(admin, ed.e3.student_id, guardian_name="Ghost Guardian")
    assert response.status_code == 200
    assert full(admin, ed.e3.student_id)["student"]["guardian"] is None
    assert len(admin.get(f"/student-parent-links/student/{ed.e3.student_id}/parents").json()) == 2


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A11")
def test_shared_parent_edit_is_visible_to_sibling(admin, ed):
    phone = "9000000202"
    assert patch(admin, ed.e2.student_id, father_phone=phone).status_code == 200
    assert full(admin, ed.e1.student_id)["student"]["father"]["phone"] == phone
    assert full(admin, ed.e2.student_id)["student"]["father"]["phone"] == phone


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A12")
@pytest.mark.parametrize("which", ["admission_id", "random"])
def test_patch_with_wrong_id(admin, ed, which):
    target = ed.e3.admission_id if which == "admission_id" else UNKNOWN
    response = patch(admin, target, first_name="x")
    assert response.status_code == 404
    assert response.json()["detail"]["message"] == "Admission not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A13")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_patch_permission_matrix(role_clients, ed, role, status):
    response = role_clients[role].patch(f"/students/admission/{ed.e3.student_id}", json={"nationality": "Indian"})
    assert response.status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A14")
def test_patch_requires_token(anon, ed):
    assert anon.patch(f"/students/admission/{ed.e3.student_id}", json={"nationality": "Indian"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A15")
def test_patch_tenant_isolation(admin, tenant_b, tenant_b_name, ed):
    assert patch(tenant_b, ed.e3.student_id, first_name="hacked").status_code == 404
    mismatch = admin.patch(
        f"/students/admission/{ed.e3.student_id}", json={"first_name": "x"}, headers={"cschema": tenant_b_name}
    )
    assert mismatch.status_code == 403
    assert full(admin, ed.e3.student_id)["student"]["first_name"] != "hacked"


@pytest.mark.api
@pytest.mark.tc("TC-STU-08-A16")
def test_patch_admission_type_keeps_number(admin, ed):
    before = full(admin, ed.e4.student_id)
    response = patch(admin, ed.e4.student_id, admission_type="pre_primary")
    assert response.status_code == 200
    assert response.json()["admission_type"] == "pre_primary"
    assert response.json()["admission_number"] == before["admission_number"]


@pytest.mark.api
@pytest.mark.tc("TC-STU-09-A01")
def test_toggle_flips_active_flag(admin, ed):
    first = admin.patch(f"/students/admission/{ed.e4.student_id}/toggle-active")
    assert first.status_code == 200
    state = first.json()["student"]["is_active"]
    second = admin.patch(f"/students/admission/{ed.e4.student_id}/toggle-active")
    assert second.json()["student"]["is_active"] is (not state)
    assert state is False


@pytest.mark.api
@pytest.mark.tc("TC-STU-09-A02")
@pytest.mark.tc("TC-STU-09-A03")
def test_deactivated_student_cannot_login_and_leaves_dropdowns(admin, ed, klass, academic_year_id):
    assert admin.patch(f"/students/admission/{ed.e4.student_id}/toggle-active").status_code == 200
    try:
        anon = Api(tenant_header=QA_TENANT)
        login = anon.post(
            "/auth/login",
            json={"username": ed.e4.number, "password": h.STUDENT_DEFAULT_PASSWORD, "academic_year_id": academic_year_id},
        )
        anon.close()
        assert login.status_code in (400, 401, 403)
        params = {"class_id": klass["id"], "limit": 100}
        simple = "/students/admission/students/dropdown/simple"
        assert ed.e4.student_id not in [r["id"] for r in admin.get(simple, params={"class_id": klass["id"]}).json()]
        assert ed.e4.student_id in [
            r["id"] for r in admin.get(simple, params={"class_id": klass["id"], "active_only": "false"}).json()
        ]
        listed = admin.get("/students/admission/", params=params).json()["items"]
        row = next(i for i in listed if i["student"]["id"] == ed.e4.student_id)
        assert row["student"]["is_active"] is False
    finally:
        admin.patch(f"/students/admission/{ed.e4.student_id}/toggle-active")


@pytest.mark.api
@pytest.mark.tc("TC-STU-09-A04")
@pytest.mark.parametrize("which", ["admission_id", "random"])
def test_toggle_unknown_ids(admin, ed, which):
    target = ed.e3.admission_id if which == "admission_id" else UNKNOWN
    response = admin.patch(f"/students/admission/{target}/toggle-active")
    assert response.status_code == 404
    assert "Student not found" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-STU-09-A05")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_toggle_permission_matrix(admin, role_clients, ed, role, status):
    response = role_clients[role].patch(f"/students/admission/{ed.e3.student_id}/toggle-active")
    assert response.status_code == status
    if status == 200:
        admin.patch(f"/students/admission/{ed.e3.student_id}/toggle-active")


@pytest.mark.api
@pytest.mark.tc("TC-STU-09-A06")
def test_delete_permission_matrix(admin, role_clients, make_admission, academic_year_id):
    throwaway = make_admission(admission_number=unique("stu_d"))
    for role in ("staff", "teacher", "student", "parent"):
        denied = role_clients[role].delete(f"/students/admission/{throwaway.admission_id}")
        assert denied.status_code == 403
    assert admin.get(f"/students/admission/id/{throwaway.student_id}").status_code == 200
    deleted = admin.delete(f"/students/admission/{throwaway.admission_id}")
    assert deleted.status_code == 200
    assert "message" in deleted.json()
    assert admin.get(f"/students/admission/id/{throwaway.student_id}").status_code == 404
    leftover = admin.get(f"/student-parent-links/student/{throwaway.student_id}/parents")
    assert leftover.status_code == 404 or leftover.json() == []
    assert not can_login(throwaway.father_email, h.PARENT_DEFAULT_PASSWORD, academic_year_id)
    assert not can_login(throwaway.number, h.STUDENT_DEFAULT_PASSWORD, academic_year_id)


@pytest.mark.api
@pytest.mark.tc("TC-STU-09-A07")
def test_delete_keeps_shared_parent_and_removes_unshared(admin, make_admission, academic_year_id):
    first = make_admission()
    father = {"name": "Shared F", "email": first.father_email, "phone": "9000000401", "relation_to_student": "Father"}
    second = make_admission(student={"father": father})
    father_id = full(admin, first.student_id)["student"]["father"]["id"]
    mother_id = full(admin, first.student_id)["student"]["mother"]["id"]
    assert admin.delete(f"/students/admission/{first.admission_id}").status_code == 200
    survivors = admin.get(f"/student-parent-links/parent/{father_id}/students")
    assert survivors.status_code == 200
    assert [s["id"] for s in survivors.json()] == [second.student_id]
    assert can_login(first.father_email, h.PARENT_DEFAULT_PASSWORD, academic_year_id)
    assert not can_login(first.mother_email, h.PARENT_DEFAULT_PASSWORD, academic_year_id)
    gone = admin.get(f"/student-parent-links/parent/{mother_id}/students")
    assert gone.status_code == 404 or gone.json() == []
    assert full(admin, second.student_id)["student"]["father"]["id"] == father_id


@pytest.mark.api
@pytest.mark.tc("TC-STU-09-A08")
@pytest.mark.skip(reason="blocked: needs a fee payment or exam marks for the student, which belong to FEE and EXM fixtures")
def test_delete_with_fee_or_exam_history_is_409():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-STU-09-A08")
def test_delete_unknown_admission(admin):
    response = admin.delete(f"/students/admission/{UNKNOWN}")
    assert response.status_code == 404
    assert "Admission not found" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-STU-09-A09")
def test_toggle_and_delete_require_token(anon, ed):
    assert anon.patch(f"/students/admission/{ed.e3.student_id}/toggle-active").status_code == 401
    assert anon.delete(f"/students/admission/{ed.e3.admission_id}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-09-A10")
def test_toggle_tenant_isolation(admin, tenant_b, tenant_b_name, ed):
    assert tenant_b.patch(f"/students/admission/{ed.e3.student_id}/toggle-active").status_code == 404
    mismatch = admin.patch(f"/students/admission/{ed.e3.student_id}/toggle-active", headers={"cschema": tenant_b_name})
    assert mismatch.status_code == 403
    assert tenant_b.delete(f"/students/admission/{ed.e3.admission_id}").status_code == 404
    assert admin.delete(f"/students/admission/{ed.e3.admission_id}", headers={"cschema": tenant_b_name}).status_code == 403
    assert full(admin, ed.e3.student_id)["student"]["is_active"] is None
