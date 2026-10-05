import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import pytest

from api_tests.fee import helpers as h
from api_tests.support import Api, items_of, unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
C = "/fee/collection"
RECEIPT_RE = re.compile(r"^REC-(\d{4})-(\d{4})$")


def rid():
    return str(uuid.uuid4())


def txn_of(admin, response):
    return h.ok(admin.get(f"/fee/transactions/{response.json()['transaction_id']}")).json()


def cheque_kwargs(days=0, number="CHQ100"):
    return {"cheque_number": number, "cheque_bank": "Test Bank", "cheque_date": (date.today() + timedelta(days=days)).isoformat()}


@pytest.fixture
def lab_student(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    h.map_student(admin, cleanup, year_id, s, fee_world["lab"]["id"], "1000.00")
    return s


@pytest.mark.tc("TC-FEE-10-A01")
def test_pay_cash_with_fee_items(admin, w1, year_id):
    t = w1["tuition"]["id"]
    r = h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")]))
    data = r.json()
    assert data["payment_method"] == "cash" and h.D(data["amount_paid"]) == 3000 and data["amount_paid"] == "3000.00"
    assert re.match(r"^TXN\d{8}[0-9A-F]{8}$", data["transaction_number"])
    m = RECEIPT_RE.match(data["receipt_number"])
    assert m and m.group(1) == datetime.now().strftime("%y%m")
    assert [(i["fee_type_id"], h.D(i["amount_paid"])) for i in data["items_paid"]] == [(t, 3000)]
    assert data["sms_status"] == "skipped"
    txn = txn_of(admin, r)
    assert txn["status"] == "completed" and txn["receipt_generated"] is True
    assert txn["receipt_number"] == data["receipt_number"]
    assert [(i["amount_paid"], i["amount_due"]) for i in txn["transaction_items"]] == [("3000.00", "3000.00")]
    assert txn["transaction_items"][0]["term_date_id"]
    assert h.summary_item(admin, w1["student"], year_id, t)["due_amount"] == "9000.00"


@pytest.mark.tc("TC-FEE-10-A02")
def test_pay_exact_full_due(admin, w1, year_id):
    t = w1["tuition"]["id"]
    h.ok(h.pay(admin, w1["student"], year_id, "12000.00", [(t, "12000.00")]))
    item = h.summary_item(admin, w1["student"], year_id, t)
    assert item["due_amount"] == "0.00" and item["paid_amount"] == "12000.00"


@pytest.mark.tc("TC-FEE-10-A03")
def test_pay_above_total_due(admin, w1, year_id):
    r = h.pay(admin, w1["student"], year_id, "12000.01")
    assert r.status_code == 400
    assert "Amount 12000.01 exceeds total due 12000.00" in h.detail_text(r)
    r = h.pay(admin, w1["student"], year_id, "12000.01", [(w1["tuition"]["id"], "12000.01")])
    assert r.status_code == 400
    assert "exceeds total due 12000.00" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-10-A04")
def test_pay_when_nothing_due(admin, w1, year_id):
    t = w1["tuition"]["id"]
    h.ok(h.pay(admin, w1["student"], year_id, "12000.00", [(t, "12000.00")]))
    r = h.pay(admin, w1["student"], year_id, "100.00", [(t, "100.00")])
    assert r.status_code == 400
    assert "No outstanding dues for this student" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-10-A05")
def test_pay_fee_item_above_its_outstanding(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    t, lab = fee_world["tuition"]["id"], fee_world["lab"]["id"]
    h.map_student(admin, cleanup, year_id, s, t, "12000.00")
    h.map_student(admin, cleanup, year_id, s, lab, "1000.00")
    h.ok(h.pay(admin, s, year_id, "9000.00", [(t, "9000.00")]))
    r = h.pay(admin, s, year_id, "3500.00", [(t, "3500.00")])
    assert r.status_code == 400
    text = h.detail_text(r)
    assert "Amount 3500" in text and f"'{fee_world['tuition']['type_name']}'" in text
    assert "exceeds its outstanding due 3000.00" in text


@pytest.mark.tc("TC-FEE-10-A06")
def test_pay_fee_item_not_mapped(admin, w1, year_id, fee_world):
    lab = fee_world["lab"]["id"]
    r = h.pay(admin, w1["student"], year_id, "100.00", [(lab, "100.00")])
    assert r.status_code == 400
    assert f"Fee type {lab} is not mapped to this student for this academic year" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-10-A07")
def test_pay_fee_item_already_paid(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    t, lab = fee_world["tuition"]["id"], fee_world["lab"]["id"]
    h.map_student(admin, cleanup, year_id, s, t, "12000.00")
    h.map_student(admin, cleanup, year_id, s, lab, "1000.00")
    h.ok(h.pay(admin, s, year_id, "12000.00", [(t, "12000.00")]))
    r = h.pay(admin, s, year_id, "100.00", [(t, "100.00")])
    assert r.status_code == 400
    assert f"'{fee_world['tuition']['type_name']}' has no outstanding due; nothing to pay for this fee type" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-10-A08")
def test_w5_uneven_split_explicit_full(admin, year_id, fee_world, lab_student):
    r = h.pay(admin, lab_student, year_id, "1000.00", [(fee_world["lab"]["id"], "1000.00")])
    assert r.status_code == 400
    assert f"Amount for '{fee_world['lab']['type_name']}' exceeds the scheduled term amounts by 0.01; check the term-wise fee setup" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-10-A09")
def test_w6_uneven_split_auto_full(admin, year_id, fee_world, lab_student):
    r = h.ok(h.pay(admin, lab_student, year_id, "1000.00"))
    assert r.json()["amount_paid"] == "999.99"
    item = h.summary_item(admin, lab_student, year_id, fee_world["lab"]["id"])
    assert item["due_amount"] == "0.01" and item["paid_amount"] == "999.99"


@pytest.mark.tc("TC-FEE-10-A10")
def test_w7_leftover_cent(admin, year_id, fee_world, lab_student):
    h.ok(h.pay(admin, lab_student, year_id, "1000.00"))
    r = h.pay(admin, lab_student, year_id, "0.01")
    assert r.status_code == 400
    assert "No outstanding fees to pay" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-10-A11")
def test_w2_pay_remaining_payable(admin, w2, year_id):
    t = w2["tuition"]["id"]
    h.ok(h.pay(admin, w2["student"], year_id, "6000.00", [(t, "6000.00")]))
    assert h.summary_item(admin, w2["student"], year_id, t)["due_amount"] == "0.00"


@pytest.mark.tc("TC-FEE-10-A12")
def test_w2_pay_above_payable(admin, w2, year_id):
    r = h.pay(admin, w2["student"], year_id, "6000.01", [(w2["tuition"]["id"], "6000.01")])
    assert r.status_code == 400
    assert "exceeds" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-10-A13")
def test_pay_without_items_reduces_old_fee(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    t = fee_world["tuition"]["id"]
    h.map_student(admin, cleanup, year_id, s, t, "12000.00")
    old = h.ok(
        admin.post(
            "/fee/old-fees/",
            json={"student_id": s["id"], "academic_year_label": "2024-25", "fee_type_name": "Bus Fee", "original_amount": "900.00", "paid_amount": "0"},
        ),
        201,
    ).json()
    cleanup.delete_later(admin, f"/fee/old-fees/{old['id']}")
    r = h.ok(h.pay(admin, s, year_id, "12900.00")).json()
    names = [i["fee_type_name"] for i in r["items_paid"]]
    assert "Old: Bus Fee (2024-25)" in names
    assert h.summary_item(admin, s, year_id, t)["due_amount"] == "0.00"
    got = h.ok(admin.get(f"/fee/old-fees/{old['id']}")).json()
    assert got["paid_amount"] == "900.00" and got["is_settled"] is True
    assert got["receipt_system"] == r["receipt_number"] and got["paid_date"] == date.today().isoformat()


@pytest.mark.tc("TC-FEE-10-A14")
def test_pay_upi(admin, w1, year_id):
    t = w1["tuition"]["id"]
    ref = unique("UPI")
    r = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")], method="upi", upi_reference=ref))
    assert txn_of(admin, r)["upi_reference"] == ref
    content = h.ok(admin.get(f"/fee/receipts/{r.json()['receipt_id']}/content")).json()
    assert content["payment_reference"] == ref and content["payment_method"] == "upi"


@pytest.mark.tc("TC-FEE-10-A15")
def test_pay_upi_without_reference(admin, w1, year_id):
    r = h.pay(admin, w1["student"], year_id, "1000.00", [(w1["tuition"]["id"], "1000.00")], method="upi")
    assert r.status_code == 422


@pytest.mark.tc("TC-FEE-10-A16")
def test_pay_bank_transfer(admin, w1, year_id):
    t = w1["tuition"]["id"]
    assert h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")], method="bank_transfer").status_code == 422
    ref = unique("UTR")
    r = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")], method="bank_transfer", bank_reference=ref))
    assert txn_of(admin, r)["bank_reference"] == ref


@pytest.mark.tc("TC-FEE-10-A17")
def test_pay_card(admin, w1, year_id):
    r = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(w1["tuition"]["id"], "1000.00")], method="card"))
    assert r.json()["payment_method"] == "card"
    assert txn_of(admin, r)["payment_method"] == "card"


@pytest.mark.tc("TC-FEE-10-A18")
def test_pay_cheque_is_pending(admin, w1, year_id):
    t = w1["tuition"]["id"]
    r = h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")], method="cheque", **cheque_kwargs()))
    data = r.json()
    assert data["receipt_number"] == "" and data["sms_status"] == "skipped"
    txn = txn_of(admin, r)
    assert txn["status"] == "pending" and txn["cheque_status"] == "pending" and txn["receipt_generated"] is False
    assert txn["cheque_number"] == "CHQ100" and txn["cheque_bank"] == "Test Bank"
    assert h.summary_item(admin, w1["student"], year_id, t)["due_amount"] == "12000.00"


@pytest.mark.tc("TC-FEE-10-A19")
def test_pay_dd_then_clear_and_generate_receipt(admin, w1, year_id):
    t = w1["tuition"]["id"]
    r = h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")], method="dd", **cheque_kwargs(number="DD777")))
    assert r.json()["receipt_number"] == ""
    tid = r.json()["transaction_id"]
    assert admin.get(f"/fee/transactions/{tid}").json()["status"] == "pending"
    h.ok(admin.put(f"/fee/transactions/{tid}", json={"status": "completed", "cheque_status": "cleared"}))
    gen = h.ok(admin.post(f"/fee/receipts/generate/{tid}"), 201)
    content = h.ok(admin.get(f"/fee/receipts/{gen.json()['id']}/content")).json()
    assert content["payment_reference"] == "DD: DD777"


@pytest.mark.tc("TC-FEE-10-A20")
def test_cheque_date_window(admin, w1, year_id):
    t = w1["tuition"]["id"]
    r = h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")], method="cheque", **cheque_kwargs(91))
    assert r.status_code == 422
    r = h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")], method="cheque", **cheque_kwargs(90))
    h.ok(r)


@pytest.mark.tc("TC-FEE-10-A21")
def test_print_duplicate_flag(admin, w1, year_id):
    r = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(w1["tuition"]["id"], "1000.00")], print_duplicate=True))
    receipt = h.ok(admin.get(f"/fee/receipts/{r.json()['receipt_id']}")).json()
    assert receipt["is_reprinted"] is True and receipt["reprint_count"] == 1


