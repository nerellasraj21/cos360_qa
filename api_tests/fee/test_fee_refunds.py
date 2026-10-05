import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import pytest

from api_tests.fee import helpers as h
from api_tests.support import Api, items_of

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
F = "/fee/refunds"


def rid():
    return str(uuid.uuid4())


@pytest.fixture
def txn(admin, w1, year_id):
    pay = h.ok(h.pay(admin, w1["student"], year_id, "5000.00", [(w1["tuition"]["id"], "5000.00")])).json()
    return {"id": pay["transaction_id"], "student": w1["student"], "tuition": w1["tuition"], "pay": pay}


def new_refund(admin, txn_id, amount="2000.00", reason="excess_payment", **extra):
    body = {"fee_transaction_id": txn_id, "refund_amount": amount, "refund_reason": reason}
    body.update(extra)
    return admin.post(f"{F}/", json=body)


def approve(client, refund_id, action="approve", remarks="Approved by test", **extra):
    return client.post(f"{F}/approve", json={"refund_id": refund_id, "action": action, "approval_remarks": remarks, **extra})


def process(client, refund_id, method="bank_transfer", **extra):
    return client.post(
        f"{F}/process", json={"refund_id": refund_id, "refund_method": method, "refund_reference": "UTR-REF-1", "processing_remarks": "paid out", **extra}
    )


@pytest.mark.tc("TC-FEE-13-A01")
def test_create_refund(admin, logins, txn):
    other_user = str(uuid.uuid4())
    r = h.ok(new_refund(admin, txn["id"], requested_by_user_id=other_user), 201)
    data = r.json()
    assert data["status"] == "pending"
    assert re.match(r"^RFD\d{8}[0-9A-F]{6}$", data["refund_number"])
    assert data["refund_amount"] == "2000.00"
    assert data["requested_by_user_id"] == logins["admin"]["user"]["id"]
    assert data["student_id"] == txn["student"]["id"]
    assert data["student_admission_num"] == txn["student"]["admission_number"]
    assert data["approved_by_user_id"] is None and data["processed_date"] is None


@pytest.mark.tc("TC-FEE-13-A02")
def test_create_refund_without_requested_by_user(admin, txn):
    r = h.ok(new_refund(admin, txn["id"]), 201)
    assert r.json()["status"] == "pending"


@pytest.mark.tc("TC-FEE-13-A03")
def test_create_refund_above_available(admin, txn):
    h.ok(new_refund(admin, txn["id"], "3000.00"), 201)
    r = new_refund(admin, txn["id"], "2500.00")
    assert r.status_code == 400
    assert "Refund amount 2500" in h.detail_text(r) and "exceeds available amount 2000.00" in h.detail_text(r)
    h.ok(new_refund(admin, txn["id"], "2000.00"), 201)


@pytest.mark.tc("TC-FEE-13-A04")
def test_create_refund_on_pending_cheque(admin, w1, year_id):
    t = w1["tuition"]["id"]
    ch = h.ok(
        h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")], method="cheque", cheque_number="C1", cheque_bank="B", cheque_date=date.today().isoformat())
    ).json()
    r = new_refund(admin, ch["transaction_id"], "500.00")
    assert r.status_code == 400
    assert "Can only refund completed transactions" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-13-A05")
def test_create_refund_unknown_transaction(admin):
    missing = rid()
    r = new_refund(admin, missing)
    assert r.status_code == 404
    assert f"Transaction with ID {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-13-A06")
def test_create_refund_other_without_detail(admin, txn):
    r = h.ok(new_refund(admin, txn["id"], "100.00", reason="other"), 201)
    assert r.json()["refund_reason"] == "other" and r.json()["detailed_reason"] is None


@pytest.mark.tc("TC-FEE-13-A07")
def test_create_refund_validation(admin, txn):
    assert new_refund(admin, txn["id"], reason="withdrawal").status_code == 422
    assert new_refund(admin, txn["id"], "0").status_code == 422
    assert new_refund(admin, txn["id"], "-1").status_code == 422


@pytest.mark.tc("TC-FEE-13-A08")
def test_create_refund_conflicting_student(admin, new_student, txn):
    other = new_student()
    r = new_refund(admin, txn["id"], "100.00", student_id=other["id"])
    assert r.status_code == 400


