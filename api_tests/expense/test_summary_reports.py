import uuid
from decimal import Decimal

import pytest

from api_tests.expense.helpers import (
    ROLES,
    Window,
    forbidden_roles,
    make_category,
    make_department,
    make_txn,
    make_type,
    other_tenant_header,
)
from api_tests.support import unique

SUMMARY = "/expense/summary/"
REPORTS = "/expense/reports/"


@pytest.fixture
def world(admin, cleanup):
    window = Window()
    utilities = make_category(admin, cleanup, name=unique("exp_cat_a_"))
    infra = make_category(admin, cleanup, name=unique("exp_cat_b_"))
    electricity = make_type(admin, cleanup, utilities["id"], name=unique("exp_typ_a_"))
    water = make_type(admin, cleanup, utilities["id"], name=unique("exp_typ_b_"))
    repairs = make_type(admin, cleanup, infra["id"], name=unique("exp_typ_c_"))
    approved = make_txn(admin, cleanup, electricity["id"], "1200.00", window.day(8, 15))
    assert admin.post(
        f"/expense/transactions/{approved['id']}/approval", json={"action": "approve", "approval_comment": "ok"}
    ).status_code == 200
    pending_a = make_txn(admin, cleanup, electricity["id"], "300.50", window.day(8, 20))
    pending_b = make_txn(admin, cleanup, water["id"], "150.25", window.day(9, 5))
    rejected = make_txn(admin, cleanup, repairs["id"], "5000.00", window.day(9, 10))
    assert admin.post(
        f"/expense/transactions/{rejected['id']}/approval", json={"action": "reject", "approval_comment": "no"}
    ).status_code == 200
    return {
        "window": window,
        "utilities": utilities,
        "infra": infra,
        "electricity": electricity,
        "water": water,
        "repairs": repairs,
        "approved": approved,
        "pending_a": pending_a,
        "pending_b": pending_b,
        "rejected": rejected,
    }


def _category(body, category_id):
    return next(row for row in body["categories"] if row["category_id"] == category_id)


