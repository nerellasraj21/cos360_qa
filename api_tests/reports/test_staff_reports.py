import csv
import io
import uuid

import pytest

from api_tests.reports.helpers import ROLES, make_designation, make_staff, other_tenant_header
from api_tests.support import Cleanup

SUMMARY = "/reports/staff/summary"
DETAILS = "/reports/staff/details/"
EXPORT = "/reports/staff/export"
ROW_KEYS = {
    "sl_no",
    "staff_id",
    "full_name",
    "department",
    "designation",
    "email",
    "phone",
    "address",
    "gender",
    "is_active",
    "academic_year",
}
DETAIL_KEYS = {
    "id",
    "full_name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "address",
    "date_of_birth",
    "gender",
    "qualification",
    "experience_years",
    "joining_date",
    "is_active",
    "department",
    "designation_name",
    "academic_year",
}


@pytest.fixture(scope="module")
def crew(admin):
    stack = Cleanup()
    try:
        designation = make_designation(admin, stack)
        members = [
            make_staff(admin, stack, designation["id"], "Female"),
            make_staff(admin, stack, designation["id"], "Female"),
            make_staff(admin, stack, designation["id"], "Male"),
        ]
        yield {"designation": designation, "members": members}
    finally:
        stack.run()


def _mine(admin, crew, **params):
    body = admin.get(SUMMARY, params={"page_size": 1000, **params}).json()
    ids = {member["id"] for member in crew["members"]}
    return [row for row in body["data"] if row["staff_id"] in ids]


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A01")
def test_summary_lists_my_staff(admin, crew):
    response = admin.get(SUMMARY, params={"page_size": 1000})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] >= 3
    mine = _mine(admin, crew)
    assert len(mine) == 3
    for row in mine:
        assert set(row) >= ROW_KEYS
        assert row["designation"] == crew["designation"]["title"]
        assert row["academic_year"] == "N/A"
    first = crew["members"][0]
    row = next(r for r in mine if r["staff_id"] == first["id"])
    assert row["full_name"] == f"{first['first_name']} {first['last_name']}"
    assert row["email"] == first["email"] and row["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A02")
def test_gender_filter(admin, crew):
    females = _mine(admin, crew, gender="Female")
    assert len(females) == 2
    assert {row["gender"] for row in females} == {"Female"}
    body = admin.get(SUMMARY, params={"gender": "Female", "page_size": 1000}).json()
    assert {row["gender"] for row in body["data"]} == {"Female"}


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A03")
def test_ignored_filters(admin, crew):
    params = {"department_id": str(uuid.uuid4()), "employment_type": "x", "subject_id": str(uuid.uuid4())}
    assert len(_mine(admin, crew, **params)) == 3


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A04")
def test_staff_without_designation_excluded(admin, crew, cleanup):
    staff = make_staff(admin, cleanup, None)
    body = admin.get(SUMMARY, params={"page_size": 1000}).json()
    assert staff["id"] not in [row["staff_id"] for row in body["data"]]


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A05")
def test_pagination(admin, crew):
    full = admin.get(SUMMARY, params={"page_size": 1000}).json()
    total = full["total_count"]
    page = admin.get(SUMMARY, params={"page": 2, "page_size": 2}).json()
    assert [row["sl_no"] for row in page["data"]] == [3, 4][: len(page["data"])]
    assert page["total_pages"] == (total + 1) // 2
    assert admin.get(SUMMARY, params={"page_size": 0}).status_code == 422
    assert admin.get(SUMMARY, params={"page": 0}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A06")
def test_details(admin, crew):
    member = crew["members"][0]
    response = admin.get(f"{DETAILS}{member['id']}")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert set(data) >= DETAIL_KEYS
    assert data["id"] == member["id"]
    assert data["designation_name"] == crew["designation"]["title"]
    assert data["joining_date"] == "2026-01-05"
    assert data["department"] == "Admin"


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A07")
def test_details_unknown(admin):
    response = admin.get(f"{DETAILS}{uuid.uuid4()}")
    assert response.status_code == 404 and response.json()["detail"] == "Staff not found"
    assert admin.get(f"{DETAILS}not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A08")
def test_export_formats(admin, crew):
    filters = {"gender": "Male"}
    csv_response = admin.post(EXPORT, json={"report_type": "staff_summary", "filters": filters, "format": "csv"})
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(csv_response.text)))
    assert crew["members"][2]["id"] in [row["staff_id"] for row in rows]
    xlsx = admin.post(EXPORT, json={"report_type": "staff_summary", "filters": filters, "format": "xlsx"})
    assert xlsx.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(xlsx.content) > 0
    pdf = admin.post(EXPORT, json={"report_type": "staff_summary", "filters": filters, "format": "pdf"})
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A08")
def test_export_gender_value_is_plain(admin, crew):
    response = admin.post(
        EXPORT, json={"report_type": "staff_summary", "filters": {"gender": "Male"}, "format": "csv"}
    )
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows and {row["gender"] for row in rows} == {"Male"}


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A09")
def test_export_unsupported_type(admin):
    response = admin.post(EXPORT, json={"report_type": "staff_attendance", "filters": {}, "format": "csv"})
    assert response.status_code == 400 and "Unsupported report type" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A10")
@pytest.mark.parametrize("role", ["admin", "staff"])
def test_read_roles_allowed(role_clients, crew, role):
    client = role_clients[role]
    assert client.get(SUMMARY, params={"page_size": 5}).status_code == 200
    assert client.get(f"{DETAILS}{crew['members'][0]['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A10")
@pytest.mark.parametrize("role", ["teacher", "student", "parent"])
def test_read_roles_denied(role_clients, crew, role):
    client = role_clients[role]
    assert client.get(SUMMARY, params={"page_size": 5}).status_code >= 400
    assert client.get(f"{DETAILS}{crew['members'][0]['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A10")
@pytest.mark.parametrize("role", ["teacher", "student", "parent"])
def test_summary_denied_is_403(role_clients, role):
    assert role_clients[role].get(SUMMARY, params={"page_size": 5}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A11")
@pytest.mark.parametrize("role", ROLES)
def test_export_role_matrix(role_clients, role):
    response = role_clients[role].post(
        EXPORT, json={"report_type": "staff_summary", "filters": {"gender": "Other"}, "format": "csv"}
    )
    assert response.status_code == (200 if role == "admin" else 403)


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A11")
def test_unauthenticated(anon):
    assert anon.get(SUMMARY).status_code == 401
    assert anon.post(EXPORT, json={"report_type": "staff_summary", "filters": {}, "format": "csv"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-RPT-05-A12")
def test_tenant_isolation(admin, tenant_b, crew):
    ids = {member["id"] for member in crew["members"]}
    body = tenant_b.get(SUMMARY, params={"page_size": 1000}).json()
    assert not ids & {row["staff_id"] for row in body["data"]}
    assert tenant_b.get(f"{DETAILS}{crew['members'][0]['id']}").status_code == 404
    assert other_tenant_header(admin).get(SUMMARY).status_code == 403