@pytest.mark.tc("TC-FEE-13-A09")
def test_approve_refund(admin, logins, txn):
    ref = h.ok(new_refund(admin, txn["id"]), 201).json()
    r = h.ok(approve(admin, ref["id"], approved_by_user_id=str(uuid.uuid4())))
    data = r.json()
    assert data["status"] == "approved"
    assert data["approved_by_user_id"] == logins["admin"]["user"]["id"]
    assert data["approved_date"] and data["approval_remarks"] == "Approved by test"


@pytest.mark.tc("TC-FEE-13-A10")
def test_reject_refund_is_final(admin, txn):
    ref = h.ok(new_refund(admin, txn["id"]), 201).json()
    r = h.ok(approve(admin, ref["id"], "reject", "not eligible"))
    assert r.json()["status"] == "rejected"
    again = approve(admin, ref["id"])
    assert again.status_code == 400


@pytest.mark.tc("TC-FEE-13-A11")
def test_approve_twice(admin, txn):
    ref = h.ok(new_refund(admin, txn["id"]), 201).json()
    h.ok(approve(admin, ref["id"]))
    r = approve(admin, ref["id"])
    assert r.status_code == 400
    assert "Refund is already approved, cannot change approval status" in h.detail_text(r)
    rej = h.ok(new_refund(admin, txn["id"], "100.00"), 201).json()
    h.ok(approve(admin, rej["id"], "reject", "no"))
    r = approve(admin, rej["id"], "approve")
    assert r.status_code == 400 and "Refund is already rejected" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-13-A12")
def test_approve_validation(admin, txn):
    ref = h.ok(new_refund(admin, txn["id"]), 201).json()
    assert admin.post(f"{F}/approve", json={"refund_id": ref["id"], "action": "cancel", "approval_remarks": "x"}).status_code == 422
    assert admin.post(f"{F}/approve", json={"action": "approve", "approval_remarks": "x"}).status_code == 422
    assert admin.post(f"{F}/approve", json={"refund_id": rid(), "action": "approve", "approval_remarks": "x"}).status_code == 404


@pytest.mark.tc("TC-FEE-13-A13")
def test_process_refund(admin, logins, txn):
    ref = h.ok(new_refund(admin, txn["id"]), 201).json()
    h.ok(approve(admin, ref["id"]))
    r = h.ok(process(admin, ref["id"]))
    data = r.json()
    assert data["status"] == "processed"
    assert data["refund_method"] == "bank_transfer" and data["refund_reference"] == "UTR-REF-1"
    assert data["processing_remarks"] == "paid out" and data["processed_date"]
    assert data["processed_by_user_id"] == logins["admin"]["user"]["id"]


@pytest.mark.tc("TC-FEE-13-A14")
def test_process_requires_approved(admin, txn):
    pending = h.ok(new_refund(admin, txn["id"], "100.00"), 201).json()
    r = process(admin, pending["id"])
    assert r.status_code == 400 and "Only approved refunds can be processed" in h.detail_text(r)
    rejected = h.ok(new_refund(admin, txn["id"], "100.00"), 201).json()
    h.ok(approve(admin, rejected["id"], "reject", "no"))
    assert process(admin, rejected["id"]).status_code == 400
    done = h.ok(new_refund(admin, txn["id"], "100.00"), 201).json()
    h.ok(approve(admin, done["id"]))
    h.ok(process(admin, done["id"], "cash"))
    again = process(admin, done["id"], "cash")
    assert again.status_code == 400 and "Only approved refunds can be processed" in h.detail_text(again)


@pytest.mark.tc("TC-FEE-13-A15")
def test_process_validation(admin, txn):
    ref = h.ok(new_refund(admin, txn["id"]), 201).json()
    h.ok(approve(admin, ref["id"]))
    assert admin.post(f"{F}/process", json={"refund_id": ref["id"]}).status_code == 422
    assert admin.post(f"{F}/process", json={"refund_id": ref["id"], "refund_method": "card"}).status_code == 422


@pytest.mark.tc("TC-FEE-13-A16")
def test_available_amount_after_approval(admin, txn):
    ref = h.ok(new_refund(admin, txn["id"], "3000.00"), 201).json()
    h.ok(approve(admin, ref["id"]))
    r = new_refund(admin, txn["id"], "2000.01")
    assert r.status_code == 400 and "exceeds available amount 2000.00" in h.detail_text(r)
    h.ok(new_refund(admin, txn["id"], "2000.00"), 201)


