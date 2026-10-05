import pytest

from api_tests.students import helpers as h
from api_tests.support import QA_TENANT, Api, unique

UNKNOWN = "00000000-0000-0000-0000-000000000001"
LINKS = "/student-parent-links"
PROFILE = "/profile/student/me"
PROFILE_KEYS = {
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
ALL_STUDENT_CHILDREN = [
    "/students/admission",
    "/students/attendance",
    "/students/studentdocuments",
    "/students/studentcertificates",
    "/students/certificatetypes",
    "/students/certificatetemplates",
    "/students/studenttransport",
]
SELF_SERVICE_CHILDREN = [
    "/students/admission",
    "/students/attendance",
    "/students/studentdocuments",
    "/students/studentcertificates",
    "/students/studenttransport",
]


def parent_ids(admin, student_id):
    student = admin.get(f"/students/admission/id/{student_id}").json()["student"]
    return {"father": student["father"]["id"], "mother": student["mother"]["id"]}


def students_menu_paths(login_payload):
    for item in login_payload["menu"]:
        if item["name"] == "Students":
            return sorted(child["path"] for child in item["children"])
    return []


@pytest.mark.api
@pytest.mark.tc("TC-STU-01-A01")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher", "student", "parent"])
def test_login_menu_students_children(logins, role):
    expected = ALL_STUDENT_CHILDREN if role in ("admin", "staff", "teacher") else SELF_SERVICE_CHILDREN
    assert students_menu_paths(logins[role]) == sorted(expected)


@pytest.mark.api
@pytest.mark.tc("TC-STU-18-A01")
def test_student_profile_shape(family, klass):
    response = family.c1_student.get(PROFILE)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == PROFILE_KEYS
    assert body["student_id"] == family.c1.student_id
    assert body["admission_number"] == family.c1.number
    assert body["class_name"] == klass["name"]
    assert body["section_name"] == "A"
    assert body["first_name"] == family.c1.first_name
    assert body["profile_photo_url"] is None
    assert isinstance(body["total_certificates"], int) and isinstance(body["total_documents"], int)


@pytest.mark.api
@pytest.mark.tc("TC-STU-18-A02")
def test_profile_attendance_percentage(admin, family):
    for offset, status in ((25, "present"), (24, "present"), (23, "present"), (22, "absent")):
        marked = admin.post(
            "/student/attendance/",
            json={"student_id": family.c1.student_id, "date": h.past_date(offset), "status": status},
        )
        assert marked.status_code == 201, marked.text
    assert family.c1_student.get(PROFILE).json()["attendance_percentage"] == 75.0


@pytest.mark.api
@pytest.mark.tc("TC-STU-18-A03")
def test_profile_email_update(family):
    email = f"{unique('stu_pe')}@example.com"
    response = family.c1_student.put(PROFILE, json={"email": email})
    assert response.status_code == 200
    assert family.c1_student.get(PROFILE).json()["email"] == email


@pytest.mark.api
@pytest.mark.tc("TC-STU-18-A04")
def test_profile_update_without_validation(family):
    email = f"{unique('stu_pk')}@example.com"
    family.c1_student.put(PROFILE, json={"email": email})
    empty = family.c1_student.put(PROFILE, json={})
    assert empty.status_code == 200
    assert family.c1_student.get(PROFILE).json()["email"] == email
    odd = family.c1_student.put(PROFILE, json={"email": "abc"})
    assert odd.status_code == 200
    assert family.c1_student.get(PROFILE).json()["email"] == "abc"


@pytest.mark.api
@pytest.mark.tc("TC-STU-18-A05")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher", "parent"])
def test_profile_without_student_record_is_not_found_for_other_roles(role_clients, role):
    assert role_clients[role].get(PROFILE).status_code == 404
    assert role_clients[role].put(PROFILE, json={"email": "x@example.com"}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-18-A05")
def test_shared_qa_student_without_record(student):
    assert student.get(PROFILE).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-18-A06")
def test_profile_requires_token(anon):
    assert anon.get(PROFILE).status_code == 401
    assert anon.put(PROFILE, json={"email": "x@example.com"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-18-A07")
def test_profile_tenant_mismatch(family, tenant_b_name):
    header = {"cschema": tenant_b_name}
    assert family.c1_student.get(PROFILE, headers=header).status_code == 403
    assert family.c1_student.put(PROFILE, json={"email": "x@example.com"}, headers=header).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-19-A01")
def test_parent_my_children(family, klass):
    response = family.parent.get(f"{LINKS}/my-children")
    assert response.status_code == 200
    rows = response.json()
    assert sorted(r["id"] for r in rows) == sorted([family.c1.student_id, family.c2.student_id])
    names = [(r["first_name"], r["last_name"]) for r in rows]
    assert names == sorted(names)
    for r in rows:
        assert r["class_id"] == klass["id"] and r["class_name"] == klass["name"]
        assert {"is_active", "date_of_birth", "gender", "admission_number", "academic_year_id", "section_id", "section_name"} <= set(r)
    sections = {r["id"]: r["section_name"] for r in rows}
    assert sections[family.c1.student_id] == "A" and sections[family.c2.student_id] == "B"


@pytest.mark.api
@pytest.mark.tc("TC-STU-19-A02")
@pytest.mark.skip(reason="blocked: the API cannot create a second admission for an existing student")
def test_child_with_two_admissions():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-STU-19-A03")
def test_deactivated_child_is_listed_inactive(admin, family):
    assert admin.patch(f"/students/admission/{family.c2.student_id}/toggle-active").status_code == 200
    try:
        rows = {r["id"]: r for r in family.parent.get(f"{LINKS}/my-children").json()}
        assert rows[family.c2.student_id]["is_active"] is False
        assert rows[family.c1.student_id]["is_active"] is True
    finally:
        admin.patch(f"/students/admission/{family.c2.student_id}/toggle-active")


@pytest.mark.api
@pytest.mark.tc("TC-STU-19-A04")
def test_parent_without_children_gets_empty_list(admin, make_admission, academic_year_id, cleanup):
    created = make_admission()
    father = parent_ids(admin, created.student_id)["father"]
    client = h.parent_client(created.father_email, cleanup, academic_year_id)
    assert client.get(f"{LINKS}/my-children").json() != []
    assert admin.delete(f"{LINKS}/student/{created.student_id}/parent/{father}").status_code == 204
    empty = client.get(f"{LINKS}/my-children")
    assert empty.status_code == 200
    assert empty.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-STU-19-A05")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher", "student"])
def test_my_children_is_parent_only(role_clients, role):
    response = role_clients[role].get(f"{LINKS}/my-children")
    assert response.status_code == 403
    assert response.json()["detail"] == "Only parents can access this endpoint"


@pytest.mark.api
@pytest.mark.tc("TC-STU-19-A06")
def test_parent_without_parent_row(parent):
    response = parent.get(f"{LINKS}/my-children")
    assert response.status_code == 404
    assert response.json()["detail"] == "Parent profile not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-19-A07")
def test_my_children_requires_token(anon):
    assert anon.get(f"{LINKS}/my-children").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-19-A08")
def test_parents_only_see_their_own_children(family, tenant_b_name):
    mine = [r["id"] for r in family.other_parent.get(f"{LINKS}/my-children").json()]
    assert mine == [family.other.student_id]
    assert family.parent.get(f"{LINKS}/my-children", headers={"cschema": tenant_b_name}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-19-A09")
def test_child_scope_follows_links(family):
    assert family.parent.get(f"/students/admission/id/{family.c1.student_id}").status_code == 200
    assert family.parent.get(f"/students/admission/id/{family.c2.student_id}").status_code == 200
    assert family.parent.get(f"/students/admission/id/{family.other.student_id}").status_code == 404


@pytest.fixture
def pair(admin, make_admission):
    first = make_admission()
    second = make_admission()
    return first, second


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A01")
def test_link_existing_parent(admin, pair, cleanup):
    first, second = pair
    parent_id = parent_ids(admin, second.student_id)["father"]
    response = admin.post(f"{LINKS}/", json={"student_id": first.student_id, "parent_id": parent_id})
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"id", "student_id", "parent_id"}
    assert body["student_id"] == first.student_id and body["parent_id"] == parent_id
    kids = admin.get(f"{LINKS}/parent/{parent_id}/students").json()
    assert sorted(k["id"] for k in kids) == sorted([first.student_id, second.student_id])


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A02")
def test_duplicate_link_is_400(admin, pair):
    first, _ = pair
    parent_id = parent_ids(admin, first.student_id)["father"]
    response = admin.post(f"{LINKS}/", json={"student_id": first.student_id, "parent_id": parent_id})
    assert response.status_code == 400
    assert response.json()["detail"] == "Student-parent link already exists"


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A03")
def test_link_with_unknown_ids(admin, pair):
    first, _ = pair
    parent_id = parent_ids(admin, first.student_id)["father"]
    unknown_student = admin.post(f"{LINKS}/", json={"student_id": UNKNOWN, "parent_id": parent_id})
    assert unknown_student.status_code == 404 and unknown_student.json()["detail"] == "Student not found"
    unknown_parent = admin.post(f"{LINKS}/", json={"student_id": first.student_id, "parent_id": UNKNOWN})
    assert unknown_parent.status_code == 404 and unknown_parent.json()["detail"] == "Parent not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A04")
