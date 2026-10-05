import uuid

import pytest

from api_tests.fee import helpers as h
from api_tests.support import unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
P = "/fee/old-fees"


def rid():
    return str(uuid.uuid4())


def old_body(student, label="2024-25", name="Tuition Fee", original="1500.00", paid="600.00", **extra):
    body = {
        "student_id": student["id"],
        "academic_year_label": label,
        "fee_type_name": name,
        "original_amount": original,
        "paid_amount": paid,
    }
    body.update(extra)
    return body


def make_old(admin, cleanup, student, **kw):
    r = h.ok(admin.post(f"{P}/", json=old_body(student, **kw)), 201)
    cleanup.delete_later(admin, f"{P}/{r.json()['id']}")
    return r.json()


@pytest.mark.tc("TC-FEE-08-A01")
def test_old_fee_create(admin, cleanup, new_student):
    s = new_student()
    row = make_old(admin, cleanup, s)
    assert row["outstanding"] == "900.00"
    assert row["original_amount"] == "1500.00" and row["paid_amount"] == "600.00"
    assert row["is_settled"] is False
    assert row["source"] == "manual_entry"
    assert row["academic_year_label"] == "2024-25" and row["fee_type_name"] == "Tuition Fee"


@pytest.mark.tc("TC-FEE-08-A02")
def test_old_fee_paid_equals_original_is_settled(admin, cleanup, new_student):
    row = make_old(admin, cleanup, new_student(), paid="1500.00")
    assert row["is_settled"] is True
    assert h.D(row["outstanding"]) == 0


@pytest.mark.tc("TC-FEE-08-A03")
def test_old_fee_duplicate(admin, cleanup, new_student):
    s = new_student()
    make_old(admin, cleanup, s)
    r = admin.post(f"{P}/", json=old_body(s))
    assert r.status_code == 400
    assert "Old fee record for 2024-25 / Tuition Fee already exists for this student" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-08-A04")
def test_old_fee_student_without_admission(admin):
    r = admin.post(f"{P}/", json=old_body({"id": rid()}))
    assert r.status_code == 404
    assert "Student admission not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-08-A05")
def test_old_fee_paid_above_original(admin, new_student):
    assert admin.post(f"{P}/", json=old_body(new_student(), paid="1600.00")).status_code == 422


@pytest.mark.tc("TC-FEE-08-A05")
def test_old_fee_field_validation(admin, new_student):
    s = new_student()
    assert admin.post(f"{P}/", json=old_body(s, original="0")).status_code == 422
    assert admin.post(f"{P}/", json=old_body(s, paid="-1")).status_code == 422
    assert admin.post(f"{P}/", json=old_body(s, label="2024-25" + "x" * 20)).status_code == 422


def carry_setup(admin, cleanup, year_id, fee_world, student, tuition_paid, lab_paid):
    t = fee_world["tuition"]["id"]
    lab = fee_world["lab"]["id"]
    h.map_student(admin, cleanup, year_id, student, t, "12000.00")
    h.map_student(admin, cleanup, year_id, student, lab, "999.99")
    if tuition_paid:
        h.ok(h.pay(admin, student, year_id, tuition_paid, [(t, tuition_paid)]))
    if lab_paid:
        h.ok(h.pay(admin, student, year_id, lab_paid, [(lab, lab_paid)]))


def carry(admin, student, year_id, target=None):
    return admin.post(
        f"{P}/carry-forward",
        json={"student_id": student["id"], "source_academic_year_id": year_id, "target_academic_year_id": target or year_id},
    )


