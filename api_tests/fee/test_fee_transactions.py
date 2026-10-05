import uuid
from datetime import date, timedelta

import pytest

from api_tests.fee import helpers as h
from api_tests.support import items_of

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
T = "/fee/transactions"


def rid():
    return str(uuid.uuid4())


def tx_body(year_id, student, items, method="cash", total=None, **extra):
    total = total if total is not None else sum(h.D(i["amount_paid"]) for i in items)
    body = {
        "student_id": student["id"],
        "student_admission_num": student["admission_number"],
        "academic_year_id": year_id,
        "total_amount": str(total),
        "payment_method": method,
        "transaction_items": items,
    }
    body.update(extra)
    return body


def item(type_id, term_date_id, due="3000.00", paid="3000.00"):
    return {"fee_type_id": type_id, "term_date_id": term_date_id, "amount_due": due, "amount_paid": paid}


def cheque_fields(**over):
    base = {"cheque_number": "CHQ500", "cheque_bank": "Test Bank", "cheque_date": date.today().isoformat()}
    base.update(over)
    return base


@pytest.fixture
def ctx(w1, fee_world):
    return {"student": w1["student"], "type": w1["tuition"]["id"], "dates": fee_world["q4_dates"]}


def cash_txn(admin, ctx, year_id, amount="3000.00"):
    paid = h.ok(h.pay(admin, ctx["student"], year_id, amount, [(ctx["type"], amount)])).json()
    return h.ok(admin.get(f"{T}/{paid['transaction_id']}")).json()


def create_txn(admin, year_id, ctx, **kw):
    items = kw.pop("items", None) or [item(ctx["type"], ctx["dates"][0]["id"])]
    return admin.post(f"{T}/", json=tx_body(year_id, ctx["student"], items, **kw))


@pytest.mark.tc("TC-FEE-12-A01")
@pytest.mark.xfail(strict=True, reason="FEE-B09: POST /fee/transactions/ for a completed method (cash, upi, bank_transfer) returns 500 MissingGreenlet after the transaction and receipt were already committed")
def test_create_cash_transaction(admin, ctx, year_id):
    r = h.ok(create_txn(admin, year_id, ctx), 201)
    data = r.json()
    assert data["status"] == "completed" and data["payment_method"] == "cash"
    assert data["total_amount"] == "3000.00"
    assert data["receipt_number"] and data["receipt_generated"] is True
    assert [(i["amount_due"], i["amount_paid"]) for i in data["transaction_items"]] == [("3000.00", "3000.00")]


@pytest.mark.tc("TC-FEE-12-A01")
def test_create_cash_transaction_side_effects_persist_despite_500(admin, ctx, year_id):
    create_txn(admin, year_id, ctx)
    rows = items_of(h.ok(admin.get(f"{T}/", params={"student_id": ctx["student"]["id"]})))
    assert len(rows) == 1 and rows[0]["status"] == "completed" and rows[0]["payment_method"] == "cash"
    assert h.summary_item(admin, ctx["student"], year_id, ctx["type"])["paid_amount"] == "3000.00"


@pytest.mark.tc("TC-FEE-12-A02")
def test_create_cheque_transaction(admin, ctx, year_id):
    r = h.ok(create_txn(admin, year_id, ctx, method="cheque", **cheque_fields()), 201)
    data = r.json()
    assert data["status"] == "pending" and data["cheque_status"] == "pending"
    assert not data["receipt_number"] and data["receipt_generated"] is False
    assert h.summary_item(admin, ctx["student"], year_id, ctx["type"])["paid_amount"] in ("0", "0.00")


@pytest.mark.tc("TC-FEE-12-A02")
def test_summary_zero_paid_has_two_places(admin, ctx, year_id):
    assert h.summary_item(admin, ctx["student"], year_id, ctx["type"])["paid_amount"] == "0.00"


@pytest.mark.tc("TC-FEE-12-A03")
def test_create_method_field_validation(admin, ctx, year_id):
    assert create_txn(admin, year_id, ctx, method="upi").status_code == 422
    assert create_txn(admin, year_id, ctx, method="bank_transfer", bank_reference="UTR1").status_code == 422
    assert create_txn(admin, year_id, ctx, method="cheque", **cheque_fields(cheque_bank=None)).status_code == 422
    assert create_txn(admin, year_id, ctx, method="cheque", **cheque_fields(cheque_number=None)).status_code == 422


