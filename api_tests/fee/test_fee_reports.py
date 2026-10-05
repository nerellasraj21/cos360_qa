import csv
import io
from datetime import date, timedelta

import pytest

from api_tests.fee import helpers as h
from api_tests.support import Cleanup

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
RP = "/reports/fees"

COLLECTION_FIELDS = {
    "sl_no", "transaction_number", "student_admission_no", "student_name", "class_section", "fee_category", "fee_type",
    "fee_term", "amount_due", "amount_paid", "payment_method", "payment_status", "transaction_date", "collected_by",
}


@pytest.fixture(scope="module")
def rep(admin, year_id, fee_world):
    stack = Cleanup()
    cls = h.make_class(admin, stack, year_id, sections=("A", "B"))
    cat = h.make_category(admin, stack, year_id)
    term = h.make_term(admin, stack, year_id)
    ftype = h.make_type(admin, stack, year_id, cat["id"], term["id"])
    h.make_class_mapping(admin, stack, year_id, cls["id"], ftype["id"], "12000.00")
    names = sorted(cls["sections"])
    a = h.make_student(admin, stack, year_id, cls, names[0])
    b = h.make_student(admin, stack, year_id, cls, names[0])
    h.map_student(admin, stack, year_id, a, ftype["id"])
    h.map_student(admin, stack, year_id, b, ftype["id"])
    t = ftype["id"]
    h.ok(h.pay(admin, a, year_id, "5000.00", [(t, "5000.00")]))
    h.ok(h.pay(admin, a, year_id, "2500.00", [(t, "2500.00")], method="upi", upi_reference="REP-U1"))
    h.ok(
        h.pay(admin, a, year_id, "1000.00", [(t, "1000.00")], method="cheque", cheque_number="CHQ-R", cheque_bank="Test Bank", cheque_date=date.today().isoformat())
    )
    cls2 = h.make_class(admin, stack, year_id)
    type2 = h.make_type(admin, stack, year_id, cat["id"], term["id"])
    c = h.make_student(admin, stack, year_id, cls2)
    h.map_student(admin, stack, year_id, c, type2["id"], "12000.00")
    h.ok(
        admin.post(
            "/fee/concessions/bulk",
            json={
                "student_id": c["id"],
                "academic_year_id": year_id,
                "concessions": [{"fee_type_id": type2["id"], "concession_amount": "2000.00", "reason": "Report check", "approved_by": "owner"}],
            },
        )
    )
    yield {"class": cls, "section_a": cls["sections"][names[0]], "type": ftype, "a": a, "b": b, "c": c, "type2": type2, "class2": cls2, "category": cat}
    stack.run()


def q(rep, year_id, **extra):
    return {"academic_year_id": year_id, "fee_type_id": rep["type"]["id"], **extra}


def get(admin, path, params):
    return admin.get(f"{RP}/{path}", params=params)


@pytest.mark.tc("TC-FEE-15-A01")
def test_collection_summary_rows(admin, rep, year_id):
    r = h.ok(get(admin, "collection-summary", q(rep, year_id)))
    body = r.json()
    assert set(body) >= {"data", "total_count", "page", "page_size", "total_pages"}
    assert body["total_count"] == 5 and len(body["data"]) == 5
    assert all(set(row) == COLLECTION_FIELDS for row in body["data"])
    assert [row["sl_no"] for row in body["data"]] == [1, 2, 3, 4, 5]
    assert {row["student_admission_no"] for row in body["data"]} == {rep["a"]["admission_number"]}
    assert sorted(row["payment_method"] for row in body["data"]) == ["cash", "cash", "cheque", "upi", "upi"]
    assert body["page"] == 1 and body["page_size"] == 100 and body["total_pages"] == 1


@pytest.mark.tc("TC-FEE-15-A02")
def test_collection_summary_filters(admin, rep, year_id):
    params = q(rep, year_id, status="completed", payment_method="cash", class_id=rep["class"]["id"], section_id=rep["section_a"])
    rows = h.ok(get(admin, "collection-summary", params)).json()["data"]
    assert len(rows) == 2 and all(r["payment_method"] == "cash" and r["payment_status"] == "completed" for r in rows)
    pending = h.ok(get(admin, "collection-summary", q(rep, year_id, status="pending"))).json()["data"]
    assert [r["payment_method"] for r in pending] == ["cheque"]


