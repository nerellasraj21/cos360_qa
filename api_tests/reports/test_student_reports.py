import csv
import io
import uuid

import pytest

from api_tests.reports.helpers import (
    ROLES,
    make_class,
    make_student,
    other_tenant_header,
)
from api_tests.support import Cleanup, unique

SUMMARY = "/reports/students/summary"
DETAILS = "/reports/students/details/"
EXPORT = "/reports/students/export"
ROW_KEYS = {"sl_no", "admission_no", "student_id", "class_section", "address", "city", "academic_year"}
DETAIL_KEYS = {
    "id",
    "admission_number",
    "student_id",
    "admission_date",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "previous_school_name",
    "previous_class",
    "class_name",
    "section_name",
    "academic_year",
}


@pytest.fixture(scope="module")
def roster(admin, academic_year_id):
    stack = Cleanup()
    try:
        klass = make_class(admin, stack, academic_year_id, ("A", "B"))
        students = [
            make_student(admin, stack, academic_year_id, klass, 0, "Pune"),
            make_student(admin, stack, academic_year_id, klass, 0, "Pune"),
            make_student(admin, stack, academic_year_id, klass, 1, "Delhi"),
        ]
        yield {"class": klass, "students": students, "year": academic_year_id}
    finally:
        stack.run()


def _scope(roster, **extra):
    return {"class_id": roster["class"]["id"], **extra}


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A01")
def test_summary_rows_and_shape(admin, roster):
    response = admin.get(SUMMARY, params=_scope(roster))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] == 3 and len(body["data"]) == 3
    for row in body["data"]:
        assert set(row) >= ROW_KEYS
    class_name = roster["class"]["name"]
    assert {row["class_section"] for row in body["data"]} == {f"{class_name}-A", f"{class_name}-B"}
    assert {row["student_id"] for row in body["data"]} == {s["student_id"] for s in roster["students"]}
    assert [row["sl_no"] for row in body["data"]] == [1, 2, 3]


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A02")
def test_summary_filters(admin, roster):
    section_b = roster["class"]["sections"][1]["id"]
    by_section = admin.get(SUMMARY, params=_scope(roster, section_id=section_b)).json()
    assert by_section["total_count"] == 1
    by_city = admin.get(SUMMARY, params=_scope(roster, address_city="Pune")).json()
    assert by_city["total_count"] == 2
    assert {row["city"] for row in by_city["data"]} == {"Pune"}
    by_year = admin.get(SUMMARY, params=_scope(roster, academic_year_id=roster["year"])).json()
    assert by_year["total_count"] == 3
    other_year = admin.get(SUMMARY, params=_scope(roster, academic_year_id=str(uuid.uuid4()))).json()
    assert other_year["total_count"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A03")
def test_ignored_filters(admin, roster):
    params = _scope(roster, gender="Female", caste="X", religion="Y", student_type="Z")
    assert admin.get(SUMMARY, params=params).json()["total_count"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A04")
def test_pagination(admin, roster):
    body = admin.get(SUMMARY, params=_scope(roster, page=2, page_size=2)).json()
    assert len(body["data"]) == 1
    assert body["data"][0]["sl_no"] == 3
    assert body["total_pages"] == 2 and body["page"] == 2 and body["page_size"] == 2


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A05")
@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 1001}, {"sort_order": "up"}, {"page_size": 0}])
def test_pagination_validation(admin, roster, params):
    assert admin.get(SUMMARY, params=_scope(roster, **params)).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A06")
