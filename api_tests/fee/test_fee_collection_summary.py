import uuid
from datetime import date, timedelta

import pytest

from api_tests.fee import helpers as h
from api_tests.support import items_of

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
C = "/fee/collection"


def rid():
    return str(uuid.uuid4())


def search(admin, **params):
    return admin.get(f"{C}/search-student", params=params)


@pytest.mark.tc("TC-FEE-09-A01")
def test_search_by_admission_number(admin, fee_world, w1):
    s = w1["student"]
    rows = items_of(h.ok(search(admin, q=s["admission_number"], class_id=fee_world["class"]["id"], section_id=s["section_id"])))
    mine = [r for r in rows if r["student_id"] == s["id"]]
    assert len(mine) == 1
    row = mine[0]
    assert row["admission_number"] == s["admission_number"]
    assert row["first_name"] == s["first_name"] and row["last_name"] == "Tester"
    assert row["class_id"] == fee_world["class"]["id"] and row["section_id"] == s["section_id"]
    assert row["class_name"] == fee_world["class"]["name"]
    assert s["father_phone"] in row["mobile_number"]
    assert "Father" in row["parent_name"] and "Mother" in row["parent_name"]
    assert set(row) >= {"student_id", "admission_number", "first_name", "last_name", "class_id", "class_name", "section_id", "section_name", "parent_name", "mobile_number", "photo_url"}


@pytest.mark.tc("TC-FEE-09-A02")
def test_search_by_name_mobile_city_address(admin, fee_world, new_student):
    s = new_student()
    cid = fee_world["class"]["id"]
    for q in (s["first_name"][:8], s["father_phone"], s["city"], s["address_line1"][:14]):
        rows = items_of(h.ok(search(admin, q=q, class_id=cid)))
        assert s["id"] in {r["student_id"] for r in rows}, q


@pytest.mark.tc("TC-FEE-09-A03")
def test_search_by_class_and_section(admin, cleanup, year_id):
    cls = h.make_class(admin, cleanup, year_id, sections=("A", "B"))
    names = sorted(cls["sections"])
    a1 = h.make_student(admin, cleanup, year_id, cls, names[0])
    a2 = h.make_student(admin, cleanup, year_id, cls, names[0])
    b1 = h.make_student(admin, cleanup, year_id, cls, names[1])
    rows = items_of(h.ok(search(admin, class_id=cls["id"], section_id=cls["sections"][names[0]])))
    assert {r["student_id"] for r in rows} == {a1["id"], a2["id"]}
    both = items_of(h.ok(search(admin, class_id=cls["id"])))
    assert {r["student_id"] for r in both} == {a1["id"], a2["id"], b1["id"]}
    assert len(both) <= 20


@pytest.mark.tc("TC-FEE-09-A04")
def test_search_short_query(admin):
    assert search(admin, q="a").status_code == 422


@pytest.mark.tc("TC-FEE-09-A05")
def test_search_without_parameters(admin):
    r = search(admin)
    assert r.status_code == 400
    assert "At least one search parameter is required" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-09-A06")
def test_summary_w2(admin, w2, year_id):
    data = h.ok(h.summary(admin, w2["student"], year_id)).json()
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["fee_type_id"] == w2["tuition"]["id"] and item["s_no"] == 1
    assert item["assigned_fee"] == "12000.00"
    assert item["fee_after_concession"] == "10000.00"
    assert item["paid_amount"] == "4000.00"
    assert item["due_amount"] == "6000.00"
    assert item["last_receipt_number"] and item["last_paid_date"]
    assert data["grand_total_assigned"] == "12000.00"
    assert data["grand_total_fee"] == "10000.00"
    assert data["grand_total_paid"] == "4000.00"
    assert data["grand_total_due"] == "6000.00"
    assert data["student_id"] == w2["student"]["id"]
    assert data["admission_number"] == w2["student"]["admission_number"]
    assert data["as_of_date"] == date.today().isoformat()