@pytest.mark.tc("TC-FEE-12-A03")
@pytest.mark.xfail(strict=True, reason="FEE-B09: POST /fee/transactions/ for upi and bank_transfer returns 500 MissingGreenlet after commit")
def test_create_upi_and_bank_transfer_transactions(admin, ctx, year_id):
    upi = h.ok(create_txn(admin, year_id, ctx, method="upi", upi_reference="UPI-REF-1"), 201)
    assert upi.json()["upi_reference"] == "UPI-REF-1"
    r = h.ok(create_txn(admin, year_id, ctx, method="bank_transfer", bank_reference="UTR-9", bank_name="Test Bank", items=[item(ctx["type"], ctx["dates"][1]["id"])]), 201)
    assert r.json()["bank_reference"] == "UTR-9" and r.json()["status"] == "completed"


@pytest.mark.tc("TC-FEE-12-A04")
def test_create_total_mismatch(admin, ctx, year_id):
    assert create_txn(admin, year_id, ctx, total="3000.02").status_code == 422


@pytest.mark.tc("TC-FEE-12-A05")
def test_create_overpay_is_400(admin, ctx, year_id):
    cash_txn(admin, ctx, year_id)
    r = create_txn(admin, year_id, ctx, items=[item(ctx["type"], ctx["dates"][0]["id"], "3000.00", "100.00")])
    assert r.status_code == 400
    assert "0" in h.detail_text(r)
    assert "outstanding" in h.detail_text(r).lower()


@pytest.mark.tc("TC-FEE-12-A06")
def test_create_student_without_mappings(admin, ctx, year_id, new_student):
    s = new_student()
    r = admin.post(f"{T}/", json=tx_body(year_id, s, [item(ctx["type"], ctx["dates"][0]["id"])]))
    assert r.status_code == 404
    assert f"Student has no fee structure configured for academic year {year_id}" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-12-A07")
def test_create_admission_number_mismatch(admin, ctx, year_id):
    body = tx_body(year_id, ctx["student"], [item(ctx["type"], ctx["dates"][0]["id"])])
    body["student_admission_num"] = "NOPE" + rid()[:6]
    r = admin.post(f"{T}/", json=body)
    assert r.status_code == 404
    assert "admission number" in h.detail_text(r) and "not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-12-A08")
def test_create_unknown_term_date(admin, ctx, year_id):
    ghost = rid()
    r = create_txn(admin, year_id, ctx, items=[item(ctx["type"], ghost)])
    assert r.status_code == 404
    assert f"Term amount not found for term date {ghost}" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-12-A09")
def test_create_two_items_same_term_date_cumulative(admin, ctx, year_id):
    d0 = ctx["dates"][0]["id"]
    r = create_txn(
        admin, year_id, ctx, items=[item(ctx["type"], d0, "3000.00", "2000.00"), item(ctx["type"], d0, "3000.00", "2000.00")]
    )
    assert r.status_code == 400
    assert h.summary_item(admin, ctx["student"], year_id, ctx["type"])["paid_amount"] in ("0", "0.00")


@pytest.mark.tc("TC-FEE-12-A10")
def test_create_dd_rejected(admin, ctx, year_id):
    assert create_txn(admin, year_id, ctx, method="dd", **cheque_fields()).status_code == 422


@pytest.mark.tc("TC-FEE-12-A10")
def test_create_idempotency_key(admin, ctx, year_id):
    key = "idem-" + rid()[:12]
    a = h.ok(create_txn(admin, year_id, ctx, method="cheque", idempotency_key=key, **cheque_fields()), 201).json()
    b = h.ok(create_txn(admin, year_id, ctx, method="cheque", idempotency_key=key, **cheque_fields()), 200, 201).json()
    assert a["id"] == b["id"] and a["transaction_number"] == b["transaction_number"]
    rows = items_of(h.ok(admin.get(f"{T}/", params={"student_id": ctx["student"]["id"]})))
    assert len(rows) == 1