@pytest.mark.tc("TC-FEE-15-A03")
def test_collection_summary_date_only_range(admin, rep, year_id):
    today = date.today().isoformat()
    body = h.ok(get(admin, "collection-summary", q(rep, year_id, date_from=today, date_to=today))).json()
    assert body["total_count"] == 5
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert h.ok(get(admin, "collection-summary", q(rep, year_id, date_from=yesterday, date_to=yesterday))).json()["total_count"] == 0


@pytest.mark.tc("TC-FEE-15-A04")
def test_collection_summary_pagination(admin, rep, year_id):
    body = h.ok(get(admin, "collection-summary", q(rep, year_id, page=2, page_size=1))).json()
    assert len(body["data"]) == 1 and body["data"][0]["sl_no"] == 2
    assert body["page"] == 2 and body["page_size"] == 1
    assert body["total_pages"] == body["total_count"] == 5


@pytest.mark.tc("TC-FEE-15-A05")
def test_collection_summary_sorting(admin, rep, year_id):
    rows = h.ok(get(admin, "collection-summary", q(rep, year_id, sort_by="total_amount", sort_order="asc"))).json()["data"]
    paid = [r["amount_paid"] for r in rows]
    assert len(rows) == 5
    default = h.ok(get(admin, "collection-summary", q(rep, year_id, sort_by="not_a_column"))).json()
    assert default["total_count"] == 5


@pytest.mark.tc("TC-FEE-15-A06")
@pytest.mark.parametrize(
    "extra", [{"page_size": 0}, {"page_size": 1001}, {"sort_order": "up"}, {"date_from": "notadate"}, {"date_to": "notadate"}, {"page": 0}]
)
def test_collection_summary_invalid_filters(extra, admin, rep, year_id):
    assert get(admin, "collection-summary", q(rep, year_id, **extra)).status_code == 422


@pytest.mark.tc("TC-FEE-15-A07")
def test_collection_stats(admin, rep, year_id):
    data = h.ok(get(admin, "collection-summary/stats", q(rep, year_id))).json()
    assert data["total_collected"] == 7500.0
    assert data["total_due"] == 9000.0
    assert data["collection_percentage"] == round(7500.0 / 9000.0 * 100, 2) == 83.33
    assert data["payment_methods"] == {"cash": 5000.0, "upi": 2500.0}
    assert list(data["fee_categories"].values()) == [7500.0]
    month = date.today().strftime("%Y-%m")
    assert data["monthly_collection"] == {month: 7500.0}


@pytest.mark.tc("TC-FEE-15-A08")
def test_collection_stats_agree_with_table(admin, rep, year_id):
    rows = h.ok(get(admin, "collection-summary", q(rep, year_id, status="completed"))).json()["data"]
    stats = h.ok(get(admin, "collection-summary/stats", q(rep, year_id))).json()
    assert sum(r["amount_paid"] for r in rows) == stats["total_collected"]


@pytest.mark.tc("TC-FEE-15-A09")
def test_pending_fees_rows(admin, rep, year_id):
    body = h.ok(get(admin, "pending-fees", q(rep, year_id))).json()
    rows = body["data"]
    assert body["total_count"] == 6
    a_rows = [r for r in rows if r["student_admission_no"] == rep["a"]["admission_number"]]
    b_rows = [r for r in rows if r["student_admission_no"] == rep["b"]["admission_number"]]
    assert sorted((r["due_date"], r["balance_amount"]) for r in a_rows) == [("2026-12-10", 1500.0), ("2027-03-10", 3000.0)]
    assert sorted((r["due_date"], r["balance_amount"]) for r in b_rows) == [
        ("2026-06-10", 3000.0), ("2026-09-10", 3000.0), ("2026-12-10", 3000.0), ("2027-03-10", 3000.0),
    ]
    today = date.today()
    for r in rows:
        due = date.fromisoformat(r["due_date"])
        assert r["days_overdue"] == ((today - due).days if due < today else None)
        assert set(r) == {"sl_no", "student_admission_no", "student_name", "class_section", "fee_category", "fee_type", "fee_term", "amount_due", "amount_paid", "balance_amount", "due_date", "days_overdue"}


