import csv
import io
from datetime import date, timedelta

import pytest

from api_tests.reports.helpers import ROLES, make_class, make_student, other_tenant_header
from api_tests.support import Cleanup, unique

COLLECTION = "/reports/fees/collection-summary"
PENDING = "/reports/fees/pending-fees"
STRUCTURE = "/reports/fees/fee-structure"
EXPORT = "/reports/fees/export"
PAST_DAYS = 60
FUTURE_DAYS = 120


@pytest.fixture(scope="module")
def fees(admin, academic_year_id):
    stack = Cleanup()
    try:
        token = unique("rpt_")
        klass = make_class(admin, stack, academic_year_id, ("A",))
        past = date.today() - timedelta(days=PAST_DAYS)
        future = date.today() + timedelta(days=FUTURE_DAYS)
        term = admin.post(
            "/fee/terms/",
            json={
                "term_name": token,
                "term_status": "active",
                "number_of_terms": 2,
                "academic_year_id": academic_year_id,
                "fee_term_dates": [{"fee_term_date": past.isoformat()}, {"fee_term_date": future.isoformat()}],
            },
        )
        assert term.status_code == 201, term.text
        term = term.json()
        stack.delete_later(admin, f"/fee/terms/{term['id']}")
        category = admin.post(
            "/fee/categories/",
            json={"category_name": token, "category_status": "active", "academic_year_id": academic_year_id},
        )
        assert category.status_code == 201, category.text
        category = category.json()
        stack.delete_later(admin, f"/fee/categories/{category['id']}")
        fee_type = admin.post(
            "/fee/types/",
            json={
                "type_name": token,
                "fee_category_id": category["id"],
                "fee_status": "active",
                "fee_term_id": term["id"],
                "academic_year_id": academic_year_id,
            },
        )
        assert fee_type.status_code == 201, fee_type.text
        fee_type = fee_type.json()
        stack.delete_later(admin, f"/fee/types/{fee_type['id']}")
        mapping = admin.post(
            "/fee/class-mappings/",
            json={
                "class_id": klass["id"],
                "fee_type_id": fee_type["id"],
                "total_fee": 6000,
                "academic_year_id": academic_year_id,
                "all_by_default": True,
            },
        )
        assert mapping.status_code == 201, mapping.text
        mapping = mapping.json()
        stack.delete_later(admin, f"/fee/class-mappings/{mapping['id']}")
        dates = sorted(admin.get(f"/fee/terms/{term['id']}/dates").json(), key=lambda row: row["fee_term_date"])
        amounts = admin.post(
            "/fee/class-mapping-term-amounts/",
            json={
                "fee_class_mapping_id": mapping["id"],
                "term_amounts": [
                    {"term_date_id": dates[0]["id"], "term_amount": 4000},
                    {"term_date_id": dates[1]["id"], "term_amount": 2000},
                ],
            },
        )
        assert amounts.status_code == 201, amounts.text
        student = make_student(admin, stack, academic_year_id, klass, 0, "Pune")
        yield {
            "token": token,
            "class": klass,
            "category": category,
            "type": fee_type,
            "student": student,
            "past": past,
            "future": future,
        }
    finally:
        stack.run()


def _scope(fees, **extra):
    return {"class_id": fees["class"]["id"], **extra}


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A01")
@pytest.mark.skip(reason="a completed fee payment cannot be removed afterwards (admission delete returns 409), so collection rows cannot be created without leaving data behind")
def test_collection_rows_for_fixture():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A01")
def test_collection_summary_shape_without_payments(admin, fees):
    response = admin.get(COLLECTION, params=_scope(fees))
    assert response.status_code == 200
    body = response.json()
    assert body == {"data": [], "total_count": 0, "page": 1, "page_size": 100, "total_pages": 0}


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A02")
@pytest.mark.skip(reason="needs completed fee payments; see TC-RPT-06-A01")
def test_collection_filters():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A03")
def test_collection_date_filters_accept_date_only(admin, fees):
    params = _scope(fees, date_from="2026-09-01", date_to="2026-09-05")
    response = admin.get(COLLECTION, params=params)
    assert response.status_code == 200 and response.json()["total_count"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A04")
def test_collection_malformed_date_is_validation_error(admin, fees):
    response = admin.get(COLLECTION, params=_scope(fees, date_from="garbage"))
    assert response.status_code == 422
    assert "date_from must be an ISO date or datetime" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A05")
def test_collection_pagination_envelope(admin, fees):
    body = admin.get(COLLECTION, params=_scope(fees, page=2, page_size=1)).json()
    assert body["page"] == 2 and body["page_size"] == 1
    assert {"data", "total_count", "total_pages"} <= set(body)


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A06")
@pytest.mark.parametrize("path", [COLLECTION, PENDING, STRUCTURE])
@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 5000}, {"page_size": 0}])
def test_paging_bounds_are_validation_errors(admin, fees, path, params):
    assert admin.get(path, params=_scope(fees, **params)).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A07")