@pytest.mark.tc("TC-FEE-10-A22")
def test_send_sms_false(admin, w1, year_id):
    r = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(w1["tuition"]["id"], "1000.00")], send_sms=False))
    assert r.json()["sms_status"] == "skipped"


@pytest.mark.tc("TC-FEE-10-A23")
@pytest.mark.skip(reason="admission requires a parent phone, so a parent without a phone cannot be created and send_sms=true would reach the SMS provider")
def test_send_sms_without_parent_phone():
    pass


@pytest.mark.tc("TC-FEE-10-A24")
def test_pay_student_without_mappings(admin, year_id, new_student):
    r = h.pay(admin, new_student(), year_id, "100.00")
    assert r.status_code == 404
    assert "No fee mappings found for this student and academic year" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-10-A25")
def test_pay_unknown_student(admin, year_id):
    r = h.pay(admin, {"id": rid()}, year_id, "100.00")
    assert r.status_code == 404


@pytest.mark.tc("TC-FEE-10-A26")
def test_duplicate_payment_without_key_creates_two(admin, w1, year_id):
    t = w1["tuition"]["id"]
    a = h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")])).json()
    b = h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")])).json()
    assert a["transaction_id"] != b["transaction_id"]
    assert a["receipt_number"] != b["receipt_number"]
    assert h.summary_item(admin, w1["student"], year_id, t)["due_amount"] == "6000.00"