@pytest.mark.tc("TC-FEE-08-A06")
def test_old_fee_carry_forward(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    carry_setup(admin, cleanup, year_id, fee_world, s, "9000.00", "999.99")
    r = h.ok(carry(admin, s, year_id))
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["fee_type_name"] == fee_world["tuition"]["type_name"]
    assert rows[0]["original_amount"] == "3000.00"
    assert rows[0]["source"] == "auto_carryforward"


@pytest.mark.tc("TC-FEE-08-A07")
def test_old_fee_carry_forward_twice(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    carry_setup(admin, cleanup, year_id, fee_world, s, "9000.00", None)
    h.ok(carry(admin, s, year_id))
    r = carry(admin, s, year_id)
    assert r.status_code == 400
    assert "Old fees already carried forward for this student and source academic year" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-08-A08")
def test_old_fee_carry_forward_all_paid(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    t = fee_world["tuition"]["id"]
    h.map_student(admin, cleanup, year_id, s, t, "12000.00")
    h.ok(h.pay(admin, s, year_id, "12000.00", [(t, "12000.00")]))
    assert h.ok(carry(admin, s, year_id)).json() == []
    assert h.ok(carry(admin, s, year_id)).json() == []


@pytest.mark.tc("TC-FEE-08-A09")
def test_old_fee_student_list_and_filter(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    make_old(admin, cleanup, s, label="2022-23", name="Lab Fee", original="400.00", paid="0")
    make_old(admin, cleanup, s, label="2024-25", name="Tuition Fee", original="1500.00", paid="600.00")
    t = fee_world["tuition"]["id"]
    h.map_student(admin, cleanup, year_id, s, t, "12000.00")
    h.ok(h.pay(admin, s, year_id, "9000.00", [(t, "9000.00")]))
    h.ok(carry(admin, s, year_id))
    data = h.ok(admin.get(f"{P}/student/{s['id']}")).json()
    assert len(data["items"]) == 3
    labels = [i["academic_year_label"] for i in data["items"]]
    assert labels == sorted(labels, reverse=True)
    assert data["grand_total_original"] == "4900.00"
    assert data["grand_total_paid"] == "600.00"
    assert data["grand_total_outstanding"] == "4300.00"
    filtered = h.ok(admin.get(f"{P}/student/{s['id']}", params={"current_year_id": year_id})).json()
    assert [i["source"] for i in filtered["items"]] == ["auto_carryforward"]
    assert filtered["grand_total_original"] == "3000.00"


@pytest.mark.tc("TC-FEE-08-A10")
def test_old_fee_list_unknown_student(admin):
    r = admin.get(f"{P}/student/{rid()}")
    assert r.status_code == 404
    assert "Student not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-08-A11")
def test_old_fee_get(admin, cleanup, new_student):
    row = make_old(admin, cleanup, new_student())
    assert h.ok(admin.get(f"{P}/{row['id']}")).json()["id"] == row["id"]
    r = admin.get(f"{P}/{rid()}")
    assert r.status_code == 404
    assert "Old fee record not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-08-A12")
def test_old_fee_put_paid_settles(admin, cleanup, new_student):
    row = make_old(admin, cleanup, new_student())
    r = h.ok(admin.put(f"{P}/{row['id']}", json={"paid_amount": "1500.00", "paid_date": "2026-10-01"}))
    assert r.json()["is_settled"] is True
    assert r.json()["paid_date"] == "2026-10-01"
    lower = h.ok(admin.put(f"{P}/{row['id']}", json={"paid_amount": "1000.00"}))
    assert lower.json()["is_settled"] is False


@pytest.mark.tc("TC-FEE-08-A13")
def test_old_fee_put_paid_above_original(admin, cleanup, new_student):
    row = make_old(admin, cleanup, new_student())
    r = admin.put(f"{P}/{row['id']}", json={"paid_amount": "1500.01"})
    assert r.status_code == 400
    assert "paid_amount cannot exceed original_amount" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-08-A14")
def test_old_fee_put_only_remarks(admin, cleanup, new_student):
    row = make_old(admin, cleanup, new_student())
    r = h.ok(admin.put(f"{P}/{row['id']}", json={"remarks": "checked by office"}))
    assert r.json()["remarks"] == "checked by office"
    assert r.json()["paid_amount"] == "600.00" and r.json()["original_amount"] == "1500.00"
    assert r.json()["is_settled"] is False


@pytest.mark.tc("TC-FEE-08-A15")
def test_old_fee_settle(admin, cleanup, year_id, new_student, fee_world):
    s = new_student()
    row = make_old(admin, cleanup, s)
    before = h.ok(h.summary(admin, s, year_id)).json()
    assert before["old_fee_pending_amount"] in ("900", "900.00")
    r = h.ok(admin.patch(f"{P}/{row['id']}/settle"))
    assert r.json() == {"detail": "Old fee marked as settled", "old_fee_id": row["id"]}
    got = h.ok(admin.get(f"{P}/{row['id']}")).json()
    assert got["is_settled"] is True
    assert got["outstanding"] == "900.00" and got["paid_amount"] == "600.00"
    after = h.ok(h.summary(admin, s, year_id)).json()
    assert h.D(after["old_fee_pending_amount"]) == 0


@pytest.mark.tc("TC-FEE-08-A16")
def test_old_fee_delete_rules(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    manual = h.ok(admin.post(f"{P}/", json=old_body(s)), 201).json()
    r = h.ok(admin.delete(f"{P}/{manual['id']}"))
    assert r.json() == {"detail": "Old fee record deleted", "old_fee_id": manual["id"]}
    assert admin.get(f"{P}/{manual['id']}").status_code == 404
    t = fee_world["tuition"]["id"]
    h.map_student(admin, cleanup, year_id, s, t, "12000.00")
    h.ok(h.pay(admin, s, year_id, "9000.00", [(t, "9000.00")]))
    cf = h.ok(carry(admin, s, year_id)).json()[0]
    r = admin.delete(f"{P}/{cf['id']}")
    assert r.status_code == 400
    assert "Only manually entered old fees can be deleted. Auto carry-forward records cannot be deleted." in h.detail_text(r)


@pytest.mark.tc("TC-FEE-08-A17")
def test_old_fee_pending_in_summary(admin, cleanup, year_id, new_student):
    s = new_student()
    make_old(admin, cleanup, s, label="2023-24", name="Lab Fee", original="1500.00", paid="600.00")
    make_old(admin, cleanup, s, label="2024-25", name="Tuition Fee", original="400.00", paid="0")
    settled = make_old(admin, cleanup, s, label="2022-23", name="Bus Fee", original="500.00", paid="0")
    h.ok(admin.patch(f"{P}/{settled['id']}/settle"))
    data = h.ok(h.summary(admin, s, year_id)).json()
    assert data["old_fee_pending_amount"] in ("1300", "1300.00")
    assert h.D(data["old_fee_pending_amount"]) == h.D("1300.00")


@pytest.mark.tc("TC-FEE-08-A18")
def test_payment_reduces_old_fee_after_current_dues(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    t = fee_world["tuition"]["id"]
    h.map_student(admin, cleanup, year_id, s, t, "12000.00")
    old = make_old(admin, cleanup, s, label="2024-25", name="Tuition Fee", original="900.00", paid="0")
    r = h.ok(h.pay(admin, s, year_id, "12900.00"))
    data = r.json()
    names = [i["fee_type_name"] for i in data["items_paid"]]
    assert "Old: Tuition Fee (2024-25)" in names
    assert h.D(sum(h.D(i["amount_paid"]) for i in data["items_paid"] if i["fee_type_name"].startswith("Old:"))) == h.D("900.00")
    item = h.summary_item(admin, s, year_id, t)
    assert item["due_amount"] == "0.00"
    got = h.ok(admin.get(f"{P}/{old['id']}")).json()
    assert got["paid_amount"] == "900.00" and got["is_settled"] is True
    assert got["receipt_system"] == data["receipt_number"]
    assert got["paid_date"]


@pytest.mark.tc("TC-FEE-08-A19")
@pytest.mark.parametrize("role", ROLES)
def test_old_fee_write_matrix(role, role_clients, admin, cleanup, year_id, new_student):
    client = role_clients[role]
    allowed = role == "admin"
    s = new_student()
    r = client.post(f"{P}/", json=old_body(s))
    if allowed:
        h.ok(r, 201)
        cleanup.delete_later(admin, f"{P}/{r.json()['id']}")
        row = r.json()
    else:
        assert r.status_code == 403
        row = make_old(admin, cleanup, s)
    r = client.post(
        f"{P}/carry-forward",
        json={"student_id": s["id"], "source_academic_year_id": year_id, "target_academic_year_id": year_id},
    )
    assert r.status_code == (200 if allowed else 403)
    r = client.put(f"{P}/{row['id']}", json={"remarks": "matrix check"})
    assert r.status_code == (200 if allowed else 403)
    r = client.patch(f"{P}/{row['id']}/settle")
    assert r.status_code == (200 if allowed else 403)
    r = client.delete(f"{P}/{row['id']}")
    assert r.status_code == (200 if allowed else 403)


@pytest.mark.tc("TC-FEE-08-A20")
@pytest.mark.parametrize("role", ROLES)
def test_old_fee_read_matrix(role, role_clients, admin, cleanup, new_student):
    s = new_student()
    row = make_old(admin, cleanup, s)
    client = role_clients[role]
    expected = 200 if role == "admin" else 403
    assert client.get(f"{P}/student/{s['id']}").status_code == expected
    assert client.get(f"{P}/{row['id']}").status_code == expected


@pytest.mark.tc("TC-FEE-08-A21")
def test_old_fee_no_token_header_isolation(anon, mismatched_admin, tenant_b, admin, cleanup, new_student):
    s = new_student()
    row = make_old(admin, cleanup, s)
    assert anon.get(f"{P}/{row['id']}").status_code == 401
    assert anon.get(f"{P}/student/{s['id']}").status_code == 401
    assert anon.post(f"{P}/", json=old_body(s, label=unique("L"))).status_code == 401
    assert mismatched_admin.get(f"{P}/{row['id']}").status_code == 403
    assert tenant_b.get(f"{P}/{row['id']}").status_code == 404
    assert tenant_b.get(f"{P}/student/{s['id']}").status_code == 404
