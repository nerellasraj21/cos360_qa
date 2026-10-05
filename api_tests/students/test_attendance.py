import pytest

from api_tests.students import helpers as h
from api_tests.support import Cleanup, unique

UNKNOWN = "00000000-0000-0000-0000-000000000001"
BASE = "/student/attendance"
ROW_KEYS = {"id", "student_id", "date", "status", "remarks"}


class Att:
    pass


def day(offset):
    return h.past_date(offset)


@pytest.fixture(scope="module")
def att(admin, academic_year_id, klass):
    stack = Cleanup()
    fx = Att()
    fx.s1 = h.create_admission(admin, academic_year_id, klass, stack, admission_date=day(30))
    fx.s2 = h.create_admission(admin, academic_year_id, klass, stack, admission_date=day(30))
    fx.s3 = h.create_admission(admin, academic_year_id, klass, stack, admission_date=day(10))
    fx.s4 = h.create_admission(admin, academic_year_id, klass, stack, admission_date=day(30))
    fx.s1_student = h.student_client(fx.s1, stack, academic_year_id)
    fx.s1_parent = h.parent_client(fx.s1.father_email, stack, academic_year_id)
    for offset, status in ((29, "present"), (28, "absent"), (27, "half_day")):
        seeded = admin.post(
            f"{BASE}/", json={"student_id": fx.s1.student_id, "date": day(offset), "status": status}
        )
        assert seeded.status_code == 201, seeded.text
    yield fx
    stack.run()


def mark(client, student_id, offset, status="present", **extra):
    return client.post(f"{BASE}/", json={"student_id": student_id, "date": day(offset), "status": status, **extra})


def row(admin, student_id, offset, status="present"):
    response = mark(admin, student_id, offset, status)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A01")
def test_create_present_shape(admin, att):
    response = mark(admin, att.s1.student_id, 1)
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == ROW_KEYS
    assert body["student_id"] == att.s1.student_id
    assert body["date"] == day(1)
    assert body["status"] == "present"
    assert body["remarks"] is None


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A02")
def test_create_status_is_case_insensitive(admin, att):
    response = mark(admin, att.s1.student_id, 2, "Late", remarks="bus")
    assert response.status_code == 201
    assert response.json()["status"] == "late"
    assert response.json()["remarks"] == "bus"


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A03")
@pytest.mark.parametrize("offset,status", [(3, "absent"), (4, "late"), (5, "half_day"), (6, "leave"), (7, "present")])
def test_every_status_is_accepted(admin, att, offset, status):
    response = mark(admin, att.s1.student_id, offset, status)
    assert response.status_code == 201
    assert response.json()["status"] == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A03")
def test_unknown_status_is_422(admin, att):
    assert mark(admin, att.s1.student_id, 8, "holiday").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A04")
def test_duplicate_mark_is_422(admin, att):
    row(admin, att.s2.student_id, 1)
    response = mark(admin, att.s2.student_id, 1, "absent")
    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "Attendance already marked for this student on this date"


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A05")
def test_date_guards(admin, att):
    future = admin.post(f"{BASE}/", json={"student_id": att.s1.student_id, "date": h.future_date(), "status": "present"})
    assert future.status_code == 400
    assert future.json()["detail"]["message"] == "Attendance date cannot be in the future"
    early = mark(admin, att.s3.student_id, 11)
    assert early.status_code == 400
    assert "before the student's admission date" in early.json()["detail"]["message"]
    assert mark(admin, att.s3.student_id, 10).status_code == 201


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A06")
def test_unknown_student_is_404(admin):
    response = mark(admin, UNKNOWN, 1)
    assert response.status_code == 404
    assert response.json()["detail"]["message"] == "Student not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A07")