@pytest.mark.tc("TC-FEE-10-A26")
def test_idempotency_key_returns_original(admin, w1, year_id):
    t = w1["tuition"]["id"]
    key = unique("idem")
    a = h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")], idempotency_key=key)).json()
    b = h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")], idempotency_key=key)).json()
    assert a["transaction_id"] == b["transaction_id"]
    assert a["transaction_number"] == b["transaction_number"]
    assert a["receipt_number"] == b["receipt_number"] and a["receipt_id"] == b["receipt_id"]
    assert [i["fee_type_id"] for i in a["items_paid"]] == [i["fee_type_id"] for i in b["items_paid"]]
    assert h.summary_item(admin, w1["student"], year_id, t)["due_amount"] == "9000.00"
    history = h.ok(admin.get(f"{C}/history/{w1['student']['id']}", params={"academic_year_id": year_id})).json()
    assert len(history["items"]) == 1


@pytest.mark.tc("TC-FEE-10-A26")
def test_idempotency_key_too_long(admin, w1, year_id):
    r = h.pay(admin, w1["student"], year_id, "100.00", [(w1["tuition"]["id"], "100.00")], idempotency_key="k" * 65)
    assert r.status_code == 422


@pytest.mark.tc("TC-FEE-10-A27")
def test_second_full_payment_rejected(admin, w1, year_id):
    t = w1["tuition"]["id"]
    h.ok(h.pay(admin, w1["student"], year_id, "12000.00", [(t, "12000.00")]))
    r = h.pay(admin, w1["student"], year_id, "12000.00", [(t, "12000.00")])
    assert r.status_code == 400
    assert "No outstanding dues for this student" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-10-A28")
