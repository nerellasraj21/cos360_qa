import csv
import io
import uuid

import pytest

from api_tests.reports.helpers import (
    ROLES,
    make_class,
    make_designation,
    make_staff,
    make_student,
    mark_attendance,
    mark_staff_attendance,
    other_tenant_header,
)
from api_tests.support import Cleanup

STUDENTS = "/reports/attendance/students"
STAFF = "/reports/attendance/staff"
EXPORT = "/reports/attendance/export"
RANGE = {"date_from": "2026-09-08", "date_to": "2026-09-11"}
STUDENT_ROW_KEYS = {
    "sl_no",
    "admission_no",
    "student_name",
    "class_section",
    "date",
    "attendance_status",
    "marked_at",
    "remarks",
    "academic_year",
}
STAFF_ROW_KEYS = {
    "sl_no",
    "staff_id",
    "staff_name",
    "designation",
    "department",
    "date",
    "attendance_status",
    "clock_in",
    "clock_out",
    "total_hours",
    "marked_at",
    "remarks",
}


@pytest.fixture(scope="module")
def students(admin, academic_year_id):
    stack = Cleanup()
    try:
        klass = make_class(admin, stack, academic_year_id, ("A", "B"))
        first = make_student(admin, stack, academic_year_id, klass, 0)
        second = make_student(admin, stack, academic_year_id, klass, 1)
        for day, status in (("2026-09-08", "present"), ("2026-09-09", "present"), ("2026-09-10", "present"), ("2026-09-11", "half_day")):
            mark_attendance(admin, stack, first["student_id"], day, status)
        mark_attendance(admin, stack, second["student_id"], "2026-09-10", "absent")
        mark_attendance(admin, stack, second["student_id"], "2026-09-11", "late")
        yield {"class": klass, "first": first, "second": second}
    finally:
        stack.run()


@pytest.fixture(scope="module")
def crew(admin):
    stack = Cleanup()
    try:
        designation = make_designation(admin, stack)
        first = make_staff(admin, stack, designation["id"], "Female")
        second = make_staff(admin, stack, designation["id"], "Male")
        mark_staff_attendance(admin, stack, first["id"], "2026-09-09", "present")
        mark_staff_attendance(admin, stack, first["id"], "2026-09-10", "half_day")
        mark_staff_attendance(admin, stack, second["id"], "2026-09-10", "absent")
        yield {"designation": designation, "first": first, "second": second}
    finally:
        stack.run()


def _scope(students, **extra):
    return {"class_id": students["class"]["id"], **extra}


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A01")
def test_student_list(admin, students):
    response = admin.get(STUDENTS, params=_scope(students))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] == 6
    dates = [row["date"] for row in body["data"]]
    assert dates == sorted(dates, reverse=True)
    for row in body["data"]:
        assert set(row) >= STUDENT_ROW_KEYS
        assert row["marked_at"] is None
    assert [row["sl_no"] for row in body["data"]] == [1, 2, 3, 4, 5, 6]


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A02")
def test_student_filters(admin, students):
    absent = admin.get(STUDENTS, params=_scope(students, attendance_status="absent")).json()
    assert absent["total_count"] == 1 and absent["data"][0]["attendance_status"] == "absent"
    one_day = admin.get(STUDENTS, params=_scope(students, date_from="2026-09-10", date_to="2026-09-10")).json()
    assert one_day["total_count"] == 2
    assert {row["date"] for row in one_day["data"]} == {"2026-09-10"}
    by_student = admin.get(STUDENTS, params={"student_id": students["first"]["student_id"]}).json()
    assert by_student["total_count"] == 4
    by_section = admin.get(
        STUDENTS, params=_scope(students, section_id=students["second"]["section_id"])
    ).json()
    assert by_section["total_count"] == 2


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A03")
def test_month_year_filter(admin, students):
    body = admin.get(STUDENTS, params=_scope(students, month=9, year=2026)).json()
    assert body["total_count"] == 6
    other = admin.get(STUDENTS, params=_scope(students, month=8, year=2026)).json()
    assert other["total_count"] == 0
    month_only = admin.get(STUDENTS, params=_scope(students, month=8)).json()
    assert month_only["total_count"] == 6
    assert admin.get(STUDENTS, params=_scope(students, month=13)).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A04")
def test_student_pagination(admin, students):
    page = admin.get(STUDENTS, params=_scope(students, page=2, page_size=5)).json()
    assert [row["sl_no"] for row in page["data"]] == [6]
    assert page["total_pages"] == 2
    for params in ({"page": 0}, {"page_size": 1001}, {"sort_order": "x"}):
        assert admin.get(STUDENTS, params=_scope(students, **params)).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A05")