def test_unlink_then_unlink_again(admin, pair):
    first, second = pair
    parent_id = parent_ids(admin, second.student_id)["father"]
    admin.post(f"{LINKS}/", json={"student_id": first.student_id, "parent_id": parent_id})
    done = admin.delete(f"{LINKS}/student/{first.student_id}/parent/{parent_id}")
    assert done.status_code == 204
    again = admin.delete(f"{LINKS}/student/{first.student_id}/parent/{parent_id}")
    assert again.status_code == 404
    assert again.json()["detail"] == "Student-parent link not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A05")
def test_parents_of_student(admin, family):
    response = admin.get(f"{LINKS}/student/{family.other.student_id}/parents")
    assert response.status_code == 200
    rows = response.json()
    assert sorted(r["email"] for r in rows) == sorted([family.other.father_email, family.other.mother_email])
    assert all({"id", "name", "email", "phone", "relation_to_student", "students"} <= set(r) for r in rows)
    assert {r["relation_to_student"] for r in rows} == {"Father", "Mother"}


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A06")
def test_parent_reads_only_own_children(admin, family):
    ids = parent_ids(admin, family.other.student_id)
    own = family.other_parent.get(f"{LINKS}/parent/{ids['father']}/students")
    assert own.status_code == 200
    assert [s["id"] for s in own.json()] == [family.other.student_id]
    foreign = family.parent.get(f"{LINKS}/parent/{ids['father']}/students")
    assert foreign.status_code == 403
    assert foreign.json()["detail"] == "You can only view your own children"


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A07")
def test_admin_reads_students_of_parent(admin, family):
    ids = parent_ids(admin, family.c1.student_id)
    response = admin.get(f"{LINKS}/parent/{ids['father']}/students")
    assert response.status_code == 200
    rows = response.json()
    assert sorted(r["id"] for r in rows) == sorted([family.c1.student_id, family.c2.student_id])
    assert all({"first_name", "last_name", "father", "mother"} <= set(r) for r in rows)


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A08")
@pytest.mark.parametrize("role", ["admin", "staff"])
def test_list_all_links(role_clients, family, role):
    response = role_clients[role].get(f"{LINKS}/")
    assert response.status_code == 200
    assert family.c1.student_id in [link["student_id"] for link in response.json()]


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A09")
@pytest.mark.parametrize(
    "role,status", [("admin", 201), ("staff", 201), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_link_create_matrix(role_clients, admin, pair, role, status):
    first, second = pair
    parent_id = parent_ids(admin, second.student_id)["mother"]
    response = role_clients[role].post(f"{LINKS}/", json={"student_id": first.student_id, "parent_id": parent_id})
    assert response.status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A09")
def test_link_delete_matrix(role_clients, admin, pair):
    first, second = pair
    parent_id = parent_ids(admin, second.student_id)["father"]
    admin.post(f"{LINKS}/", json={"student_id": first.student_id, "parent_id": parent_id})
    path = f"{LINKS}/student/{first.student_id}/parent/{parent_id}"
    for role in ("staff", "teacher", "student", "parent"):
        assert role_clients[role].delete(path).status_code == 403
    assert role_clients["admin"].delete(path).status_code == 204


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A09")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_link_read_matrix(role_clients, family, role, status):
    assert role_clients[role].get(f"{LINKS}/student/{family.c1.student_id}/parents").status_code == status
    assert role_clients[role].get(f"{LINKS}/").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A10")
def test_links_require_token(anon, family):
    ids = (family.c1.student_id, UNKNOWN)
    assert anon.post(f"{LINKS}/", json={"student_id": ids[0], "parent_id": ids[1]}).status_code == 401
    assert anon.delete(f"{LINKS}/student/{ids[0]}/parent/{ids[1]}").status_code == 401
    assert anon.get(f"{LINKS}/student/{ids[0]}/parents").status_code == 401
    assert anon.get(f"{LINKS}/parent/{ids[1]}/students").status_code == 401
    assert anon.get(f"{LINKS}/").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-20-A11")
def test_links_tenant_isolation(admin, tenant_b, tenant_b_name, family):
    ids = parent_ids(admin, family.c1.student_id)
    body = {"student_id": family.c1.student_id, "parent_id": ids["father"]}
    assert tenant_b.post(f"{LINKS}/", json=body).status_code == 404
    header = {"cschema": tenant_b_name}
    assert admin.post(f"{LINKS}/", json=body, headers=header).status_code == 403
    assert admin.get(f"{LINKS}/", headers=header).status_code == 403
    leaked = tenant_b.get(f"{LINKS}/student/{family.c1.student_id}/parents")
    assert leaked.status_code == 200
    assert leaked.json() == []
    assert tenant_b.get(f"{LINKS}/parent/{ids['father']}/students").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-STU-22-A01")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher", "student", "parent"])