@pytest.mark.tc("TC-FEE-12-A11")
def test_list_filters(admin, ctx, year_id):
    a = cash_txn(admin, ctx, year_id)
    h.ok(h.pay(admin, ctx["student"], year_id, "3000.00", [(ctx["type"], "3000.00")], method="upi", upi_reference="U-1"))
    ch = h.ok(create_txn(admin, year_id, ctx, method="cheque", items=[item(ctx["type"], ctx["dates"][2]["id"])], **cheque_fields()), 201).json()
    base = {"student_id": ctx["student"]["id"], "academic_year_id": year_id}
    allrows = items_of(h.ok(admin.get(f"{T}/", params=base)))
    assert len(allrows) == 3
    assert [r["id"] for r in allrows] == sorted((r["id"] for r in allrows), key=lambda i: [x["created_at"] for x in allrows if x["id"] == i][0], reverse=True)
    cash = items_of(admin.get(f"{T}/", params={**base, "payment_method": "cash", "status": "completed", "has_receipt": "true"}))
    assert [r["id"] for r in cash] == [a["id"]]
    assert cash[0]["transaction_items"] and cash[0]["receipt_number"]
    pending = items_of(admin.get(f"{T}/", params={**base, "status": "pending"}))
    assert [r["id"] for r in pending] == [ch["id"]]
    no_receipt = items_of(admin.get(f"{T}/", params={**base, "has_receipt": "false"}))
    assert [r["id"] for r in no_receipt] == [ch["id"]]


@pytest.mark.tc("TC-FEE-12-A12")
def test_list_invalid_status(admin):
    assert admin.get(f"{T}/", params={"status": "paid"}).status_code == 422
    assert admin.get(f"{T}/", params={"payment_method": "wallet"}).status_code == 422


@pytest.mark.tc("TC-FEE-12-A13")
def test_list_date_order(admin):
    r = admin.get(f"{T}/", params={"date_from": "2026-10-02", "date_to": "2026-10-01"})
    assert r.status_code == 400
    assert "date_from must be before or equal to date_to" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-12-A14")
def test_list_date_only_end_excludes_today(admin, ctx, year_id):
    cash_txn(admin, ctx, year_id)
    today = date.today()
    base = {"student_id": ctx["student"]["id"]}
    assert items_of(admin.get(f"{T}/", params={**base, "date_to": today.isoformat()})) == []
    tomorrow = (today + timedelta(days=1)).isoformat()
    assert len(items_of(admin.get(f"{T}/", params={**base, "date_from": today.isoformat(), "date_to": tomorrow}))) == 1


@pytest.mark.tc("TC-FEE-12-A15")
@pytest.mark.parametrize("limit", [0, 501])
def test_list_limit_bounds(admin, limit):
    assert admin.get(f"{T}/", params={"limit": limit}).status_code == 422


@pytest.mark.tc("TC-FEE-12-A16")
def test_get_transaction(admin, ctx, year_id):
    a = cash_txn(admin, ctx, year_id)
    data = h.ok(admin.get(f"{T}/{a['id']}")).json()
    assert data["student_full_name"] == f"{ctx['student']['first_name']} Tester"
    assert data["receipt_number"] == a["receipt_number"] and len(data["transaction_items"]) == 1
    r = admin.get(f"{T}/{rid()}")
    assert r.status_code == 404
    assert "Transaction not found" in h.detail_text(r)


def pending_cheque(admin, ctx, year_id, **kw):
    return h.ok(create_txn(admin, year_id, ctx, method="cheque", **cheque_fields(), **kw), 201).json()


@pytest.mark.tc("TC-FEE-12-A17")
def test_cheque_pending_to_completed_cleared(admin, ctx, year_id):
    c = pending_cheque(admin, ctx, year_id)
    r = h.ok(admin.put(f"{T}/{c['id']}", json={"status": "completed", "cheque_status": "cleared"}))
    assert r.json()["status"] == "completed" and r.json()["cheque_status"] == "cleared"
    assert h.summary_item(admin, ctx["student"], year_id, ctx["type"])["paid_amount"] == "3000.00"


@pytest.mark.tc("TC-FEE-12-A18")
def test_cheque_pending_to_bounced(admin, ctx, year_id):
    c = pending_cheque(admin, ctx, year_id)
    r = h.ok(admin.put(f"{T}/{c['id']}", json={"status": "bounced", "cheque_status": "bounced"}))
    assert r.json()["status"] == "bounced" and r.json()["cheque_status"] == "bounced"
    assert h.summary_item(admin, ctx["student"], year_id, ctx["type"])["paid_amount"] in ("0", "0.00")
    again = admin.put(f"{T}/{c['id']}", json={"status": "completed"})
    assert again.status_code == 400