def _type(category_row, type_id):
    return next(row for row in category_row["types"] if row["type_id"] == type_id)


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A01")
def test_summary_totals(admin, world):
    response = admin.get(SUMMARY, params=world["window"].params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["grand_total"]) == Decimal("6650.75")
    assert body["total_entries"] == 4
    utilities = _category(body, world["utilities"]["id"])
    infra = _category(body, world["infra"]["id"])
    assert Decimal(utilities["category_total"]) == Decimal("1650.75") and utilities["entry_count"] == 3
    assert Decimal(infra["category_total"]) == Decimal("5000.00") and infra["entry_count"] == 1
    electricity = _type(utilities, world["electricity"]["id"])
    water = _type(utilities, world["water"]["id"])
    assert Decimal(electricity["type_total"]) == Decimal("1500.50") and electricity["entry_count"] == 2
    assert Decimal(water["type_total"]) == Decimal("150.25")
    dates = [entry["transaction_date"] for entry in electricity["entries"]]
    assert dates == sorted(dates, reverse=True)
    entry = electricity["entries"][0]
    assert set(entry) >= {
        "id",
        "amount",
        "description",
        "transaction_date",
        "payment_method",
        "vendor_name",
        "status",
        "reference_number",
    }
    assert isinstance(entry["amount"], str)
    names = [row["category_name"] for row in body["categories"]]
    assert names == sorted(names)
    assert body["start_date"] == world["window"].start and body["end_date"] == world["window"].end


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A02")
def test_summary_status_filter(admin, world):
    approved = admin.get(SUMMARY, params={**world["window"].params, "status_filter": "approved"}).json()
    assert Decimal(approved["grand_total"]) == Decimal("1200.00")
    pending = admin.get(SUMMARY, params={**world["window"].params, "status_filter": "pending"}).json()
    assert Decimal(pending["grand_total"]) == Decimal("450.75")
    rejected = admin.get(SUMMARY, params={**world["window"].params, "status_filter": "rejected"}).json()
    assert Decimal(rejected["grand_total"]) == Decimal("5000.00")


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A03")
def test_summary_date_range(admin, world):
    window = world["window"]
    september = admin.get(SUMMARY, params={"start_date": window.day(9, 1), "end_date": window.day(9, 30)}).json()
    assert Decimal(september["grand_total"]) == Decimal("5150.25")
    boundary = admin.get(SUMMARY, params={"start_date": window.start, "end_date": window.day(8, 15)}).json()
    assert Decimal(boundary["grand_total"]) == Decimal("1200.00")


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A04")
def test_summary_academic_year_without_matches(admin, world, academic_year_id):
    response = admin.get(SUMMARY, params={**world["window"].params, "academic_year_id": academic_year_id})
    assert response.status_code == 200
    body = response.json()
    assert body["academic_year_title"]
    assert Decimal(body["grand_total"]) == Decimal("0")
    assert body["total_entries"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A05")
def test_summary_unknown_academic_year(admin):
    response = admin.get(SUMMARY, params={"academic_year_id": str(uuid.uuid4())})
    assert response.status_code == 200
    assert response.json()["academic_year_title"] is None


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A06")
def test_summary_filters_by_academic_year(admin, cleanup, academic_year_id):
    window = Window()
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    with_year = make_txn(admin, cleanup, expense_type["id"], "40.00", window.day(3, 3), academic_year_id=academic_year_id)
    make_txn(admin, cleanup, expense_type["id"], "60.00", window.day(3, 4))
    both = admin.get(SUMMARY, params=window.params).json()
    assert Decimal(both["grand_total"]) == Decimal("100.00")
    scoped = admin.get(SUMMARY, params={**window.params, "academic_year_id": academic_year_id}).json()
    assert Decimal(scoped["grand_total"]) == Decimal("40.00")
    entries = _category(scoped, category["id"])["types"][0]["entries"]
    assert [entry["id"] for entry in entries] == [with_year["id"]]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A07")
def test_summary_excludes_inactive_type(admin, world):
    admin.put(f"/expense/types/{world['water']['id']}", json={"is_active": False})
    body = admin.get(SUMMARY, params=world["window"].params).json()
    assert Decimal(body["grand_total"]) == Decimal("6500.50")
    utilities = _category(body, world["utilities"]["id"])
    assert world["water"]["id"] not in [row["type_id"] for row in utilities["types"]]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A08")
def test_summary_malformed_date(admin):
    assert admin.get(SUMMARY, params={"start_date": "2026-13-45"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A09")
@pytest.mark.parametrize("role", ROLES)
def test_summary_role_matrix(role_clients, role):
    expected = 200 if role in ("admin", "staff") else 403
    assert role_clients[role].get(SUMMARY).status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A10")
def test_summary_tenant_isolation(admin, tenant_b, world):
    body = tenant_b.get(SUMMARY, params=world["window"].params).json()
    assert body["categories"] == []
    assert Decimal(body["grand_total"]) == Decimal("0")
    assert other_tenant_header(admin).get(SUMMARY).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXP-13-A09")
def test_summary_unauthenticated(anon):
    assert anon.get(SUMMARY).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A01")
def test_report_by_category(admin, world):
    params = {**world["window"].params, "category_ids": [world["utilities"]["id"], world["infra"]["id"]]}
    response = admin.get(f"{REPORTS}by-category", params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["category_id"] for row in body["categories"]] == [world["infra"]["id"], world["utilities"]["id"]]
    infra, utilities = body["categories"]
    assert Decimal(infra["total_amount"]) == Decimal("5000.00") and infra["transaction_count"] == 1
    assert Decimal(utilities["total_amount"]) == Decimal("1650.75") and utilities["transaction_count"] == 3
    assert round(Decimal(utilities["average_amount"]), 2) == Decimal("550.25")
    assert body["summary"]["total_transactions"] == 4
    assert body["generated_by"]
    assert body["generated_at"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A01")
def test_report_by_category_summary_total_and_percentages(admin, world):
    params = {**world["window"].params, "category_ids": [world["utilities"]["id"], world["infra"]["id"]]}
    body = admin.get(f"{REPORTS}by-category", params=params).json()
    infra, utilities = body["categories"]
    assert Decimal(body["summary"]["total_amount"]) == Decimal("6650.75")
    assert Decimal(infra["percentage_of_total"]) == Decimal("75.18")
    assert Decimal(utilities["percentage_of_total"]) == Decimal("24.82")
    assert Decimal(body["summary"]["average_transaction"]) == Decimal("1662.69")


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A02")
def test_report_by_type(admin, world):
    params = {**world["window"].params, "type_ids": [world["repairs"]["id"], world["electricity"]["id"], world["water"]["id"]]}
    body = admin.get(f"{REPORTS}by-type", params=params).json()
    rows = {row["type_id"]: row for row in body["types"]}
    assert Decimal(rows[world["repairs"]["id"]]["total_amount"]) == Decimal("5000.00")
    assert Decimal(rows[world["electricity"]["id"]]["total_amount"]) == Decimal("1500.50")
    assert rows[world["electricity"]["id"]]["transaction_count"] == 2
    assert Decimal(rows[world["water"]["id"]]["total_amount"]) == Decimal("150.25")
    assert rows[world["water"]["id"]]["category_name"] == world["utilities"]["name"]
    totals = [Decimal(row["total_amount"]) for row in body["types"]]
    assert totals == sorted(totals, reverse=True)


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A03")
def test_report_trend_totals(admin, world):
    body = admin.get(f"{REPORTS}trend", params=world["window"].params).json()
    trends = body["monthly_trends"]
    assert len(trends) == 2
    assert [row["transaction_count"] for row in trends] == [2, 2]
    assert [Decimal(row["total_amount"]) for row in trends] == [Decimal("1500.50"), Decimal("5150.25")]
    assert round(Decimal(trends[0]["average_per_transaction"]), 2) == Decimal("750.25")
    assert Decimal(body["summary"]["total_amount"]) == Decimal("6650.75")
    assert all(len(row["month"]) == 7 for row in trends)


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A03")
def test_report_trend_month_labels(admin, world):
    body = admin.get(f"{REPORTS}trend", params=world["window"].params).json()
    year = world["window"].year
    assert [row["month"] for row in body["monthly_trends"]] == [f"{year}-08", f"{year}-09"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A04")
def test_report_date_range(admin, world):
    window = world["window"]
    params = {"start_date": window.day(9, 1), "end_date": window.day(9, 30), "category_ids": [world["utilities"]["id"], world["infra"]["id"]]}
    body = admin.get(f"{REPORTS}by-category", params=params).json()
    rows = {row["category_id"]: row for row in body["categories"]}
    assert Decimal(rows[world["utilities"]["id"]]["total_amount"]) == Decimal("150.25")
    assert Decimal(rows[world["infra"]["id"]]["total_amount"]) == Decimal("5000.00")


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A05")
def test_report_status_filter(admin, world):
    params = {**world["window"].params, "status_filter": "approved"}
    body = admin.get(f"{REPORTS}by-category", params=params).json()
    assert [Decimal(row["total_amount"]) for row in body["categories"]] == [Decimal("1200.00")]
    assert body["summary"]["total_transactions"] == 1


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A06")
def test_report_amount_filters(admin, world):
    params = {**world["window"].params, "min_amount": "1000", "max_amount": "2000"}
    body = admin.get(f"{REPORTS}by-category", params=params).json()
    assert [Decimal(row["total_amount"]) for row in body["categories"]] == [Decimal("1200.00")]
    assert admin.get(f"{REPORTS}by-category", params={"min_amount": "-1"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A07")
def test_report_category_ids_filter(admin, world):
    body = admin.get(
        f"{REPORTS}by-category", params={**world["window"].params, "category_ids": [world["utilities"]["id"]]}
    ).json()
    assert [row["category_id"] for row in body["categories"]] == [world["utilities"]["id"]]
    missing = admin.get(f"{REPORTS}by-category", params={"category_ids": [str(uuid.uuid4())]})
    assert missing.status_code == 200 and missing.json()["categories"] == []


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A08")
def test_report_department_filter(admin, cleanup):
    window = Window()
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    department = make_department(admin, cleanup)
    make_txn(admin, cleanup, expense_type["id"], "70.00", window.day(5, 5), department_id=department["id"])
    make_txn(admin, cleanup, expense_type["id"], "30.00", window.day(5, 6))
    body = admin.get(f"{REPORTS}by-category", params={**window.params, "department_id": department["id"]}).json()
    assert [Decimal(row["total_amount"]) for row in body["categories"]] == [Decimal("70.00")]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A09")
def test_quick_summary(admin):
    response = admin.get(f"{REPORTS}summary", params={"period_days": 30})
    assert response.status_code == 200
    body = response.json()
    assert body["period_days"] == 30
    assert len(body["top_categories"]) <= 5
    for key in ("total_amount", "total_transactions", "average_transaction", "generated_at"):
        assert key in body


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A10")
@pytest.mark.parametrize("days", [0, 366])
def test_quick_summary_bounds(admin, days):
    assert admin.get(f"{REPORTS}summary", params={"period_days": days}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A11")
def test_reports_for_empty_window(admin):
    window = Window()
    body = admin.get(f"{REPORTS}by-category", params=window.params).json()
    assert body["categories"] == []
    assert body["summary"]["total_transactions"] == 0
    assert admin.get(f"{REPORTS}by-type", params=window.params).json()["types"] == []
    assert admin.get(f"{REPORTS}trend", params=window.params).json()["monthly_trends"] == []


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A12")
@pytest.mark.parametrize("fmt", ["csv", "excel", "pdf", "json"])
def test_export_is_a_stub(admin, fmt):
    response = admin.post(
        f"{REPORTS}export", json={"report_type": "category", "export_format": fmt, "filters": {}}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["export_id"] == "12345678-1234-5678-9012-123456789012"
    assert body["status"] == "pending"
    assert body["export_format"] == fmt
    assert body["file_url"] is None


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A13")
def test_export_invalid_format(admin):
    response = admin.post(
        f"{REPORTS}export", json={"report_type": "category", "export_format": "xlsx", "filters": {}}
    )
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A14")
def test_export_status_is_a_stub(admin):
    response = admin.get(f"{REPORTS}export/{uuid.uuid4()}/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["file_url"]
    download = admin.get(body["file_url"].replace("/api/v1", "", 1))
    assert download.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A15")
@pytest.mark.parametrize("role", ROLES)
def test_report_read_role_matrix(role_clients, role):
    expected = 200 if role == "admin" else 403
    client = role_clients[role]
    for path in ("by-category", "by-type", "trend", "summary"):
        assert client.get(f"{REPORTS}{path}").status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A16")
@pytest.mark.parametrize("role", ROLES)
def test_report_export_role_matrix(role_clients, role):
    expected = 200 if role == "admin" else 403
    response = role_clients[role].post(
        f"{REPORTS}export", json={"report_type": "category", "export_format": "csv", "filters": {}}
    )
    assert response.status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A15")
def test_report_unauthenticated(anon):
    assert anon.get(f"{REPORTS}by-category").status_code == 401
    assert anon.post(f"{REPORTS}export", json={"report_type": "c", "export_format": "csv", "filters": {}}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXP-14-A17")
def test_report_tenant_isolation(admin, tenant_b, world):
    window = world["window"]
    assert tenant_b.get(f"{REPORTS}by-category", params=window.params).json()["categories"] == []
    assert tenant_b.get(f"{REPORTS}by-type", params=window.params).json()["types"] == []
    assert tenant_b.get(f"{REPORTS}trend", params=window.params).json()["monthly_trends"] == []
    assert other_tenant_header(admin).get(f"{REPORTS}by-category").status_code == 403
    assert forbidden_roles(["admin"])