def test_pending_cheque_does_not_block_cash(admin, w1, year_id):
    t = w1["tuition"]["id"]
    h.ok(h.pay(admin, w1["student"], year_id, "12000.00", [(t, "12000.00")], method="cheque", **cheque_kwargs()))
    h.ok(h.pay(admin, w1["student"], year_id, "12000.00", [(t, "12000.00")]))
    assert h.summary_item(admin, w1["student"], year_id, t)["due_amount"] == "0.00"


def parallel_pay(token, student, year_id, bodies):
    def call(extra):
        client = Api(token=token)
        try:
            return h.pay(client, student, year_id, extra["amount"], extra.get("items"), **extra.get("kw", {}))
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=len(bodies)) as pool:
        return list(pool.map(call, bodies))


@pytest.mark.tc("TC-FEE-10-A29")
def test_parallel_identical_full_due(logins, admin, w1, year_id):
    t = w1["tuition"]["id"]
    bodies = [{"amount": "12000.00", "items": [(t, "12000.00")]}] * 2
    results = parallel_pay(logins["admin"]["access_token"], w1["student"], year_id, bodies)
    assert sorted(r.status_code for r in results) == [200, 400]
    item = h.summary_item(admin, w1["student"], year_id, t)
    assert item["paid_amount"] == "12000.00" and item["due_amount"] == "0.00"
    history = h.ok(admin.get(f"{C}/history/{w1['student']['id']}", params={"academic_year_id": year_id})).json()
    assert len(history["items"]) == 1


@pytest.mark.tc("TC-FEE-10-A29")
def test_parallel_payments_never_exceed_due(logins, admin, w1, year_id):
    t = w1["tuition"]["id"]
    bodies = [{"amount": "3000.00", "items": [(t, "3000.00")]}] * 6
    results = parallel_pay(logins["admin"]["access_token"], w1["student"], year_id, bodies)
    ok_results = [r for r in results if r.status_code == 200]
    assert len(ok_results) == 4
    assert all(r.status_code == 400 for r in results if r.status_code != 200)
    receipts = [r.json()["receipt_number"] for r in ok_results]
    assert len(set(receipts)) == 4 and all(RECEIPT_RE.match(x) for x in receipts)
    assert len({r.json()["transaction_id"] for r in ok_results}) == 4
    item = h.summary_item(admin, w1["student"], year_id, t)
    assert item["paid_amount"] == "12000.00" and item["due_amount"] == "0.00"


@pytest.mark.tc("TC-FEE-10-A29")
def test_parallel_oversized_payments(logins, admin, w1, year_id):
    t = w1["tuition"]["id"]
    bodies = [{"amount": "8000.00", "items": [(t, "8000.00")]}] * 2
    results = parallel_pay(logins["admin"]["access_token"], w1["student"], year_id, bodies)
    assert sorted(r.status_code for r in results) == [200, 400]
    assert h.summary_item(admin, w1["student"], year_id, t)["paid_amount"] == "8000.00"


@pytest.mark.tc("TC-FEE-10-A29")
def test_parallel_same_idempotency_key(logins, admin, w1, year_id):
    t = w1["tuition"]["id"]
    key = unique("idem")
    bodies = [{"amount": "3000.00", "items": [(t, "3000.00")], "kw": {"idempotency_key": key}}] * 3
    results = parallel_pay(logins["admin"]["access_token"], w1["student"], year_id, bodies)
    good = [r for r in results if r.status_code == 200]
    assert good
    assert len({r.json()["transaction_id"] for r in good}) == 1
    assert h.summary_item(admin, w1["student"], year_id, t)["paid_amount"] == "3000.00"