@pytest.mark.tc("TC-FEE-12-A19")
def test_completed_cheque_to_bounced_reduces_paid(admin, ctx, year_id):
    c = pending_cheque(admin, ctx, year_id)
    h.ok(admin.put(f"{T}/{c['id']}", json={"status": "completed", "cheque_status": "cleared"}))
    gen = h.ok(admin.post(f"/fee/receipts/generate/{c['id']}"), 201).json()
    h.ok(admin.put(f"{T}/{c['id']}", json={"status": "bounced", "cheque_status": "bounced"}))
    assert h.summary_item(admin, ctx["student"], year_id, ctx["type"])["paid_amount"] in ("0", "0.00")
    assert h.ok(admin.get(f"/fee/receipts/{gen['id']}")).json()["id"] == gen["id"]


@pytest.mark.tc("TC-FEE-12-A20")
def test_pending_cash_cancel(admin, ctx, year_id):
    c = pending_cheque(admin, ctx, year_id)
    r = h.ok(admin.put(f"{T}/{c['id']}", json={"status": "cancelled"}))
    assert r.json()["status"] == "cancelled"


@pytest.mark.tc("TC-FEE-12-A21")
def test_invalid_status_moves(admin, ctx, year_id):
    cash = cash_txn(admin, ctx, year_id)
    r = admin.put(f"{T}/{cash['id']}", json={"status": "cancelled"})
    assert r.status_code == 400
    assert "Cannot change status from completed to cancelled." in h.detail_text(r)
    assert "Completed payments are reversed through refunds." in h.detail_text(r)
    r = admin.put(f"{T}/{cash['id']}", json={"status": "bounced"})
    assert r.status_code == 400 and "Only cheque and DD payments can bounce" in h.detail_text(r)
    later = [item(ctx["type"], ctx["dates"][1]["id"])]
    c = pending_cheque(admin, ctx, year_id, items=later)
    h.ok(admin.put(f"{T}/{c['id']}", json={"status": "cancelled"}))
    r = admin.put(f"{T}/{c['id']}", json={"status": "completed"})
    assert r.status_code == 400 and "Cannot change status from cancelled to completed." in h.detail_text(r)
    c2 = pending_cheque(admin, ctx, year_id, items=later)
    r = admin.put(f"{T}/{c2['id']}", json={"cheque_status": "bounced"})
    assert r.status_code == 400
    assert "A bounced cheque needs the transaction status set to bounced as well" in h.detail_text(r)
    r = admin.put(f"{T}/{cash['id']}", json={"cheque_status": "cleared"})
    assert r.status_code == 400
    assert "Cheque status applies only to cheque and DD payments" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-12-A22")
def test_update_approver_and_remarks(admin, logins, ctx, year_id):
    c = pending_cheque(admin, ctx, year_id)
    user_id = logins["admin"]["user"]["id"]
    r = h.ok(admin.put(f"{T}/{c['id']}", json={"approved_by_user_id": user_id, "remarks": "checked at counter"}))
    assert r.json()["approved_by_user_id"] == user_id and r.json()["remarks"] == "checked at counter"
    assert admin.get(f"{T}/{c['id']}").json()["remarks"] == "checked at counter"


@pytest.mark.tc("TC-FEE-12-A23")
def test_update_unknown_transaction(admin):
    missing = rid()
    r = admin.put(f"{T}/{missing}", json={"remarks": "x"})
    assert r.status_code == 404
    assert f"Transaction with ID {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-12-A24")
def test_update_invalid_status_value(admin, ctx, year_id):
    c = pending_cheque(admin, ctx, year_id)
    assert admin.put(f"{T}/{c['id']}", json={"status": "done"}).status_code == 422


@pytest.mark.tc("TC-FEE-12-A25")
def test_marking_cheque_completed_creates_no_receipt(admin, ctx, year_id):
    c = pending_cheque(admin, ctx, year_id)
    h.ok(admin.put(f"{T}/{c['id']}", json={"status": "completed", "cheque_status": "cleared"}))
    got = h.ok(admin.get(f"{T}/{c['id']}")).json()
    assert got["receipt_generated"] is False and not got["receipt_number"]