def test_by_date_upsert_skips_pre_admission_students(admin, att):
    existing = row(admin, att.s1.student_id, 15)
    payload = [
        {"student_id": att.s1.student_id, "status": "late", "remarks": "note"},
        {"student_id": att.s2.student_id, "status": "absent", "remarks": ""},
        {"student_id": att.s3.student_id, "status": "absent"},
    ]
    response = admin.patch(f"{BASE}/by-date/{day(15)}", json=payload)
    assert response.status_code == 200, response.text
    rows = {r["student_id"]: r for r in response.json()}
    assert set(rows) == {att.s1.student_id, att.s2.student_id}
    assert rows[att.s1.student_id]["id"] == existing["id"]
    assert rows[att.s1.student_id]["status"] == "late"
    assert rows[att.s1.student_id]["remarks"] == "note"
    assert rows[att.s2.student_id]["status"] == "absent"
    assert rows[att.s2.student_id]["remarks"] in (None, "")


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A07")
def test_by_date_updates_existing_and_skips_pre_admission(admin, att):
    existing = row(admin, att.s1.student_id, 19)
    payload = [
        {"student_id": att.s1.student_id, "status": "late", "remarks": "note"},
        {"student_id": att.s3.student_id, "status": "absent"},
    ]
    response = admin.patch(f"{BASE}/by-date/{day(19)}", json=payload)
    assert response.status_code == 200, response.text
    rows = {r["student_id"]: r for r in response.json()}
    assert set(rows) == {att.s1.student_id}
    assert rows[att.s1.student_id]["id"] == existing["id"]
    assert rows[att.s1.student_id]["status"] == "late"
    assert rows[att.s1.student_id]["remarks"] == "note"


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A07")
def test_by_date_creates_new_rows_and_skips_pre_admission(admin, att):
    payload = [
        {"student_id": att.s2.student_id, "status": "absent", "remarks": ""},
        {"student_id": att.s4.student_id, "status": "late"},
        {"student_id": att.s3.student_id, "status": "absent"},
    ]
    response = admin.patch(f"{BASE}/by-date/{day(30)}", json=payload)
    assert response.status_code == 200, response.text
    rows = {r["student_id"]: r for r in response.json()}
    assert set(rows) == {att.s2.student_id, att.s4.student_id}
    assert rows[att.s2.student_id]["status"] == "absent"
    assert rows[att.s4.student_id]["status"] == "late"


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A08")
@pytest.mark.parametrize(
    "date_value,payload,message",
    [
        (day(16), [{"student_id": "s1", "status": "Absent"}], "Invalid attendance status"),
        (day(16), [], "No attendance updates provided"),
        (h.future_date(), [{"student_id": "s1", "status": "absent"}], "Cannot update attendance for future dates"),
    ],
)
def test_by_date_rejections(admin, att, date_value, payload, message):
    payload = [{**item, "student_id": att.s1.student_id} for item in payload]
    response = admin.patch(f"{BASE}/by-date/{date_value}", json=payload)
    assert response.status_code == 400
    assert message in response.json()["detail"]["message"]


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A09")
def test_by_date_skips_incomplete_items(admin, att):
    payload = [{"status": "absent"}, {"student_id": att.s1.student_id}]
    response = admin.patch(f"{BASE}/by-date/{day(17)}", json=payload)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A10")
def test_by_date_unknown_student_is_database_error(admin):
    response = admin.patch(f"{BASE}/by-date/{day(18)}", json=[{"student_id": UNKNOWN, "status": "absent"}])
    assert response.status_code == 500
    assert response.json()["detail"]["error_code"] == "DATABASE_ERROR"


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A11")
@pytest.mark.parametrize(
    "role,status,offset", [("admin", 201, 20), ("staff", 201, 21), ("teacher", 201, 22), ("student", 403, 23), ("parent", 403, 24)]
)
def test_create_permission_matrix(role_clients, att, role, status, offset):
    assert mark(role_clients[role], att.s2.student_id, offset).status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A12")
@pytest.mark.parametrize(
    "role,status,offset", [("admin", 200, 25), ("staff", 200, 26), ("teacher", 200, 27), ("student", 403, 28), ("parent", 403, 29)]
)
def test_by_date_permission_matrix(role_clients, att, role, status, offset):
    response = role_clients[role].patch(
        f"{BASE}/by-date/{day(offset)}", json=[{"student_id": att.s4.student_id, "status": "present"}]
    )
    assert response.status_code == status
    if status == 200:
        assert len(response.json()) == 1


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A13")
def test_marking_requires_token(anon, att):
    assert anon.post(f"{BASE}/", json={"student_id": att.s1.student_id, "date": day(1), "status": "present"}).status_code == 401
    assert anon.patch(f"{BASE}/by-date/{day(1)}", json=[]).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A14")
