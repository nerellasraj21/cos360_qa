import csv
import io
from datetime import date
from decimal import Decimal

import pytest

from api_tests.reports.helpers import ROLES, fresh_year, other_tenant_header
from api_tests.support import Cleanup, unique

SUMMARY = "/reports/financial/summary"
EXPENDITURE = "/reports/financial/expenditure"
LEDGER = "/reports/financial/ledger"
EXPORT = "/reports/financial/export"
EXPENSE_REPORT = "/expense/reports/by-category"


def _txn(admin, stack, type_id, amount, day, **over):
    body = {
        "expense_type_id": type_id,
        "amount": amount,
        "transaction_date": day,
        "description": "qa financial",
        "payment_method": "cash",
        "vendor_name": "qa vendor",
        "idempotency_key": unique("rpt_idem_"),
    }
    body.update(over)
    response = admin.post("/expense/transactions/", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(scope="module")
def ledger(admin):
    stack = Cleanup()
    try:
        year = fresh_year()
        category = admin.post("/expense/categories/", json={"name": unique("rpt_cat_")})
        assert category.status_code == 201, category.text
        category = category.json()
        stack.delete_later(admin, f"/expense/categories/{category['id']}")
        electricity = admin.post(
            "/expense/types/", json={"name": unique("rpt_typ_a_"), "category_id": category["id"]}
        ).json()
        water = admin.post("/expense/types/", json={"name": unique("rpt_typ_b_"), "category_id": category["id"]}).json()
        department = admin.post("/expense/departments/", json={"name": unique("rpt_dep_")}).json()
        stack.delete_later(admin, f"/expense/departments/{department['id']}")
        pending = _txn(admin, stack, electricity["id"], "1000.00", date(year, 9, 10).isoformat(), department_id=department["id"])
        approved = _txn(
            admin, stack, water["id"], "500.00", date(year, 9, 12).isoformat(), requires_approval_override=True
        )
        rejected = _txn(
            admin, stack, water["id"], "700.00", date(year, 9, 14).isoformat(), requires_approval_override=True
        )
        assert admin.post(
            f"/expense/transactions/{approved['id']}/approval", json={"action": "approve", "approval_comment": "ok"}
        ).status_code == 200
        assert admin.post(
            f"/expense/transactions/{rejected['id']}/approval", json={"action": "reject", "approval_comment": "no"}
        ).status_code == 200
        yield {
            "year": year,
            "category": category,
            "electricity": electricity,
            "water": water,
            "department": department,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "range": {"date_from": date(year, 9, 1).isoformat(), "date_to": date(year, 9, 30).isoformat()},
        }
    finally:
        stack.run()


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A01")
def test_summary_for_month(admin, ledger):
    response = admin.get(SUMMARY, params={"month": 9, "year": ledger["year"]})
    assert response.status_code == 200, response.text
    data = response.json()["summary_data"]
    assert data["period"] == f"{ledger['year']}-09-01 to {ledger['year']}-09-30"
    assert Decimal(data["total_expenses"]) == Decimal("1500.00")
    assert Decimal(data["total_income"]) == Decimal("0.00")
    assert Decimal(data["net_balance"]) == Decimal("-1500.00")
    assert Decimal(data["fee_collections"]) == Decimal("0.00")
    assert Decimal(data["fee_pending"]) == 0
    assert {key: float(value) for key, value in data["expense_by_category"].items()} == {
        ledger["category"]["name"]: 1500.0
    }
    assert {key: float(value) for key, value in data["expense_by_type"].items()} == {
        ledger["electricity"]["name"]: 1000.0,
        ledger["water"]["name"]: 500.0,
    }
    body = response.json()
    for key in ("income_breakdown", "expense_breakdown", "budget_comparison", "cash_flow_trends"):
        assert body[key] == []


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A02")
def test_summary_for_date_range(admin, ledger):
    params = {"date_from": date(ledger["year"], 9, 1).isoformat(), "date_to": date(ledger["year"], 9, 10).isoformat()}
    data = admin.get(SUMMARY, params=params).json()["summary_data"]
    assert Decimal(data["total_expenses"]) == Decimal("1000.00")
    assert Decimal(data["total_income"]) == Decimal("0.00")


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A02")
def test_summary_include_flags(admin, ledger):
    params = {"month": 9, "year": ledger["year"]}
    no_expenses = admin.get(SUMMARY, params={**params, "include_expenses": "false"}).json()["summary_data"]
    assert Decimal(no_expenses["total_expenses"]) == 0 and no_expenses["expense_by_category"] == {}
    no_fees = admin.get(SUMMARY, params={**params, "include_fees": "false"}).json()["summary_data"]
    assert Decimal(no_fees["total_income"]) == 0 and Decimal(no_fees["total_expenses"]) == Decimal("1500.00")


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A03")
@pytest.mark.parametrize("params", [{"period_type": "weekly"}, {"month": 13}])
def test_summary_validation(admin, params):
    assert admin.get(SUMMARY, params=params).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A04")
def test_expenditure_lists_every_status(admin, ledger):
    response = admin.get(EXPENDITURE, params={**ledger["range"], "sort_order": "desc"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] == 3
    amounts = [Decimal(str(row["amount"])) for row in body["data"]]
    assert sorted(amounts) == [Decimal("500.00"), Decimal("700.00"), Decimal("1000.00")]
    for row in body["data"]:
        assert set(row) >= {
            "sl_no",
            "transaction_id",
            "date",
            "category_name",
            "type_name",
            "description",
            "amount",
            "department",
            "approved_by",
            "approved_at",
            "receipt_number",
            "vendor_name",
            "created_at",
        }
        assert row["category_name"] == ledger["category"]["name"]
    assert sum(amounts) == Decimal("2200.00")


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A05")
def test_expenditure_filters(admin, ledger):
    base = ledger["range"]
    by_type = admin.get(EXPENDITURE, params={**base, "type_id": ledger["water"]["id"]}).json()
    assert by_type["total_count"] == 2
    by_category = admin.get(EXPENDITURE, params={**base, "category_id": ledger["category"]["id"]}).json()
    assert by_category["total_count"] == 3
    ranged = admin.get(EXPENDITURE, params={**base, "amount_min": 600, "amount_max": 1000}).json()
    assert sorted(Decimal(str(row["amount"])) for row in ranged["data"]) == [Decimal("700.00"), Decimal("1000.00")]
    by_department = admin.get(EXPENDITURE, params={**base, "department": ledger["department"]["id"]}).json()
    assert by_department["total_count"] == 1
    by_month = admin.get(EXPENDITURE, params={"month": 9, "year": ledger["year"]}).json()
    assert by_month["total_count"] == 3
    ignored = admin.get(EXPENDITURE, params={**base, "department": "not-a-uuid"}).json()
    assert ignored["total_count"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A06")
def test_expenditure_department_name(admin, ledger):
    rows = admin.get(EXPENDITURE, params={**ledger["range"], "department": ledger["department"]["id"]}).json()["data"]
    assert rows[0]["department"] == ledger["department"]["name"]


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A06")
@pytest.mark.skip(reason="needs an expense whose department row no longer exists; departments can only be deactivated, never removed")
def test_expenditure_missing_department_shows_raw_id():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A07")
def test_expenditure_pagination(admin, ledger):
    body = admin.get(EXPENDITURE, params={**ledger["range"], "page": 2, "page_size": 2}).json()
    assert [row["sl_no"] for row in body["data"]] == [3]
    assert body["total_pages"] == 2


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A08")
def test_ledger_rows(admin, ledger):
    response = admin.get(LEDGER, params=ledger["range"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] == 2
    for row in body["data"]:
        assert row["account_type"] == "Expense" and row["transaction_type"] == "Debit"
        assert row["reference_type"] == "Expense Payment"
        assert set(row) >= {"sl_no", "transaction_id", "date", "reference_id", "amount", "balance", "description", "created_at"}
    assert sorted(Decimal(str(row["amount"])) for row in body["data"]) == [Decimal("500.00"), Decimal("1000.00")]
    ids = {row["transaction_id"] for row in body["data"]}
    assert ledger["rejected"]["id"] not in ids


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A09")
def test_ledger_filters(admin, ledger):
    base = ledger["range"]
    income = admin.get(LEDGER, params={**base, "account_type": "Income"}).json()
    assert income["total_count"] == 0
    debit = admin.get(LEDGER, params={**base, "transaction_type": "Debit"}).json()
    assert debit["total_count"] == 2
    ignored = admin.get(LEDGER, params={**base, "reference_type": "Fee Payment"}).json()
    assert ignored["total_count"] == 2


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A10")
def test_ledger_running_balance_per_page(admin, ledger):
    first = admin.get(LEDGER, params={**ledger["range"], "page_size": 1, "page": 1}).json()["data"][0]
    second = admin.get(LEDGER, params={**ledger["range"], "page_size": 1, "page": 2}).json()["data"][0]
    assert Decimal(str(first["balance"])) == -Decimal(str(first["amount"]))
    assert Decimal(str(second["balance"])) == -Decimal(str(second["amount"]))
    both = admin.get(LEDGER, params=ledger["range"]).json()["data"]
    assert Decimal(str(both[1]["balance"])) == -(Decimal(str(both[0]["amount"])) + Decimal(str(both[1]["amount"])))


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A11")
@pytest.mark.parametrize("report_type,rows", [("expenditure", 3), ("ledger", 2)])
def test_exports(admin, ledger, report_type, rows):
    filters = {**ledger["range"], "page_size": 1}
    csv_response = admin.post(EXPORT, json={"report_type": report_type, "filters": filters, "format": "csv"})
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert len(list(csv.DictReader(io.StringIO(csv_response.text)))) == rows
    xlsx = admin.post(EXPORT, json={"report_type": report_type, "filters": filters, "format": "xlsx"})
    assert xlsx.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(xlsx.content) > 0
    pdf = admin.post(EXPORT, json={"report_type": report_type, "filters": filters, "format": "pdf"})
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A12")
def test_export_summary_unsupported(admin):
    response = admin.post(EXPORT, json={"report_type": "summary", "filters": {}, "format": "csv"})
    assert response.status_code == 400 and "Unsupported financial report type" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A13")
@pytest.mark.parametrize("role", ROLES)
def test_read_role_matrix(role_clients, ledger, role):
    expected = 200 if role == "admin" else 403
    client = role_clients[role]
    assert client.get(SUMMARY, params={"month": 9, "year": ledger["year"]}).status_code == expected
    assert client.get(EXPENDITURE, params=ledger["range"]).status_code == expected
    assert client.get(LEDGER, params=ledger["range"]).status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A14")
@pytest.mark.parametrize("role", ROLES)
def test_export_role_matrix(role_clients, ledger, role):
    expected = 200 if role == "admin" else 403
    response = role_clients[role].post(
        EXPORT, json={"report_type": "ledger", "filters": ledger["range"], "format": "csv"}
    )
    assert response.status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A13")
def test_unauthenticated(anon):
    assert anon.get(SUMMARY).status_code == 401
    assert anon.get(LEDGER).status_code == 401
    assert anon.post(EXPORT, json={"report_type": "ledger", "filters": {}, "format": "csv"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-RPT-08-A15")
def test_tenant_isolation(admin, tenant_b, ledger):
    data = tenant_b.get(SUMMARY, params={"month": 9, "year": ledger["year"]}).json()["summary_data"]
    assert Decimal(data["total_expenses"]) == 0 and data["expense_by_category"] == {}
    assert tenant_b.get(EXPENDITURE, params=ledger["range"]).json()["total_count"] == 0
    assert tenant_b.get(LEDGER, params=ledger["range"]).json()["total_count"] == 0
    assert other_tenant_header(admin).get(SUMMARY).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-RPT-09-A01")
def test_expense_report_counts_every_status(admin, ledger):
    params = {
        "start_date": ledger["range"]["date_from"],
        "end_date": ledger["range"]["date_to"],
        "category_ids": [ledger["category"]["id"]],
    }
    body = admin.get(EXPENSE_REPORT, params=params).json()
    assert [Decimal(row["total_amount"]) for row in body["categories"]] == [Decimal("2200.00")]
    assert body["categories"][0]["transaction_count"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-RPT-09-A02")
def test_financial_summary_excludes_rejected(admin, ledger):
    data = admin.get(SUMMARY, params={"month": 9, "year": ledger["year"]}).json()["summary_data"]
    assert Decimal(data["total_expenses"]) == Decimal("1500.00")


@pytest.mark.api
@pytest.mark.tc("TC-RPT-09-A03")
def test_expenditure_total_matches_expense_report(admin, ledger):
    rows = admin.get(EXPENDITURE, params=ledger["range"]).json()["data"]
    assert sum(Decimal(str(row["amount"])) for row in rows) == Decimal("2200.00")


@pytest.mark.api
@pytest.mark.tc("TC-RPT-09-A04")
@pytest.mark.parametrize("role", ["admin", "staff"])
def test_expense_report_access(role_clients, role):
    expected = 200 if role == "admin" else 403
    assert role_clients[role].get(EXPENSE_REPORT).status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-RPT-09-A03")
def test_difference_between_reports(admin, ledger):
    expense_total = sum(
        Decimal(str(row["amount"])) for row in admin.get(EXPENDITURE, params=ledger["range"]).json()["data"]
    )
    summary = admin.get(SUMMARY, params={"month": 9, "year": ledger["year"]}).json()["summary_data"]
    assert expense_total - Decimal(summary["total_expenses"]) == Decimal("700.00")