@pytest.mark.tc("TC-FEE-13-A16")
def test_pending_refunds_count_against_available(admin, txn):
    h.ok(new_refund(admin, txn["id"], "4000.00"), 201)
    r = new_refund(admin, txn["id"], "4000.00")
    assert r.status_code == 400
    assert "exceeds available amount 1000.00" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-13-A16")
def test_rejected_refund_frees_amount(admin, txn):
    first = h.ok(new_refund(admin, txn["id"], "5000.00"), 201).json()
    assert new_refund(admin, txn["id"], "100.00").status_code == 400
    h.ok(approve(admin, first["id"], "reject", "declined"))
    h.ok(new_refund(admin, txn["id"], "5000.00"), 201)


@pytest.mark.tc("TC-FEE-13-A16")
def test_parallel_refund_requests_never_exceed_transaction(logins, txn):
    def call(_):
        client = Api(token=logins["admin"]["access_token"])
        try:
            return new_refund(client, txn["id"], "3000.00")
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(call, range(3)))
    assert sorted(r.status_code for r in results) == [201, 400, 400]
    client = Api(token=logins["admin"]["access_token"])
    try:
        summ = h.ok(client.get(f"{F}/transaction/{txn['id']}/summary")).json()
    finally:
        client.close()
    assert h.D(summ["total_requested"]) == 3000


@pytest.mark.tc("TC-FEE-13-A17")
def test_processed_refund_keeps_paid_unchanged(admin, w1, year_id, txn):
    ref = h.ok(new_refund(admin, txn["id"], "1000.00"), 201).json()
    h.ok(approve(admin, ref["id"]))
    h.ok(process(admin, ref["id"], "cash"))
    item = h.summary_item(admin, w1["student"], year_id, w1["tuition"]["id"])
    assert item["paid_amount"] == "5000.00" and item["due_amount"] == "7000.00"


@pytest.mark.tc("TC-FEE-13-A18")
def test_list_filters(admin, txn):
    a = h.ok(new_refund(admin, txn["id"], "500.00"), 201).json()
    b = h.ok(new_refund(admin, txn["id"], "600.00", reason="fee_adjustment"), 201).json()
    h.ok(approve(admin, b["id"]))
    base = {"student_id": txn["student"]["id"]}
    rows = items_of(h.ok(admin.get(f"{F}/", params=base)))
    assert [r["id"] for r in rows] == [b["id"], a["id"]]
    pending = items_of(admin.get(f"{F}/", params={**base, "status": "pending"}))
    assert [r["id"] for r in pending] == [a["id"]]
    today = date.today()
    ranged = items_of(
        admin.get(f"{F}/", params={**base, "date_from": today.isoformat(), "date_to": (today + timedelta(days=1)).isoformat()})
    )
    assert {r["id"] for r in ranged} == {a["id"], b["id"]}
    page = items_of(admin.get(f"{F}/", params={**base, "limit": 1, "offset": 1}))
    assert len(page) == 1
    assert admin.get(f"{F}/", params={"date_from": "2026-10-02", "date_to": "2026-10-01"}).status_code == 400


@pytest.mark.tc("TC-FEE-13-A19")
@pytest.mark.parametrize("reason", ["fee_adjustment", "student_withdrawal", "excess_payment", "other"])
def test_list_filter_by_reason(reason, admin, txn):
    ref = h.ok(new_refund(admin, txn["id"], "100.00", reason=reason), 201).json()
    rows = items_of(h.ok(admin.get(f"{F}/", params={"student_id": txn["student"]["id"], "refund_reason": reason})))
    assert [r["id"] for r in rows] == [ref["id"]]


@pytest.mark.tc("TC-FEE-13-A19")
def test_list_filter_invalid_reason(admin):
    assert admin.get(f"{F}/", params={"refund_reason": "adjustment"}).status_code == 422


@pytest.mark.tc("TC-FEE-13-A20")
def test_list_invalid_status(admin):
    assert admin.get(f"{F}/", params={"status": "completed"}).status_code == 422