def test_sms_triggers_forbidden_for_every_role(role_clients, role):
    client = role_clients[role]
    confirmation = client.post("/students/admission/send-confirmation", json=[UNKNOWN])
    alerts = client.post("/student/attendance/send-absence-alerts", params={"attendance_date": h.iso(h.today())}, json=[UNKNOWN])
    reminders = client.post("/students/homework/send-reminders", json=[UNKNOWN])
    assert confirmation.status_code == 403
    assert alerts.status_code == 403
    assert reminders.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-22-A02")
@pytest.mark.skip(reason="skipped: after a send_sms grant this endpoint would reach the SMS path, and the suite never sends messages")
def test_confirmation_with_grant():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-STU-22-A03")
@pytest.mark.skip(reason="skipped: after a send_sms grant this endpoint would reach the SMS path, and the suite never sends messages")
def test_absence_alerts_with_grant():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-STU-22-A04")
def test_absence_alerts_need_attendance_date(admin):
    assert admin.post("/student/attendance/send-absence-alerts", json=[UNKNOWN]).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-22-A05")
@pytest.mark.skip(reason="skipped: needs a send_sms grant on the shared Admin role and would reach the Celery queue")
def test_homework_reminders_unknown_id():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-STU-22-A06")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_sms_triggers_report_permission_error(role_clients, role):
    response = role_clients[role].post("/students/admission/send-confirmation", json=[UNKNOWN])
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-22-A07")
def test_sms_triggers_require_token(anon):
    assert anon.post("/students/admission/send-confirmation", json=[UNKNOWN]).status_code == 401
    assert anon.post("/student/attendance/send-absence-alerts", params={"attendance_date": h.iso(h.today())}, json=[UNKNOWN]).status_code == 401
    assert anon.post("/students/homework/send-reminders", json=[UNKNOWN]).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-22-A08")
def test_sms_triggers_tenant_mismatch(admin, tenant_b_name):
    header = {"cschema": tenant_b_name}
    assert admin.post("/students/admission/send-confirmation", json=[UNKNOWN], headers=header).status_code == 403
    assert admin.post("/students/homework/send-reminders", json=[UNKNOWN], headers=header).status_code == 404