@pytest.mark.skip(reason="the admission API creates a new student per admission, so a student with two admissions cannot be produced")
def test_student_with_two_admissions_repeats():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A06")
def test_student_stats(admin, students):
    response = admin.get(STUDENTS + "/stats", params=_scope(students, **RANGE))
    assert response.status_code == 200, response.text
    stats = response.json()["summary_stats"]
    assert stats["total_students"] == 2
    assert stats["present_count"] == 3 and stats["half_day_count"] == 1
    assert stats["absent_count"] == 1 and stats["late_count"] == 1
    assert stats["attendance_percentage"] == 58.33
    assert stats["date_range"] == "2026-09-08 to 2026-09-11"


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A07")
def test_student_stats_ignore_status_and_month(admin, students):
    plain = admin.get(STUDENTS + "/stats", params=_scope(students, **RANGE)).json()["summary_stats"]
    noisy = admin.get(
        STUDENTS + "/stats", params=_scope(students, attendance_status="absent", month=1, year=2020, **RANGE)
    ).json()["summary_stats"]
    assert noisy == plain


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A08")
def test_staff_list(admin, crew):
    response = admin.get(STAFF, params={"staff_id": crew["first"]["id"]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] == 2
    for row in body["data"]:
        assert set(row) >= STAFF_ROW_KEYS
        assert row["staff_id"] == crew["first"]["id"]
        assert row["clock_in"] is None and row["clock_out"] is None
        assert row["total_hours"] is None and row["marked_at"] is None
    uuid.UUID(body["data"][0]["staff_id"])


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A09")
def test_staff_filters(admin, crew):
    by_status = admin.get(STAFF, params={"staff_id": crew["first"]["id"], "attendance_status": "present"}).json()
    assert by_status["total_count"] == 1
    by_designation = admin.get(STAFF, params={"designation_id": crew["designation"]["id"]}).json()
    assert by_designation["total_count"] == 3
    by_department = admin.get(
        STAFF, params={"designation_id": crew["designation"]["id"], "department": "Admin"}
    ).json()
    assert by_department["total_count"] == 3
    by_date = admin.get(
        STAFF, params={"designation_id": crew["designation"]["id"], "date_from": "2026-09-10", "date_to": "2026-09-10"}
    ).json()
    assert by_date["total_count"] == 2


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A10")
def test_staff_stats(admin, crew):
    response = admin.get(
        STAFF + "/stats", params={"staff_id": crew["first"]["id"], "date_from": "2026-09-09", "date_to": "2026-09-10"}
    )
    assert response.status_code == 200, response.text
    stats = response.json()["summary_stats"]
    assert stats["total_staff"] == 1
    assert stats["present_count"] == 1 and stats["half_day_count"] == 1
    assert stats["attendance_percentage"] == 75.0
    assert stats["date_range"] == "2026-09-09 to 2026-09-10"


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A11")
def test_exports(admin, students, crew):
    filters = {"class_id": students["class"]["id"], "page_size": 1}
    csv_response = admin.post(
        EXPORT, json={"report_type": "student_attendance", "filters": filters, "format": "csv"}
    )
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert len(list(csv.DictReader(io.StringIO(csv_response.text)))) == 6
    xlsx = admin.post(EXPORT, json={"report_type": "student_attendance", "filters": filters, "format": "xlsx"})
    assert xlsx.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(xlsx.content) > 0
    pdf = admin.post(EXPORT, json={"report_type": "student_attendance", "filters": filters, "format": "pdf"})
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    staff_csv = admin.post(
        EXPORT,
        json={"report_type": "staff_attendance", "filters": {"staff_id": crew["first"]["id"]}, "format": "csv"},
    )
    assert staff_csv.status_code == 200
    assert len(list(csv.DictReader(io.StringIO(staff_csv.text)))) == 2


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A12")
def test_export_unsupported_type(admin):
    response = admin.post(EXPORT, json={"report_type": "fees", "filters": {}, "format": "csv"})
    assert response.status_code == 400
    assert "Unsupported attendance report type" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A13")
@pytest.mark.parametrize("role", ROLES)
def test_read_role_matrix(role_clients, students, crew, role):
    expected = 200 if role in ("admin", "staff", "teacher") else 403
    client = role_clients[role]
    scope = _scope(students)
    assert client.get(STUDENTS, params=scope).status_code == expected
    assert client.get(STUDENTS + "/stats", params=scope).status_code == expected
    assert client.get(STAFF, params={"staff_id": crew["first"]["id"]}).status_code == expected
    assert client.get(STAFF + "/stats", params={"staff_id": crew["first"]["id"]}).status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A14")
@pytest.mark.parametrize("role", ROLES)
def test_export_role_matrix(role_clients, students, role):
    expected = 200 if role in ("admin", "staff", "teacher") else 403
    response = role_clients[role].post(
        EXPORT,
        json={"report_type": "student_attendance", "filters": {"class_id": students["class"]["id"]}, "format": "csv"},
    )
    assert response.status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A13")
def test_unauthenticated(anon):
    assert anon.get(STUDENTS).status_code == 401
    assert anon.get(STAFF + "/stats").status_code == 401
    assert anon.post(EXPORT, json={"report_type": "student_attendance", "filters": {}, "format": "csv"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-RPT-07-A15")
def test_tenant_isolation(admin, tenant_b, students, crew):
    scope = _scope(students)
    assert tenant_b.get(STUDENTS, params=scope).json()["total_count"] == 0
    stats = tenant_b.get(STUDENTS + "/stats", params={**scope, **RANGE}).json()["summary_stats"]
    assert stats["present_count"] == 0 and stats["total_students"] == 0
    assert tenant_b.get(STAFF, params={"staff_id": crew["first"]["id"]}).json()["total_count"] == 0
    assert other_tenant_header(admin).get(STUDENTS).status_code == 403