@pytest.mark.tc("TC-FEE-13-A21")
def test_pending_and_approved_queues(admin, txn):
    a = h.ok(new_refund(admin, txn["id"], "500.00"), 201).json()
    b = h.ok(new_refund(admin, txn["id"], "600.00"), 201).json()
    h.ok(approve(admin, b["id"]))
    pending = items_of(h.ok(admin.get(f"{F}/pending/approval", params={"limit": 500})))
    assert a["id"] in {r["id"] for r in pending} and b["id"] not in {r["id"] for r in pending}
    assert all(r["status"] == "pending" for r in pending)
    ordered = [r["requested_date"] for r in pending]
    assert ordered == sorted(ordered)
    approved = items_of(h.ok(admin.get(f"{F}/approved/processing", params={"limit": 500})))
    assert b["id"] in {r["id"] for r in approved} and a["id"] not in {r["id"] for r in approved}
    assert all(r["status"] == "approved" for r in approved)


@pytest.mark.tc("TC-FEE-13-A22")
def test_statistics_delta(admin, year_id, txn):
    before = h.ok(admin.get(f"{F}/statistics", params={"academic_year_id": year_id})).json()
    pend = h.ok(new_refund(admin, txn["id"], "500.00"), 201).json()
    proc = h.ok(new_refund(admin, txn["id"], "700.00", reason="student_withdrawal"), 201).json()
    h.ok(approve(admin, proc["id"]))
    h.ok(process(admin, proc["id"], "cash"))
    rej = h.ok(new_refund(admin, txn["id"], "300.00"), 201).json()
    h.ok(approve(admin, rej["id"], "reject", "no"))
    after = h.ok(admin.get(f"{F}/statistics", params={"academic_year_id": year_id})).json()
    assert after["total_pending_refunds"] - before["total_pending_refunds"] >= 1
    assert after["total_processed_refunds"] - before["total_processed_refunds"] >= 1
    assert after["total_rejected_refunds"] - before["total_rejected_refunds"] >= 1
    assert round(after["total_refund_amount"] - before["total_refund_amount"], 2) >= 700.00
    assert after["refunds_by_reason"].get("student_withdrawal", 0) - before["refunds_by_reason"].get("student_withdrawal", 0) >= 1
    month = datetime.now().strftime("%Y-%m")
    month_after = next(m for m in after["monthly_refunds"] if m["month"] == month)
    month_before = next((m for m in before["monthly_refunds"] if m["month"] == month), {"count": 0, "amount": 0})
    assert month_after["count"] - month_before["count"] >= 2
    assert round(month_after["amount"] - month_before["amount"], 2) >= 1200.00
    assert pend["id"]


@pytest.mark.tc("TC-FEE-13-A22")
def test_statistics_with_future_dates_is_empty(admin, year_id):
    far = (date.today() + timedelta(days=3650)).isoformat()
    far2 = (date.today() + timedelta(days=3651)).isoformat()
    data = h.ok(admin.get(f"{F}/statistics", params={"academic_year_id": year_id, "date_from": far, "date_to": far2})).json()
    assert data["total_refund_amount"] == 0
    assert data["total_pending_refunds"] == data["total_approved_refunds"] == data["total_processed_refunds"] == data["total_rejected_refunds"] == 0
    assert data["monthly_refunds"] == []


@pytest.mark.tc("TC-FEE-13-A23")
def test_transaction_summary(admin, txn):
    a = h.ok(new_refund(admin, txn["id"], "1000.00"), 201).json()
    b = h.ok(new_refund(admin, txn["id"], "700.00"), 201).json()
    c = h.ok(new_refund(admin, txn["id"], "300.00"), 201).json()
    h.ok(approve(admin, b["id"]))
    h.ok(process(admin, b["id"], "cash"))
    h.ok(approve(admin, c["id"], "reject", "no"))
    s = h.ok(admin.get(f"{F}/transaction/{txn['id']}/summary")).json()
    assert h.D(s["total_requested"]) == 2000
    assert h.D(s["total_approved"]) == 700
    assert h.D(s["total_processed"]) == 700
    assert s["status_counts"] == {"pending": 1, "approved": 0, "rejected": 1, "processed": 1}
    assert s["refund_count"] == 3
    assert a["id"]
    empty = h.ok(admin.get(f"{F}/transaction/{rid()}/summary")).json()
    assert empty["refund_count"] == 0 and h.D(empty["total_requested"]) == 0