@pytest.mark.tc("TC-FEE-09-A06")
def test_summary_w1_and_w3_overpayment_clamp(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    lab = fee_world["lab"]["id"]
    h.map_student(admin, cleanup, year_id, s, lab, "3000.00")
    assert h.summary_item(admin, s, year_id, lab)["due_amount"] == "3000.00"
    h.ok(
        admin.post(
            "/fee/concessions/bulk",
            json={
                "student_id": s["id"],
                "academic_year_id": year_id,
                "concessions": [{"fee_type_id": lab, "concession_amount": "1000.00", "reason": "Merit award", "approved_by": "owner"}],
            },
        )
    )
    h.ok(h.pay(admin, s, year_id, "2000.00", [(lab, "2000.00")]))
    h.ok(
        admin.post(
            "/fee/concessions/bulk",
            json={
                "student_id": s["id"],
                "academic_year_id": year_id,
                "concessions": [{"fee_type_id": lab, "concession_amount": "1000.00", "reason": "Second award", "approved_by": "owner"}],
            },
        )
    )
    item = h.summary_item(admin, s, year_id, lab)
    assert item["fee_after_concession"] == "1000.00"
    assert item["paid_amount"] == "2000.00"
    assert item["due_amount"] == "0.00"


@pytest.mark.tc("TC-FEE-09-A07")
def test_summary_as_of_before_payment(admin, w2, year_id):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    item = h.summary_item(admin, w2["student"], year_id, w2["tuition"]["id"], as_of_date=yesterday)
    assert h.D(item["paid_amount"]) == 0
    assert item["last_paid_date"] is None
    assert item["assigned_fee"] == "12000.00"
    assert item["fee_after_concession"] == "10000.00"
    today = h.summary_item(admin, w2["student"], year_id, w2["tuition"]["id"], as_of_date=date.today().isoformat())
    assert today["paid_amount"] == "4000.00"


@pytest.mark.tc("TC-FEE-09-A08")
def test_summary_requires_year(admin, w1):
    assert admin.get(f"{C}/summary/{w1['student']['id']}").status_code == 422


@pytest.mark.tc("TC-FEE-09-A09")
def test_summary_unknown_student(admin, year_id):
    r = admin.get(f"{C}/summary/{rid()}", params={"academic_year_id": year_id})
    assert r.status_code == 404
    assert "Student not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-09-A10")
def test_summary_without_mappings(admin, year_id, new_student):
    data = h.ok(h.summary(admin, new_student(), year_id)).json()
    assert data["items"] == []
    for key in ("grand_total_assigned", "grand_total_fee", "grand_total_paid", "grand_total_due", "old_fee_pending_amount"):
        assert isinstance(data[key], str) and h.D(data[key]) == 0


@pytest.mark.tc("TC-FEE-09-A11")
def test_summary_old_fee_pending(admin, cleanup, year_id, new_student):
    s = new_student()
    r = h.ok(
        admin.post(
            "/fee/old-fees/",
            json={"student_id": s["id"], "academic_year_label": "2024-25", "fee_type_name": "Tuition Fee", "original_amount": "1500.00", "paid_amount": "600.00"},
        ),
        201,
    )
    cleanup.delete_later(admin, f"/fee/old-fees/{r.json()['id']}")
    data = h.ok(h.summary(admin, s, year_id)).json()
    assert isinstance(data["old_fee_pending_amount"], str)
    assert h.D(data["old_fee_pending_amount"]) == h.D("900.00")


def terms_due(admin, student, year_id, as_of):
    return admin.get(f"{C}/terms-due/{student['id']}", params={"academic_year_id": year_id, "as_of_date": as_of})


@pytest.mark.tc("TC-FEE-09-A12")
def test_terms_due_w8(admin, w1, year_id, fee_world):
    t = w1["tuition"]["id"]
    h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")]))
    data = h.ok(terms_due(admin, w1["student"], year_id, "2026-09-15")).json()
    assert data["selected_month"] == "September 2026"
    assert [x["due_date"] for x in data["current_month_terms"]] == ["2026-09-10"]
    assert data["overdue_terms"] == []
    cur = data["current_month_terms"][0]
    assert cur["term_amount"] == "3000.00" and h.D(cur["pending_amount"]) == h.D("3000")
    assert cur["fee_type_id"] == t and cur["term_date_id"] == fee_world["q4_dates"][1]["id"]
    assert h.D(data["total_current_month_pending"]) == 3000
    assert h.D(data["total_overdue_pending"]) == 0
    assert h.D(data["grand_total_pending"]) == 3000


@pytest.mark.tc("TC-FEE-09-A12")
def test_terms_due_partial_first_term_goes_overdue(admin, w1, year_id):
    t = w1["tuition"]["id"]
    h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")]))
    data = h.ok(terms_due(admin, w1["student"], year_id, "2026-09-15")).json()
    assert [(x["due_date"], h.D(x["pending_amount"])) for x in data["overdue_terms"]] == [("2026-06-10", 2000)]
    assert [(x["due_date"], h.D(x["pending_amount"])) for x in data["current_month_terms"]] == [("2026-09-10", 3000)]
    assert h.D(data["grand_total_pending"]) == 5000


@pytest.mark.tc("TC-FEE-09-A12")
def test_terms_due_ignores_concession(admin, w2, year_id):
    data = h.ok(terms_due(admin, w2["student"], year_id, "2026-09-15")).json()
    assert data["overdue_terms"] == []
    assert [(x["due_date"], h.D(x["pending_amount"])) for x in data["current_month_terms"]] == [("2026-09-10", 2000)]


@pytest.mark.tc("TC-FEE-09-A12")
def test_terms_due_on_first_due_date_is_current_month(admin, w1, year_id):
    data = h.ok(terms_due(admin, w1["student"], year_id, "2026-06-10")).json()
    assert [x["due_date"] for x in data["current_month_terms"]] == ["2026-06-10"]
    assert data["selected_month"] == "June 2026"


