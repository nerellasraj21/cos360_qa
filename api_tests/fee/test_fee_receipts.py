import re
import uuid
from datetime import date, datetime, timedelta

import pytest

from api_tests.fee import helpers as h
from api_tests.support import items_of, unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
R = "/fee/receipts"
RECEIPT_RE = re.compile(r"^REC-(\d{4})-(\d{4})$")


def rid():
    return str(uuid.uuid4())


def cheque_kwargs():
    return {"cheque_number": "CHQ900", "cheque_bank": "Test Bank", "cheque_date": date.today().isoformat()}


@pytest.fixture
def paid(admin, w1, year_id):
    t = w1["tuition"]["id"]
    pay = h.ok(h.pay(admin, w1["student"], year_id, "3000.00", [(t, "3000.00")])).json()
    return {"pay": pay, "student": w1["student"], "tuition": w1["tuition"], "receipt_id": pay["receipt_id"], "txn_id": pay["transaction_id"]}


@pytest.fixture
def cleared_cheque(admin, w1, year_id):
    t = w1["tuition"]["id"]
    r = h.ok(h.pay(admin, w1["student"], year_id, "2000.00", [(t, "2000.00")], method="cheque", **cheque_kwargs())).json()
    h.ok(admin.put(f"/fee/transactions/{r['transaction_id']}", json={"status": "completed", "cheque_status": "cleared"}))
    return {"txn_id": r["transaction_id"], "student": w1["student"], "tuition": w1["tuition"]}


@pytest.mark.tc("TC-FEE-11-A01")
def test_generate_receipt_for_completed_transaction(admin, cleared_cheque):
    r = h.ok(admin.post(f"{R}/generate/{cleared_cheque['txn_id']}"), 201)
    data = r.json()
    assert RECEIPT_RE.match(data["receipt_number"])
    assert data["fee_transaction_id"] == cleared_cheque["txn_id"]
    assert data["content_hash"] and len(data["content_hash"]) == 64
    assert data["is_reprinted"] is False and data["reprint_count"] == 0
    assert data["student_admission_num"] == cleared_cheque["student"]["admission_number"]
    txn = admin.get(f"/fee/transactions/{cleared_cheque['txn_id']}").json()
    assert txn["receipt_generated"] is True and txn["receipt_number"] == data["receipt_number"]
    assert txn["receipt_hash"] == data["content_hash"]


@pytest.mark.tc("TC-FEE-11-A02")
def test_generate_receipt_twice(admin, cleared_cheque):
    h.ok(admin.post(f"{R}/generate/{cleared_cheque['txn_id']}"), 201)
    r = admin.post(f"{R}/generate/{cleared_cheque['txn_id']}")
    assert r.status_code == 400
    assert "Receipt already exists for this transaction" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-11-A03")
def test_generate_receipt_for_pending_transaction(admin, w1, year_id):
    t = w1["tuition"]["id"]
    r = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")], method="cheque", **cheque_kwargs())).json()
    g = admin.post(f"{R}/generate/{r['transaction_id']}")
    assert g.status_code == 400
    assert "Cannot generate receipt for non-completed transaction" in h.detail_text(g)


@pytest.mark.tc("TC-FEE-11-A04")
def test_generate_receipt_unknown_transaction(admin):
    missing = rid()
    r = admin.post(f"{R}/generate/{missing}")
    assert r.status_code == 404
    assert f"Transaction with ID {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-11-A05")
def test_cheque_flow_has_no_receipt_until_generated(admin, w1, year_id):
    t = w1["tuition"]["id"]
    r = h.ok(h.pay(admin, w1["student"], year_id, "1500.00", [(t, "1500.00")], method="cheque", **cheque_kwargs())).json()
    assert r["receipt_number"] == ""
    h.ok(admin.put(f"/fee/transactions/{r['transaction_id']}", json={"status": "completed", "cheque_status": "cleared"}))
    txn = admin.get(f"/fee/transactions/{r['transaction_id']}").json()
    assert txn["receipt_generated"] is False and txn["receipt_number"] is None
    g = h.ok(admin.post(f"{R}/generate/{r['transaction_id']}"), 201)
    assert RECEIPT_RE.match(g.json()["receipt_number"])