def test_sorting(admin, roster):
    body = admin.get(SUMMARY, params=_scope(roster, sort_by="admission_number", sort_order="desc")).json()
    numbers = [row["admission_no"] for row in body["data"]]
    assert numbers == sorted(numbers, reverse=True)
    ascending = admin.get(SUMMARY, params=_scope(roster, sort_by="admission_number", sort_order="asc")).json()
    assert [row["admission_no"] for row in ascending["data"]] == sorted(numbers)
    ignored = admin.get(SUMMARY, params=_scope(roster, sort_by="no_such_column"))
    assert ignored.status_code == 200 and ignored.json()["total_count"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A07")
def test_admission_without_section_not_listed(admin, academic_year_id, cleanup):
    from api_tests.reports.helpers import admission_body

    klass = make_class(admin, cleanup, academic_year_id, ("A",))
    token = unique("rpt_s")
    body = admission_body(academic_year_id, klass["id"], None, token)
    body.pop("admitted_section_id")
    body.pop("current_section_id")
    created = admin.post("/students/admission/", json=body)
    assert created.status_code == 201, created.text
    cleanup.delete_later(admin, f"/students/admission/{created.json()['id']}")
    listed = admin.get(SUMMARY, params={"class_id": klass["id"]}).json()
    assert listed["total_count"] == 0 and listed["total_pages"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A08")
def test_details(admin, roster):
    student = roster["students"][0]
    response = admin.get(f"{DETAILS}{student['student_id']}")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert set(data) >= DETAIL_KEYS
    assert data["admission_number"] == student["admission_number"]
    assert data["city"] == "Pune"
    assert data["class_name"] == roster["class"]["name"] and data["section_name"] == "A"


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A09")
def test_details_not_found(admin, roster):
    unknown = admin.get(f"{DETAILS}{uuid.uuid4()}")
    assert unknown.status_code == 404 and unknown.json()["detail"] == "Student not found"
    wrong_year = admin.get(f"{DETAILS}{roster['students'][0]['student_id']}", params={"academic_year_id": str(uuid.uuid4())})
    assert wrong_year.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A10")
def test_export_csv(admin, roster, logins):
    response = admin.post(
        EXPORT, json={"report_type": "student_summary", "filters": {"class_id": roster["class"]["id"]}, "format": "csv"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        f"filename=student_student_summary_{logins['admin']['tenant_id']}.csv" in response.headers["content-disposition"]
    )
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 3
    assert set(rows[0]) == ROW_KEYS
    assert int(response.headers["content-length"]) == len(response.content)


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A11")
def test_export_xlsx_and_pdf(admin, roster):
    filters = {"class_id": roster["class"]["id"]}
    xlsx = admin.post(EXPORT, json={"report_type": "student_summary", "filters": filters, "format": "xlsx"})
    assert xlsx.status_code == 200
    assert xlsx.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(xlsx.content) > 0
    pdf = admin.post(EXPORT, json={"report_type": "student_summary", "filters": filters, "format": "pdf"})
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A12")
def test_export_errors_and_filename(admin, roster):
    filters = {"class_id": roster["class"]["id"]}
    assert admin.post(EXPORT, json={"report_type": "student_summary", "filters": filters, "format": "docx"}).status_code == 422
    other = admin.post(EXPORT, json={"report_type": "other", "filters": filters, "format": "csv"})
    assert other.status_code == 400 and "Unsupported report type" in other.text
    named = admin.post(
        EXPORT, json={"report_type": "student_summary", "filters": filters, "format": "csv", "filename": "qa_students"}
    )
    assert "filename=qa_students.csv" in named.headers["content-disposition"]


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A13")
def test_export_ignores_page_filters(admin, roster):
    filters = {"class_id": roster["class"]["id"], "page_size": 1, "page": 2}
    response = admin.post(EXPORT, json={"report_type": "student_summary", "filters": filters, "format": "csv"})
    assert len(list(csv.DictReader(io.StringIO(response.text)))) == 3


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A14")
def test_export_without_rows(admin):
    response = admin.post(
        EXPORT,
        json={"report_type": "student_summary", "filters": {"class_id": str(uuid.uuid4())}, "format": "csv"},
    )
    assert response.status_code == 200
    assert response.content == b""
    assert not response.headers["content-disposition"].endswith(".csv")


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A15")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher"])
def test_read_roles_allowed(role_clients, roster, role):
    client = role_clients[role]
    assert client.get(SUMMARY, params=_scope(roster)).status_code == 200
    assert client.get(f"{DETAILS}{roster['students'][0]['student_id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A15")
@pytest.mark.parametrize("role", ["student", "parent"])
def test_read_roles_denied(role_clients, roster, role):
    client = role_clients[role]
    assert client.get(SUMMARY, params=_scope(roster)).status_code >= 400
    assert client.get(f"{DETAILS}{roster['students'][0]['student_id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A15")
@pytest.mark.parametrize("role", ["student", "parent"])
def test_summary_denied_is_403(role_clients, roster, role):
    assert role_clients[role].get(SUMMARY, params=_scope(roster)).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A16")
@pytest.mark.parametrize("role", ROLES)
def test_export_role_matrix(role_clients, roster, role):
    response = role_clients[role].post(
        EXPORT, json={"report_type": "student_summary", "filters": {"class_id": roster["class"]["id"]}, "format": "csv"}
    )
    assert response.status_code == (200 if role in ("admin", "staff", "teacher") else 403)


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A17")
def test_unauthenticated(anon, roster):
    assert anon.get(SUMMARY).status_code == 401
    assert anon.get(f"{DETAILS}{roster['students'][0]['student_id']}").status_code == 401
    assert anon.post(EXPORT, json={"report_type": "student_summary", "filters": {}, "format": "csv"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-RPT-04-A18")
def test_tenant_isolation(admin, tenant_b, roster):
    summary = tenant_b.get(SUMMARY, params=_scope(roster)).json()
    assert summary["total_count"] == 0
    export = tenant_b.post(
        EXPORT, json={"report_type": "student_summary", "filters": _scope(roster), "format": "csv"}
    )
    assert export.status_code == 200 and export.content == b""
    assert tenant_b.get(f"{DETAILS}{roster['students'][0]['student_id']}").status_code == 404
    assert other_tenant_header(admin).get(SUMMARY).status_code == 403