@pytest.mark.tc("TC-FEE-10-A30")
def test_parallel_payments_different_students_get_distinct_receipts(logins, admin, cleanup, year_id, fee_world, new_student):
    t = fee_world["tuition"]["id"]
    students = [new_student() for _ in range(4)]
    for s in students:
        h.map_student(admin, cleanup, year_id, s, t, "12000.00")

    def call(s):
        client = Api(token=logins["admin"]["access_token"])
        try:
            return h.pay(client, s, year_id, "1000.00", [(t, "1000.00")])
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(call, students))
    assert [r.status_code for r in results] == [200] * 4
    numbers = [r.json()["receipt_number"] for r in results]
    assert len(set(numbers)) == 4 and all(RECEIPT_RE.match(n) for n in numbers)


@pytest.mark.tc("TC-FEE-10-A30")
def test_receipt_numbers_increase(admin, w1, year_id):
    t = w1["tuition"]["id"]
    numbers = [h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")])).json()["receipt_number"] for _ in range(3)]
    parts = [RECEIPT_RE.match(n) for n in numbers]
    assert all(parts) and len({p.group(1) for p in parts}) == 1
    seq = [int(p.group(2)) for p in parts]
    assert seq == sorted(seq) and len(set(seq)) == 3


@pytest.mark.tc("TC-FEE-10-A31")
def test_client_receipt_number_ignored(admin, w1, year_id):
    r = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(w1["tuition"]["id"], "1000.00")], receipt_number="MY-OWN-1"))
    assert RECEIPT_RE.match(r.json()["receipt_number"])


@pytest.mark.tc("TC-FEE-10-A32")
def test_unknown_payment_method(admin, w1, year_id):
    r = h.pay(admin, w1["student"], year_id, "1000.00", [(w1["tuition"]["id"], "1000.00")], method="wallet")
    assert r.status_code == 422


@pytest.mark.tc("TC-FEE-10-A32")
def test_pay_body_validation(admin, w1, year_id):
    t = w1["tuition"]["id"]
    s = w1["student"]
    assert h.pay(admin, s, year_id, "0").status_code == 422
    assert h.pay(admin, s, year_id, "-5").status_code == 422
    assert h.pay(admin, s, year_id, "100.005").status_code == 422
    assert h.pay(admin, s, year_id, "3500.00", [(t, "3000.00")]).status_code == 422
    assert h.pay(admin, s, year_id, "100.00", []).status_code == 422
    assert h.pay(admin, s, year_id, "200.00", [(t, "100.00"), (t, "100.00")]).status_code == 422


@pytest.mark.tc("TC-FEE-10-A33")
def test_refund_does_not_reduce_paid(admin, w1, year_id):
    t = w1["tuition"]["id"]
    paid = h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")])).json()
    refund = h.ok(
        admin.post(
            "/fee/refunds/",
            json={"fee_transaction_id": paid["transaction_id"], "refund_amount": "1000.00", "refund_reason": "excess_payment"},
        ),
        201,
    ).json()
    h.ok(admin.post("/fee/refunds/approve", json={"refund_id": refund["id"], "action": "approve", "approval_remarks": "ok"}))
    h.ok(admin.post("/fee/refunds/process", json={"refund_id": refund["id"], "refund_method": "cash", "processing_remarks": "done"}))
    item = h.summary_item(admin, w1["student"], year_id, t)
    assert item["paid_amount"] == "3000.00" and item["due_amount"] == "9000.00"


@pytest.mark.tc("TC-FEE-10-A34")
@pytest.mark.parametrize("role", ROLES)
def test_pay_role_matrix(role, role_clients, admin, w1, year_id):
    r = h.pay(role_clients[role], w1["student"], year_id, "100.00", [(w1["tuition"]["id"], "100.00")])
    assert r.status_code == (200 if role == "admin" else 403)


@pytest.mark.tc("TC-FEE-10-A35")
def test_pay_no_token_header_isolation(anon, mismatched_admin, tenant_b, w1, year_id):
    t = w1["tuition"]["id"]
    assert h.pay(anon, w1["student"], year_id, "100.00", [(t, "100.00")]).status_code == 401
    assert h.pay(mismatched_admin, w1["student"], year_id, "100.00", [(t, "100.00")]).status_code == 403
    r = h.pay(tenant_b, w1["student"], tenant_b.academic_year_id, "100.00")
    assert r.status_code == 404
    assert "No fee mappings found" in h.detail_text(r)