@pytest.mark.tc("TC-FEE-11-A06")
def test_get_receipt_enriches_fields(admin, paid, fee_world):
    data = h.ok(admin.get(f"{R}/{paid['receipt_id']}")).json()
    assert data["id"] == paid["receipt_id"]
    assert data["class_section"] == f"{fee_world['class']['name']} - " + next(
        n for n, i in fee_world["class"]["sections"].items() if i == paid["student"]["section_id"]
    )
    assert data["academic_year"]
    assert data["student_name"] == f"{paid['student']['first_name']} Tester"


@pytest.mark.tc("TC-FEE-11-A07")
def test_get_receipt_by_number(admin, paid):
    number = paid["pay"]["receipt_number"]
    assert h.ok(admin.get(f"{R}/number/{number}")).json()["id"] == paid["receipt_id"]
    r = admin.get(f"{R}/number/REC-0000-0000")
    assert r.status_code == 404
    assert "Receipt with number REC-0000-0000 not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-11-A08")
def test_get_unknown_receipt(admin):
    missing = rid()
    r = admin.get(f"{R}/{missing}")
    assert r.status_code == 404
    assert f"Receipt with ID {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-11-A09")
def test_receipt_content(admin, paid):
    c = h.ok(admin.get(f"{R}/{paid['receipt_id']}/content")).json()
    assert c["receipt_number"] == paid["pay"]["receipt_number"]
    assert c["transaction_number"] == paid["pay"]["transaction_number"]
    assert c["total_amount"] == "3000.00"
    assert [(i["fee_type_name"], i["amount_paid"]) for i in c["receipt_items"]] == [(paid["tuition"]["type_name"], "3000.00")]
    assert c["receipt_items"][0]["fee_term_name"]
    assert c["payment_method"] == "cash" and c["payment_reference"] is None
    assert c["school_name"] == "School Name" and c["school_address"] == "School Address"


@pytest.mark.tc("TC-FEE-11-A10")
def test_search_by_receipt_number_fragment(admin, paid):
    number = paid["pay"]["receipt_number"]
    rows = items_of(h.ok(admin.get(f"{R}/", params={"receipt_number": number.lower()[4:]})))
    assert paid["receipt_id"] in {r["id"] for r in rows}
    assert all(number.lower()[4:] in r["receipt_number"].lower() for r in rows)


@pytest.mark.tc("TC-FEE-11-A11")
def test_search_by_student_and_dates(admin, w1, year_id):
    t = w1["tuition"]["id"]
    a = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")])).json()
    b = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")])).json()
    today = date.today()
    rows = items_of(
        h.ok(admin.get(f"{R}/", params={"student_id": w1["student"]["id"], "date_from": today.isoformat(), "date_to": (today + timedelta(days=1)).isoformat()}))
    )
    assert [r["id"] for r in rows] == [b["receipt_id"], a["receipt_id"]]
    old = items_of(
        admin.get(f"{R}/", params={"student_id": w1["student"]["id"], "date_from": "2020-01-01", "date_to": "2020-01-02"})
    )
    assert old == []


@pytest.mark.tc("TC-FEE-11-A12")
def test_search_date_order_validation(admin):
    r = admin.get(f"{R}/", params={"date_from": "2026-10-02", "date_to": "2026-10-01"})
    assert r.status_code == 400
    assert "date_from must be before or equal to date_to" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-11-A13")
def test_search_limit_bound(admin):
    assert admin.get(f"{R}/", params={"limit": 501}).status_code == 422