@pytest.mark.tc("TC-FEE-12-A26")
def test_outstanding_for_w2_ignores_concession(admin, w2, year_id, fee_world):
    r = h.ok(admin.get(f"{T}/student/{w2['student']['id']}/outstanding", params={"academic_year_id": year_id}))
    data = r.json()
    rows = data["outstanding_items"]
    assert sorted(h.D(x["outstanding_amount"]) for x in rows) == [2000, 3000, 3000]
    assert data["total_outstanding"] == "8000.00"
    assert all(x["fee_type_id"] == w2["tuition"]["id"] for x in rows)
    assert all(set(x) >= {"fee_type_name", "fee_term_id", "fee_term_name", "amount_due", "amount_paid", "outstanding_amount"} for x in rows)
    paid_row = next(x for x in rows if h.D(x["outstanding_amount"]) == 2000)
    assert paid_row["amount_due"] == "3000.00" and paid_row["amount_paid"] == "1000.00"


@pytest.mark.tc("TC-FEE-12-A27")
def test_student_transaction_history(admin, ctx, year_id):
    cash_txn(admin, ctx, year_id)
    second = cash_txn(admin, ctx, year_id)
    r = h.ok(admin.get(f"{T}/student/{ctx['student']['id']}/history", params={"academic_year_id": year_id, "limit": 1}))
    data = r.json()
    assert len(data["transactions"]) == 1
    row = data["transactions"][0]
    assert row["transaction_number"] == second["transaction_number"]
    assert row["fee_types_paid"] and row["receipt_generated"] is True


@pytest.mark.tc("TC-FEE-12-A28")
def test_get_by_transaction_number(admin, ctx, year_id):
    older = cash_txn(admin, ctx, year_id)
    newer = cash_txn(admin, ctx, year_id)
    for t in (newer, older):
        got = h.ok(admin.get(f"{T}/transaction-number/{t['transaction_number']}")).json()
        assert got["id"] == t["id"]
    assert admin.get(f"{T}/transaction-number/TXN00000000NONE").status_code == 404


@pytest.mark.tc("TC-FEE-12-A29")
def test_transaction_health(admin):
    assert h.ok(admin.get(f"{T}/health")).json()["module"] == "fee_transactions"


@pytest.mark.tc("TC-FEE-12-A30")
@pytest.mark.parametrize("role", ROLES)
def test_transaction_create_matrix(role, role_clients, ctx, year_id):
    body = tx_body(year_id, ctx["student"], [item(ctx["type"], ctx["dates"][0]["id"], "3000.00", "100.00")], method="cheque", **cheque_fields())
    r = role_clients[role].post(f"{T}/", json=body)
    assert r.status_code == (201 if role in ("admin", "staff") else 403)


@pytest.mark.tc("TC-FEE-12-A31")
@pytest.mark.parametrize("role", ROLES)
def test_transaction_update_matrix(role, role_clients, admin, ctx, year_id):
    c = pending_cheque(admin, ctx, year_id)
    r = role_clients[role].put(f"{T}/{c['id']}", json={"remarks": "role check"})
    assert r.status_code == (200 if role in ("admin", "staff") else 403)


@pytest.mark.tc("TC-FEE-12-A32")
@pytest.mark.parametrize("role", ROLES)
def test_transaction_read_matrix(role, role_clients, admin, ctx, year_id):
    c = cash_txn(admin, ctx, year_id)
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    sid = ctx["student"]["id"]
    assert client.get(f"{T}/", params={"student_id": sid}).status_code == expected
    assert client.get(f"{T}/{c['id']}").status_code == expected
    assert client.get(f"{T}/student/{sid}/outstanding", params={"academic_year_id": year_id}).status_code == expected
    assert client.get(f"{T}/student/{sid}/history", params={"academic_year_id": year_id}).status_code == expected
    assert client.get(f"{T}/transaction-number/{c['transaction_number']}").status_code == expected


@pytest.mark.tc("TC-FEE-12-A33")
def test_transaction_no_token_header_isolation(anon, mismatched_admin, tenant_b, admin, ctx, year_id):
    c = cash_txn(admin, ctx, year_id)
    assert anon.get(f"{T}/").status_code == 401
    assert anon.get(f"{T}/{c['id']}").status_code == 401
    assert anon.post(f"{T}/", json=tx_body(year_id, ctx["student"], [item(ctx["type"], ctx["dates"][0]["id"])])).status_code == 401
    assert anon.put(f"{T}/{c['id']}", json={"remarks": "x"}).status_code == 401
    assert mismatched_admin.get(f"{T}/").status_code == 403
    assert items_of(tenant_b.get(f"{T}/", params={"student_id": ctx["student"]["id"]})) == []
    assert tenant_b.get(f"{T}/{c['id']}").status_code == 404
    assert tenant_b.put(f"{T}/{c['id']}", json={"remarks": "x"}).status_code == 404