@pytest.mark.tc("TC-FEE-09-A13")
def test_terms_due_requires_as_of_date(admin, w1, year_id):
    assert admin.get(f"{C}/terms-due/{w1['student']['id']}", params={"academic_year_id": year_id}).status_code == 422


@pytest.mark.tc("TC-FEE-09-A14")
def test_pending_cheque_not_counted(admin, w1, year_id):
    t = w1["tuition"]["id"]
    h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")], method="cheque", cheque_number="CHQ1", cheque_bank="Test Bank", cheque_date=date.today().isoformat()))
    data = h.ok(terms_due(admin, w1["student"], year_id, "2026-09-15")).json()
    assert [(x["due_date"], h.D(x["pending_amount"])) for x in data["overdue_terms"]] == [("2026-06-10", 3000)]
    assert h.summary_item(admin, w1["student"], year_id, t)["due_amount"] == "12000.00"


@pytest.mark.tc("TC-FEE-09-A15")
def test_history(admin, w1, year_id):
    t = w1["tuition"]["id"]
    a = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")])).json()
    b = h.ok(h.pay(admin, w1["student"], year_id, "2000.00", [(t, "2000.00")])).json()
    h.ok(h.pay(admin, w1["student"], year_id, "500.00", [(t, "500.00")], method="cheque", cheque_number="CHQ2", cheque_bank="Test Bank", cheque_date=date.today().isoformat()))
    data = h.ok(admin.get(f"{C}/history/{w1['student']['id']}", params={"academic_year_id": year_id})).json()
    assert [i["transaction_id"] for i in data["items"]] == [b["transaction_id"], a["transaction_id"]]
    assert data["total_paid"] == "3000.00"
    first = data["items"][0]
    assert first["receipt_id"] == b["receipt_id"] and first["receipt_number"] == b["receipt_number"]
    assert first["status"] == "completed" and first["payment_method"] == "cash"
    assert [(x["fee_type_id"], x["amount_paid"]) for x in first["fee_types_paid"]] == [(t, "2000.00")]


@pytest.mark.tc("TC-FEE-09-A16")
def test_history_without_receipt(admin, w1, year_id):
    t = w1["tuition"]["id"]
    ch = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")], method="cheque", cheque_number="CHQ3", cheque_bank="Test Bank", cheque_date=date.today().isoformat())).json()
    h.ok(admin.put(f"/fee/transactions/{ch['transaction_id']}", json={"status": "completed", "cheque_status": "cleared"}))
    data = h.ok(admin.get(f"{C}/history/{w1['student']['id']}", params={"academic_year_id": year_id})).json()
    assert len(data["items"]) == 1
    assert data["items"][0]["receipt_id"] is None and data["items"][0]["receipt_number"] is None


@pytest.mark.tc("TC-FEE-09-A17")
@pytest.mark.parametrize("role", ROLES)
def test_collection_read_matrix(role, role_clients, w1, fee_world, year_id):
    client = role_clients[role]
    expected = 200 if role == "admin" else 403
    sid = w1["student"]["id"]
    assert client.get(f"{C}/search-student", params={"q": w1["student"]["admission_number"], "class_id": fee_world["class"]["id"]}).status_code == expected
    assert client.get(f"{C}/summary/{sid}", params={"academic_year_id": year_id}).status_code == expected
    assert client.get(f"{C}/terms-due/{sid}", params={"academic_year_id": year_id, "as_of_date": "2026-09-15"}).status_code == expected
    assert client.get(f"{C}/history/{sid}", params={"academic_year_id": year_id}).status_code == expected


@pytest.mark.tc("TC-FEE-09-A18")
def test_parent_cannot_read_staff_summary(parent, w1, year_id):
    r = parent.get(f"{C}/summary/{w1['student']['id']}", params={"academic_year_id": year_id})
    assert r.status_code == 403


@pytest.mark.tc("TC-FEE-09-A19")
def test_summary_tenant_isolation(tenant_b, mismatched_admin, w1, year_id):
    r = tenant_b.get(f"{C}/summary/{w1['student']['id']}", params={"academic_year_id": tenant_b.academic_year_id})
    assert r.status_code == 404
    assert "Student not found" in h.detail_text(r)
    r = mismatched_admin.get(f"{C}/summary/{w1['student']['id']}", params={"academic_year_id": year_id})
    assert r.status_code == 403


@pytest.mark.tc("TC-FEE-09-A20")
def test_collection_reads_without_token(anon, w1, year_id):
    sid = w1["student"]["id"]
    assert anon.get(f"{C}/search-student", params={"q": "ab"}).status_code == 401
    assert anon.get(f"{C}/summary/{sid}", params={"academic_year_id": year_id}).status_code == 401
    assert anon.get(f"{C}/terms-due/{sid}", params={"academic_year_id": year_id, "as_of_date": "2026-09-15"}).status_code == 401
    assert anon.get(f"{C}/history/{sid}", params={"academic_year_id": year_id}).status_code == 401