@pytest.mark.tc("TC-FEE-13-A24")
def test_get_refund(admin, txn):
    ref = h.ok(new_refund(admin, txn["id"]), 201).json()
    assert h.ok(admin.get(f"{F}/{ref['id']}")).json()["id"] == ref["id"]
    missing = rid()
    r = admin.get(f"{F}/{missing}")
    assert r.status_code == 404
    assert f"Refund with ID {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-13-A25")
def test_nonexistent_endpoints(admin, txn):
    ref = h.ok(new_refund(admin, txn["id"]), 201).json()
    assert admin.put(f"{F}/{ref['id']}", json={"status": "approved"}).status_code in (404, 405)
    assert admin.delete(f"{F}/{ref['id']}").status_code in (404, 405)
    assert admin.post(f"{F}/{ref['id']}/cancel").status_code in (404, 405)
    assert admin.get(f"{F}/by-transaction/{txn['id']}").status_code in (404, 422)
    assert h.ok(admin.get(f"{F}/{ref['id']}")).json()["status"] == "pending"


@pytest.mark.tc("TC-FEE-13-A26")
def test_refund_health(admin):
    assert h.ok(admin.get(f"{F}/health")).json()["module"] == "fee_refunds"


@pytest.mark.tc("TC-FEE-13-A27")
@pytest.mark.parametrize("role", ROLES)
def test_refund_create_matrix(role, role_clients, txn):
    r = new_refund(role_clients[role], txn["id"], "100.00")
    assert r.status_code == (201 if role in ("admin", "staff") else 403)


@pytest.mark.tc("TC-FEE-13-A28")
@pytest.mark.parametrize("role", ROLES)
def test_refund_approve_matrix(role, role_clients, admin, txn):
    ref = h.ok(new_refund(admin, txn["id"], "100.00"), 201).json()
    r = approve(role_clients[role], ref["id"])
    assert r.status_code == (200 if role == "admin" else 403)
    if role != "admin":
        assert admin.get(f"{F}/{ref['id']}").json()["status"] == "pending"


@pytest.mark.tc("TC-FEE-13-A29")
@pytest.mark.parametrize("role", ROLES)
def test_refund_process_matrix(role, role_clients, admin, txn):
    ref = h.ok(new_refund(admin, txn["id"], "100.00"), 201).json()
    h.ok(approve(admin, ref["id"]))
    r = process(role_clients[role], ref["id"], "cash")
    assert r.status_code == (200 if role == "admin" else 403)
    if role != "admin":
        assert admin.get(f"{F}/{ref['id']}").json()["status"] == "approved"


@pytest.mark.tc("TC-FEE-13-A30")
@pytest.mark.parametrize("role", ROLES)
def test_refund_read_matrix(role, role_clients, admin, txn):
    ref = h.ok(new_refund(admin, txn["id"], "100.00"), 201).json()
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get(f"{F}/").status_code == expected
    assert client.get(f"{F}/statistics").status_code == expected
    assert client.get(f"{F}/{ref['id']}").status_code == expected
    assert client.get(f"{F}/pending/approval").status_code == expected
    assert client.get(f"{F}/approved/processing").status_code == expected
    assert client.get(f"{F}/transaction/{txn['id']}/summary").status_code == expected


@pytest.mark.tc("TC-FEE-13-A31")
def test_refund_no_token_header_isolation(anon, mismatched_admin, tenant_b, admin, txn):
    ref = h.ok(new_refund(admin, txn["id"], "100.00"), 201).json()
    assert anon.get(f"{F}/").status_code == 401
    assert anon.get(f"{F}/{ref['id']}").status_code == 401
    assert anon.post(f"{F}/", json={"fee_transaction_id": txn["id"], "refund_amount": "1", "refund_reason": "other"}).status_code == 401
    assert anon.post(f"{F}/approve", json={"refund_id": ref["id"], "action": "approve"}).status_code == 401
    assert mismatched_admin.get(f"{F}/").status_code == 403
    assert items_of(tenant_b.get(f"{F}/", params={"student_id": txn["student"]["id"]})) == []
    assert tenant_b.get(f"{F}/{ref['id']}").status_code == 404
    assert approve(tenant_b, ref["id"]).status_code == 404
    assert new_refund(tenant_b, txn["id"], "10.00").status_code == 404
    assert admin.get(f"{F}/{ref['id']}").json()["status"] == "pending"