def test_collection_sort_params(admin, fees):
    ok = admin.get(COLLECTION, params=_scope(fees, sort_by="transaction_number", sort_order="asc"))
    assert ok.status_code == 200
    unknown = admin.get(COLLECTION, params=_scope(fees, sort_by="no_such_column"))
    assert unknown.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A08")
def test_collection_stats_empty_scope(admin, fees):
    response = admin.get(COLLECTION + "/stats", params=_scope(fees))
    assert response.status_code == 200
    body = response.json()
    assert body["total_collected"] == 0 and body["total_due"] == 0
    assert body["collection_percentage"] == 0.0
    assert body["payment_methods"] == {} and body["fee_categories"] == {} and body["monthly_collection"] == {}


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A09")
def test_pending_fees_rows(admin, fees):
    response = admin.get(PENDING, params=_scope(fees))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] == 2
    overdue, upcoming = sorted(body["data"], key=lambda row: row["due_date"])
    student = fees["student"]
    for row in body["data"]:
        assert row["student_admission_no"] == student["admission_number"]
        assert row["fee_category"] == fees["token"] and row["fee_type"] == fees["token"]
        assert row["fee_term"] == fees["token"]
        assert row["amount_paid"] == 0.0
        assert set(row) >= {
            "sl_no",
            "student_name",
            "class_section",
            "amount_due",
            "balance_amount",
            "due_date",
            "days_overdue",
        }
    assert overdue["amount_due"] == 4000.0 and overdue["balance_amount"] == 4000.0
    assert overdue["days_overdue"] == PAST_DAYS
    assert upcoming["amount_due"] == 2000.0 and upcoming["days_overdue"] is None


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A10")
def test_pending_fee_filters(admin, fees):
    overdue_only = admin.get(PENDING, params=_scope(fees, days_overdue=30)).json()
    assert [row["amount_due"] for row in overdue_only["data"]] == [4000.0]
    none_left = admin.get(PENDING, params=_scope(fees, days_overdue=PAST_DAYS + 1)).json()
    assert none_left["data"] == []
    big = admin.get(PENDING, params=_scope(fees, amount_min=3000)).json()
    assert [row["balance_amount"] for row in big["data"]] == [4000.0]
    small = admin.get(PENDING, params=_scope(fees, amount_max=3000)).json()
    assert [row["balance_amount"] for row in small["data"]] == [2000.0]


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A10")
def test_pending_sort_balance(admin, fees):
    body = admin.get(PENDING, params=_scope(fees, sort_by="balance_amount", sort_order="desc")).json()
    assert [row["balance_amount"] for row in body["data"]] == [4000.0, 2000.0]


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A11")
def test_pending_stats(admin, fees):
    stats = admin.get(PENDING + "/stats", params=_scope(fees)).json()
    assert stats["total_pending_amount"] == 6000.0
    assert stats["total_overdue_amount"] == 4000.0
    assert stats["total_students_with_pending"] == 1 and stats["total_students_overdue"] == 1
    assert stats["average_overdue_days"] == float(PAST_DAYS)
    assert stats["fee_categories_pending"] == {fees["token"]: 6000.0}
    assert stats["class_wise_pending"] == {fees["class"]["name"]: 6000.0}