@pytest.mark.tc("TC-FEE-15-A10")
def test_pending_fees_overdue_and_amount_filters(admin, rep, year_id):
    rows = h.ok(get(admin, "pending-fees", q(rep, year_id, days_overdue=30, amount_min=1000))).json()["data"]
    assert [(r["student_admission_no"], r["due_date"]) for r in rows] == [(rep["b"]["admission_number"], "2026-06-10")]
    ignored = h.ok(get(admin, "pending-fees", q(rep, year_id, amount_min=0, amount_max=0))).json()
    assert ignored["total_count"] == 6


@pytest.mark.tc("TC-FEE-15-A11")
def test_pending_fees_sort_by_balance_desc(admin, rep, year_id):
    rows = h.ok(get(admin, "pending-fees", q(rep, year_id, sort_by="balance_amount", sort_order="desc"))).json()["data"]
    balances = [r["balance_amount"] for r in rows]
    assert balances == sorted(balances, reverse=True)
    assert balances[0] == 3000.0 and balances[-1] == 1500.0


@pytest.mark.tc("TC-FEE-15-A12")
def test_pending_fees_stats(admin, rep, year_id):
    data = h.ok(get(admin, "pending-fees/stats", q(rep, year_id))).json()
    assert data["total_pending_amount"] == 16500.0
    assert data["total_overdue_amount"] == 6000.0
    assert data["total_students_with_pending"] == 2
    assert data["total_students_overdue"] == 1
    due1 = (date.today() - date(2026, 6, 10)).days
    due2 = (date.today() - date(2026, 9, 10)).days
    assert data["average_overdue_days"] == round((due1 + due2) / 2, 1)
    assert data["class_wise_pending"] == {rep["class"]["name"]: 16500.0}
    assert list(data["fee_categories_pending"].values()) == [16500.0]


@pytest.mark.tc("TC-FEE-15-A13")
def test_pending_report_ignores_concession(admin, rep, year_id):
    rows = h.ok(get(admin, "pending-fees", {"academic_year_id": year_id, "fee_type_id": rep["type2"]["id"]})).json()["data"]
    assert len(rows) == 4
    assert all(r["balance_amount"] == 3000.0 for r in rows)


@pytest.mark.tc("TC-FEE-15-A14")
def test_fee_structure_rows(admin, rep, year_id):
    body = h.ok(get(admin, "fee-structure", {"academic_year_id": year_id, "class_id": rep["class"]["id"]})).json()
    assert body["total_count"] == 1
    row = body["data"][0]
    assert row["fee_type"] == rep["type"]["type_name"] and row["class_name"] == rep["class"]["name"]
    assert row["fee_amount"] == 12000.0 and row["section_name"] is None and row["status"] == "active"
    assert row["fee_category"] == rep["category"]["category_name"]


@pytest.mark.tc("TC-FEE-15-A15")
def test_fee_structure_stats(admin, rep, year_id):
    data = h.ok(get(admin, "fee-structure/stats", {"academic_year_id": year_id, "class_id": rep["class"]["id"]})).json()
    assert data["total_fee_types"] == 1 and data["total_categories"] == 1 and data["total_terms"] == 1
    assert data["average_fee_amount"] == 12000.0
    assert data["fee_range"] == {"min": 12000.0, "max": 12000.0}
    assert data["category_wise_breakdown"] == {rep["category"]["category_name"]: 1}


def export(admin, report_type, filters, fmt="csv", **extra):
    return admin.post(f"{RP}/export", json={"report_type": report_type, "filters": filters, "format": fmt, **extra})


@pytest.mark.tc("TC-FEE-15-A16")
def test_export_collection_csv(admin, rep, year_id):
    r = h.ok(export(admin, "fee_collection_summary", q(rep, year_id)))
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and ".csv" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == ["sl_no", "transaction_number", "student_admission_no", "student_name", "class_section", "fee_category", "fee_type", "fee_term", "amount_due", "amount_paid", "payment_method", "payment_status", "transaction_date", "collected_by"]
    assert len(rows) - 1 == 5