def test_marking_tenant_isolation(admin, tenant_b, tenant_b_name, att):
    other = mark(tenant_b, att.s1.student_id, 9)
    assert other.status_code == 404
    assert other.json()["detail"]["message"] == "Student not found"
    body = {"student_id": att.s1.student_id, "date": day(9), "status": "present"}
    assert admin.post(f"{BASE}/", json=body, headers={"cschema": tenant_b_name}).status_code == 403
    assert admin.patch(f"{BASE}/by-date/{day(9)}", json=[], headers={"cschema": tenant_b_name}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-11-A15")
def test_teacher_marks_any_student(teacher, att):
    assert mark(teacher, att.s4.student_id, 14).status_code == 201


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A01")
def test_patch_status_keeps_id(admin, att):
    created = row(admin, att.s4.student_id, 3, "absent")
    response = admin.patch(f"{BASE}/{created['id']}", json={"status": "present"})
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["status"] == "present"


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A02")
def test_patch_remarks_only(admin, att):
    created = row(admin, att.s4.student_id, 4, "late")
    response = admin.patch(f"{BASE}/{created['id']}", json={"remarks": "traffic"})
    assert response.status_code == 200
    assert response.json()["status"] == "late"
    assert response.json()["remarks"] == "traffic"


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A03")
def test_patch_invalid_status(admin, att):
    created = row(admin, att.s4.student_id, 5)
    assert admin.patch(f"{BASE}/{created['id']}", json={"status": "holiday"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A04")
def test_patch_unknown_and_malformed(admin):
    missing = admin.patch(f"{BASE}/{UNKNOWN}", json={"status": "absent"})
    assert missing.status_code == 404
    assert missing.json()["detail"]["message"] == "Attendance record not found"
    assert admin.patch(f"{BASE}/abc", json={"status": "absent"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A05")
def test_delete_removes_row(admin, att):
    created = row(admin, att.s4.student_id, 6)
    response = admin.delete(f"{BASE}/{created['id']}")
    assert response.status_code == 200
    assert response.json() == {"detail": "Attendance record deleted successfully"}
    assert admin.get(f"{BASE}/{created['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A06")
def test_delete_unknown(admin):
    assert admin.delete(f"{BASE}/{UNKNOWN}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A07")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 403), ("parent", 403)]
)
def test_patch_permission_matrix(role_clients, admin, att, role, status):
    created = row(admin, att.s4.student_id, 7 + ["admin", "staff", "teacher", "student", "parent"].index(role))
    response = role_clients[role].patch(f"{BASE}/{created['id']}", json={"remarks": "x"})
    assert response.status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A08")
def test_delete_permission_matrix(role_clients, admin, att):
    created = row(admin, att.s4.student_id, 12)
    for role in ("staff", "teacher", "student", "parent"):
        assert role_clients[role].delete(f"{BASE}/{created['id']}").status_code == 403
    assert admin.get(f"{BASE}/{created['id']}").status_code == 200
    assert admin.delete(f"{BASE}/{created['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A09")
def test_patch_and_delete_require_token(anon):
    assert anon.patch(f"{BASE}/{UNKNOWN}", json={"status": "absent"}).status_code == 401
    assert anon.delete(f"{BASE}/{UNKNOWN}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A10")
def test_patch_and_delete_tenant_isolation(admin, tenant_b, tenant_b_name, att):
    created = row(admin, att.s4.student_id, 13)
    assert tenant_b.patch(f"{BASE}/{created['id']}", json={"remarks": "x"}).status_code == 404
    assert tenant_b.delete(f"{BASE}/{created['id']}").status_code == 404
    header = {"cschema": tenant_b_name}
    assert admin.patch(f"{BASE}/{created['id']}", json={"remarks": "x"}, headers=header).status_code == 403
    assert admin.delete(f"{BASE}/{created['id']}", headers=header).status_code == 403
    assert admin.get(f"{BASE}/{created['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STU-12-A11")
def test_static_routes_are_not_parsed_as_ids(admin, att):
    mine = att.s1_student.get(f"{BASE}/my-attendance")
    assert mine.status_code == 422
    assert all(err["loc"][-1] != "attendance_id" for err in mine.json()["detail"])
    search = admin.get(f"{BASE}/search")
    assert search.status_code == 200
    assert isinstance(search.json(), list)


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A01")
def test_student_my_attendance_range(att):
    response = att.s1_student.get(f"{BASE}/my-attendance", params={"start_date": day(29), "end_date": day(27)})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert {r["student_id"] for r in body} == {att.s1.student_id}
    assert all(day(29) <= r["date"] <= day(27) for r in body)


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A02")
def test_my_attendance_requires_dates(att):
    assert att.s1_student.get(f"{BASE}/my-attendance").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A03")
def test_parent_and_admin_cannot_use_my_attendance(admin, att):
    params = {"start_date": day(29), "end_date": day(27)}
    assert att.s1_parent.get(f"{BASE}/my-attendance", params=params).status_code == 403
    assert admin.get(f"{BASE}/my-attendance", params=params).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A04")
def test_student_filter_own_and_other(att):
    params = {"start_date": day(29), "end_date": day(0)}
    own = att.s1_student.get(f"{BASE}/student/{att.s1.student_id}/filter", params=params)
    assert own.status_code == 200
    assert {r["student_id"] for r in own.json()} == {att.s1.student_id}
    assert len(own.json()) >= 3
    other = att.s1_student.get(f"{BASE}/student/{att.s2.student_id}/filter", params=params)
    assert other.status_code == 403
    assert other.json()["detail"] == "You can only access your own attendance records"


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A05")
def test_parent_filter_linked_and_unlinked(att):
    params = {"start_date": day(29), "end_date": day(0)}
    assert att.s1_parent.get(f"{BASE}/student/{att.s1.student_id}/filter", params=params).status_code == 200
    assert att.s1_parent.get(f"{BASE}/student/{att.s2.student_id}/filter", params=params).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A06")
def test_admin_filter_errors(admin, att):
    inverted = admin.get(f"{BASE}/student/{att.s1.student_id}/filter", params={"start_date": day(0), "end_date": day(5)})
    assert inverted.status_code == 400
    assert inverted.json()["detail"]["message"] == "Start date cannot be after end date"
    unknown = admin.get(f"{BASE}/student/{UNKNOWN}/filter", params={"start_date": day(5), "end_date": day(0)})
    assert unknown.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A07")
def test_filter_single_day_range(admin, att):
    response = admin.get(f"{BASE}/student/{att.s1.student_id}/filter", params={"start_date": day(28), "end_date": day(28)})
    assert response.status_code == 200
    assert [r["date"] for r in response.json()] == [day(28)]


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A08")
def test_by_date_reads(role_clients, att):
    response = role_clients["teacher"].get(f"{BASE}/by-date/{day(28)}")
    assert response.status_code == 200
    assert att.s1.student_id in [r["student_id"] for r in response.json()]
    future = role_clients["teacher"].get(f"{BASE}/by-date/{h.future_date()}")
    assert future.status_code == 400
    assert future.json()["detail"]["message"] == "Cannot retrieve attendance for future dates"


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A09")
def test_search_filters(admin, att):
    by_name = admin.get(f"{BASE}/search", params={"student_name": att.s1.first_name[:10]})
    assert by_name.status_code == 200
    assert by_name.json() and {r["student_id"] for r in by_name.json()} == {att.s1.student_id}
    ranged = admin.get(
        f"{BASE}/search", params={"student_name": att.s1.first_name[:10], "start_date": day(28), "end_date": day(28)}
    )
    assert [r["date"] for r in ranged.json()] == [day(28)]
    inverted = admin.get(f"{BASE}/search", params={"start_date": day(0), "end_date": day(3)})
    assert inverted.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A10")
def test_list_all_and_get_one(admin, att):
    everything = admin.get(f"{BASE}/")
    assert everything.status_code == 200
    mine = next(r for r in everything.json() if r["student_id"] == att.s1.student_id and r["date"] == day(28))
    one = admin.get(f"{BASE}/{mine['id']}")
    assert one.status_code == 200
    assert one.json() == mine
    assert admin.get(f"{BASE}/{UNKNOWN}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A11")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 403), ("parent", 403)]
)
def test_read_permission_matrix(role_clients, admin, att, role, status):
    one = admin.get(f"{BASE}/by-date/{day(28)}").json()[0]["id"]
    paths = [f"{BASE}/", f"{BASE}/search", f"{BASE}/by-date/{day(28)}", f"{BASE}/{one}"]
    for path in paths:
        assert role_clients[role].get(path).status_code == status, path


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A12")
def test_reads_require_token(anon, att):
    paths = [
        f"{BASE}/",
        f"{BASE}/search",
        f"{BASE}/my-attendance?start_date={day(5)}&end_date={day(0)}",
        f"{BASE}/{UNKNOWN}",
        f"{BASE}/student/{att.s1.student_id}/filter?start_date={day(5)}&end_date={day(0)}",
        f"{BASE}/by-date/{day(1)}",
    ]
    for path in paths:
        assert anon.get(path).status_code == 401, path


@pytest.mark.api
@pytest.mark.tc("TC-STU-13-A13")
def test_reads_tenant_isolation(admin, tenant_b, tenant_b_name, att):
    rows = tenant_b.get(f"{BASE}/")
    assert rows.status_code == 200
    assert att.s1.student_id not in [r["student_id"] for r in rows.json()]
    assert tenant_b.get(f"{BASE}/by-date/{day(1)}").json() == []
    header = {"cschema": tenant_b_name}
    assert admin.get(f"{BASE}/", headers=header).status_code == 403
    assert admin.get(f"{BASE}/by-date/{day(1)}", headers=header).status_code == 403
    assert admin.get(f"{BASE}/search", headers=header).status_code == 403