@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A12")
def test_fee_structure_rows(admin, fees):
    response = admin.get(STRUCTURE, params=_scope(fees))
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 1
    row = rows[0]
    assert row["fee_category"] == fees["token"] and row["fee_type"] == fees["token"]
    assert row["class_name"] == fees["class"]["name"]
    assert row["section_name"] is None
    assert row["fee_amount"] == 6000.0
    assert set(row) >= {"sl_no", "fee_term", "academic_year", "status"}


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A13")
def test_fee_structure_stats(admin, fees):
    stats = admin.get(STRUCTURE + "/stats", params=_scope(fees)).json()
    assert stats["total_fee_types"] == 1 and stats["total_categories"] == 1 and stats["total_terms"] == 1
    assert stats["average_fee_amount"] == 6000.0
    assert stats["fee_range"] == {"min": 6000.0, "max": 6000.0}
    assert stats["category_wise_breakdown"] == {fees["token"]: 1}


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A14")
@pytest.mark.parametrize(
    "report_type,expected_rows",
    [("pending_fees", 2), ("fee_structure", 1), ("fee_collection_summary", 0)],
)
def test_exports(admin, fees, report_type, expected_rows):
    filters = {"class_id": fees["class"]["id"], "page_size": 1}
    csv_response = admin.post(EXPORT, json={"report_type": report_type, "filters": filters, "format": "csv"})
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert len(list(csv.DictReader(io.StringIO(csv_response.text)))) == expected_rows
    xlsx = admin.post(EXPORT, json={"report_type": report_type, "filters": filters, "format": "xlsx"})
    assert xlsx.status_code == 200
    pdf = admin.post(EXPORT, json={"report_type": report_type, "filters": filters, "format": "pdf"})
    assert pdf.status_code == 200
    if expected_rows:
        assert xlsx.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert len(xlsx.content) > 0
        assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A15")
def test_export_errors(admin):
    bad_type = admin.post(EXPORT, json={"report_type": "x", "filters": {}, "format": "csv"})
    assert bad_type.status_code == 400 and "Unsupported fee report type" in bad_type.text
    bad_format = admin.post(EXPORT, json={"report_type": "pending_fees", "filters": {}, "format": "json"})
    assert bad_format.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A16")
def test_export_collection_with_date_only_upper_bound(admin, fees):
    response = admin.post(
        EXPORT,
        json={
            "report_type": "fee_collection_summary",
            "filters": {"class_id": fees["class"]["id"], "date_to": "2026-09-30"},
            "format": "csv",
        },
    )
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A17")
@pytest.mark.parametrize("role", ROLES)
def test_read_role_matrix(role_clients, fees, role):
    expected = 200 if role in ("admin", "staff") else 403
    client = role_clients[role]
    scope = _scope(fees)
    for path in (
        COLLECTION,
        COLLECTION + "/stats",
        PENDING,
        PENDING + "/stats",
        STRUCTURE,
        STRUCTURE + "/stats",
    ):
        assert client.get(path, params=scope).status_code == expected, path


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A18")
@pytest.mark.parametrize("role", ROLES)
def test_export_role_matrix(role_clients, fees, role):
    expected = 200 if role in ("admin", "staff") else 403
    response = role_clients[role].post(
        EXPORT,
        json={"report_type": "fee_structure", "filters": {"class_id": fees["class"]["id"]}, "format": "csv"},
    )
    assert response.status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A17")
def test_unauthenticated(anon):
    assert anon.get(COLLECTION).status_code == 401
    assert anon.get(PENDING + "/stats").status_code == 401
    assert anon.post(EXPORT, json={"report_type": "fee_structure", "filters": {}, "format": "csv"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-RPT-06-A19")
def test_tenant_isolation(admin, tenant_b, fees):
    scope = _scope(fees)
    assert tenant_b.get(PENDING, params=scope).json()["data"] == []
    assert tenant_b.get(STRUCTURE, params=scope).json()["data"] == []
    assert tenant_b.get(COLLECTION, params=scope).json()["data"] == []
    stats = tenant_b.get(PENDING + "/stats", params=scope).json()
    assert stats["total_pending_amount"] == 0
    export = tenant_b.post(EXPORT, json={"report_type": "pending_fees", "filters": scope, "format": "csv"})
    assert export.status_code == 200 and export.content == b""
    assert other_tenant_header(admin).get(PENDING).status_code == 403