@pytest.mark.tc("TC-FEE-15-A16")
def test_export_includes_rows_beyond_one_page(admin, rep, year_id):
    r = h.ok(export(admin, "fee_collection_summary", q(rep, year_id, page_size=2)))
    assert len(list(csv.reader(io.StringIO(r.text)))) - 1 == 5


@pytest.mark.tc("TC-FEE-15-A17")
def test_export_xlsx_and_pdf(admin, rep, year_id):
    x = h.ok(export(admin, "fee_collection_summary", q(rep, year_id), "xlsx", filename="fee_rep_x"))
    assert "spreadsheetml" in x.headers["content-type"] and len(x.content) > 100 and x.content[:2] == b"PK"
    assert "attachment" in x.headers["content-disposition"] and "fee_rep_x" in x.headers["content-disposition"]
    p = h.ok(export(admin, "fee_collection_summary", q(rep, year_id), "pdf"))
    assert p.headers["content-type"].startswith("application/pdf") and p.content.startswith(b"%PDF")


@pytest.mark.tc("TC-FEE-15-A18")
@pytest.mark.parametrize("report_type", ["pending_fees", "fee_structure"])
def test_export_other_reports(report_type, admin, rep, year_id):
    filters = q(rep, year_id) if report_type == "pending_fees" else {"academic_year_id": year_id, "class_id": rep["class"]["id"]}
    r = h.ok(export(admin, report_type, filters))
    assert r.headers["content-type"].startswith("text/csv")
    assert len(list(csv.reader(io.StringIO(r.text)))) - 1 == (6 if report_type == "pending_fees" else 1)


@pytest.mark.tc("TC-FEE-15-A19")
def test_export_validation(admin, rep, year_id):
    r = export(admin, "x", q(rep, year_id))
    assert r.status_code == 400
    assert "Unsupported fee report type" in h.detail_text(r)
    assert export(admin, "fee_collection_summary", q(rep, year_id), "txt").status_code == 422


@pytest.mark.tc("TC-FEE-15-A20")
def test_export_row_count_matches_table(admin, rep, year_id):
    params = q(rep, year_id, status="completed")
    total = h.ok(get(admin, "collection-summary", params)).json()["total_count"]
    rows = list(csv.reader(io.StringIO(h.ok(export(admin, "fee_collection_summary", params)).text)))
    assert len(rows) - 1 == total == 4


READ_PATHS = ["collection-summary", "collection-summary/stats", "pending-fees", "pending-fees/stats", "fee-structure", "fee-structure/stats"]


@pytest.mark.tc("TC-FEE-15-A21")
@pytest.mark.parametrize("role", ROLES)
def test_report_read_matrix(role, role_clients, rep, year_id):
    expected = 200 if role in ("admin", "staff") else 403
    for path in READ_PATHS:
        r = role_clients[role].get(f"{RP}/{path}", params=q(rep, year_id))
        assert r.status_code == expected, path


@pytest.mark.tc("TC-FEE-15-A22")
@pytest.mark.parametrize("role", ROLES)
def test_report_export_matrix(role, role_clients, rep, year_id):
    r = export(role_clients[role], "fee_collection_summary", q(rep, year_id))
    assert r.status_code == (200 if role in ("admin", "staff") else 403)


@pytest.mark.tc("TC-FEE-15-A23")
def test_report_no_token_header_isolation(anon, mismatched_admin, tenant_b, rep, year_id):
    for path in READ_PATHS:
        assert anon.get(f"{RP}/{path}", params=q(rep, year_id)).status_code == 401, path
    assert export(anon, "fee_collection_summary", q(rep, year_id)).status_code == 401
    assert mismatched_admin.get(f"{RP}/collection-summary", params=q(rep, year_id)).status_code == 403
    for path in ("collection-summary", "pending-fees", "fee-structure"):
        body = tenant_b.get(f"{RP}/{path}", params={"fee_type_id": rep["type"]["id"]}).json()
        assert body["total_count"] == 0 and body["data"] == []
    stats = tenant_b.get(f"{RP}/collection-summary/stats", params={"fee_type_id": rep["type"]["id"]}).json()
    assert stats["total_collected"] == 0