@pytest.mark.tc("TC-FEE-11-A14")
def test_verify_untouched_receipt(admin, paid):
    v = h.ok(admin.get(f"{R}/{paid['receipt_id']}/verify")).json()
    assert v["is_valid"] is True and v["stored_hash"] == v["current_hash"]
    assert set(v) == {"receipt_id", "receipt_number", "is_valid", "stored_hash", "current_hash", "verification_date"}


@pytest.mark.tc("TC-FEE-11-A15")
def test_verify_after_student_rename(admin, paid):
    h.ok(admin.patch(f"/students/admission/{paid['student']['id']}", json={"first_name": "Renamed" + unique("")[:5]}))
    v = h.ok(admin.get(f"{R}/{paid['receipt_id']}/verify")).json()
    assert v["is_valid"] is False and v["stored_hash"] != v["current_hash"]


@pytest.mark.tc("TC-FEE-11-A16")
def test_verify_after_renumber(admin, paid):
    h.ok(admin.patch(f"{R}/{paid['receipt_id']}/number", json={"receipt_number": "REC-TEST-" + unique("")}))
    v = h.ok(admin.get(f"{R}/{paid['receipt_id']}/verify")).json()
    assert v["is_valid"] is False


@pytest.mark.tc("TC-FEE-11-A17")
def test_verify_unknown_receipt(admin):
    assert admin.get(f"{R}/{rid()}/verify").status_code == 404


@pytest.mark.tc("TC-FEE-11-A18")
def test_renumber_to_free_number(admin, paid):
    new = "REC-TEST-" + unique("")
    r = h.ok(admin.patch(f"{R}/{paid['receipt_id']}/number", json={"receipt_number": new}))
    assert r.json()["receipt_number"] == new
    assert h.ok(admin.get(f"{R}/number/{new}")).json()["id"] == paid["receipt_id"]


@pytest.mark.tc("TC-FEE-11-A19")
def test_renumber_to_used_number(admin, w1, year_id, paid):
    t = w1["tuition"]["id"]
    other = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")])).json()
    r = admin.patch(f"{R}/{paid['receipt_id']}/number", json={"receipt_number": other["receipt_number"]})
    assert r.status_code == 400
    assert f"Receipt number '{other['receipt_number']}' is already in use" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-11-A20")
def test_renumber_to_own_number(admin, paid):
    r = h.ok(admin.patch(f"{R}/{paid['receipt_id']}/number", json={"receipt_number": paid["pay"]["receipt_number"]}))
    assert r.json()["receipt_number"] == paid["pay"]["receipt_number"]


@pytest.mark.tc("TC-FEE-11-A21")
def test_non_numeric_suffix_does_not_break_numbering(admin, w1, year_id, paid):
    prefix = "REC-" + datetime.now().strftime("%y%m") + "-"
    h.ok(admin.patch(f"{R}/{paid['receipt_id']}/number", json={"receipt_number": prefix + "ABC"}))
    t = w1["tuition"]["id"]
    nxt = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")])).json()
    assert RECEIPT_RE.match(nxt["receipt_number"])
    h.ok(admin.patch(f"{R}/{paid['receipt_id']}/number", json={"receipt_number": "REC-TEST-" + unique("")}))


@pytest.mark.tc("TC-FEE-11-A22")
def test_reprint_counts(admin, paid):
    first = h.ok(admin.post(f"{R}/{paid['receipt_id']}/reprint")).json()
    assert first["is_reprinted"] is True and first["reprint_count"] == 1
    second = h.ok(admin.post(f"{R}/{paid['receipt_id']}/reprint")).json()
    assert second["reprint_count"] == 2


@pytest.mark.tc("TC-FEE-11-A23")
def test_reprint_unknown_receipt(admin):
    missing = rid()
    r = admin.post(f"{R}/{missing}/reprint")
    assert r.status_code == 404
    assert f"Receipt with ID {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-11-A24")
def test_receipt_pdf_download(admin, paid):
    r = h.ok(admin.get(f"/fee/collection/receipts/{paid['receipt_id']}/pdf"))
    assert r.headers["content-type"].startswith("application/pdf")
    assert f'filename="{paid["pay"]["receipt_number"]}.pdf"' in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF") and len(r.content) > 500


@pytest.mark.tc("TC-FEE-11-A27")
def test_receipt_pdf_unknown_receipt(admin):
    missing = rid()
    r = admin.get(f"/fee/collection/receipts/{missing}/pdf")
    assert r.status_code == 404
    assert f"Receipt with ID {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-11-A28")
def test_legacy_payment_receipt_items_less_than_total(admin, cleanup, year_id, fee_world, new_student):
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
    pay = h.ok(h.pay(admin, s, year_id, "12900.00")).json()
    content = h.ok(admin.get(f"{R}/{pay['receipt_id']}/content")).json()
    items_total = sum(h.D(i["amount_paid"]) for i in content["receipt_items"])
    assert h.D(content["total_amount"]) == h.D("12900.00")
    assert items_total == h.D("12000.00") < h.D(content["total_amount"])


@pytest.mark.tc("TC-FEE-11-A29")
def test_receipt_health(admin):
    assert h.ok(admin.get(f"{R}/health")).json()["module"] == "fee_receipts"


@pytest.mark.tc("TC-FEE-11-A30")
@pytest.mark.parametrize("role", ROLES)
def test_receipt_generate_matrix(role, role_clients, admin, w1, year_id):
    t = w1["tuition"]["id"]
    r = h.ok(h.pay(admin, w1["student"], year_id, "1000.00", [(t, "1000.00")], method="cheque", **cheque_kwargs())).json()
    h.ok(admin.put(f"/fee/transactions/{r['transaction_id']}", json={"status": "completed", "cheque_status": "cleared"}))
    g = role_clients[role].post(f"{R}/generate/{r['transaction_id']}")
    assert g.status_code == (201 if role in ("admin", "staff") else 403)


@pytest.mark.tc("TC-FEE-11-A31")
@pytest.mark.parametrize("role", ROLES)
def test_receipt_update_matrix(role, role_clients, paid):
    client = role_clients[role]
    allowed = role == "admin"
    assert client.post(f"{R}/{paid['receipt_id']}/reprint").status_code == (200 if allowed else 403)
    r = client.patch(f"{R}/{paid['receipt_id']}/number", json={"receipt_number": "REC-TEST-" + unique("")})
    assert r.status_code == (200 if allowed else 403)


@pytest.mark.tc("TC-FEE-11-A32")
@pytest.mark.parametrize("role", ROLES)
def test_receipt_read_matrix(role, role_clients, paid):
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get(f"{R}/{paid['receipt_id']}").status_code == expected
    assert client.get(f"{R}/number/{paid['pay']['receipt_number']}").status_code == expected
    assert client.get(f"{R}/{paid['receipt_id']}/content").status_code == expected
    assert client.get(f"{R}/{paid['receipt_id']}/verify").status_code == expected
    assert client.get(f"{R}/").status_code == expected


@pytest.mark.tc("TC-FEE-11-A33")
def test_receipt_no_token_header_isolation(anon, mismatched_admin, tenant_b, paid):
    rid_ = paid["receipt_id"]
    assert anon.get(f"{R}/{rid_}").status_code == 401
    assert anon.get(f"{R}/").status_code == 401
    assert anon.post(f"{R}/generate/{paid['txn_id']}").status_code == 401
    assert anon.get(f"/fee/collection/receipts/{rid_}/pdf").status_code == 401
    assert mismatched_admin.get(f"{R}/{rid_}").status_code == 403
    assert tenant_b.get(f"{R}/{rid_}").status_code == 404
    assert tenant_b.get(f"{R}/number/{paid['pay']['receipt_number']}").status_code == 404
    assert tenant_b.get(f"/fee/collection/receipts/{rid_}/pdf").status_code == 404
