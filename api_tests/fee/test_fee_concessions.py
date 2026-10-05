import uuid

import pytest

from api_tests.fee import helpers as h

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
P = "/fee/concessions"


def rid():
    return str(uuid.uuid4())


def conc(type_id, amount="2000.00", reason="Sibling discount", approver="principal"):
    return {"fee_type_id": type_id, "concession_amount": amount, "reason": reason, "approved_by": approver}


def apply(admin, student, year_id, *items):
    return admin.post(
        f"{P}/bulk", json={"student_id": student["id"], "academic_year_id": year_id, "concessions": list(items)}
    )


def summary_row(admin, student, year_id, type_id):
    data = h.ok(admin.get(f"{P}/student/{student['id']}", params={"academic_year_id": year_id})).json()
    return data, next((i for i in data["items"] if i["fee_type_id"] == type_id), None)


@pytest.mark.tc("TC-FEE-07-A01")
def test_concession_apply(admin, w1, year_id):
    r = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"])), 201)
    row = r.json()[0]
    assert row["assigned_fee"] == "12000.00"
    assert row["concession_amount"] == "2000.00"
    assert row["is_active"] is True
    assert row["fee_type_name"] == w1["tuition"]["type_name"]
    assert row["reason"] == "Sibling discount" and row["approved_by"] == "principal"


@pytest.mark.tc("TC-FEE-07-A02")
def test_concession_reflected_in_fee_summary(admin, w1, year_id):
    h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"])), 201)
    item = h.summary_item(admin, w1["student"], year_id, w1["tuition"]["id"])
    assert item["assigned_fee"] == "12000.00"
    assert item["fee_after_concession"] == "10000.00"
    assert item["due_amount"] == "10000.00"


@pytest.mark.tc("TC-FEE-07-A03")
def test_concession_cumulative(admin, w1, year_id):
    first = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"])), 201).json()[0]
    second = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "1000.00")), 201).json()[0]
    assert second["id"] == first["id"]
    assert second["concession_amount"] == "3000.00"


@pytest.mark.tc("TC-FEE-07-A04")
def test_concession_exceeds_assigned_fee(admin, w1, year_id):
    h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "3000.00")), 201)
    r = apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "9500.00"))
    assert r.status_code == 400
    text = h.detail_text(r)
    assert "Concession amount 12500.00 (previous 3000.00 + new 9500.00) exceeds assigned fee 12000.00" in text
    assert f"fee_type_id={w1['tuition']['id']}" in text
    _, row = summary_row(admin, w1["student"], year_id, w1["tuition"]["id"])
    assert row["concession_amount"] == "3000.00"


@pytest.mark.tc("TC-FEE-07-A05")
def test_concession_equal_to_full_fee(admin, w1, year_id):
    h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "12000.00")), 201)
    item = h.summary_item(admin, w1["student"], year_id, w1["tuition"]["id"])
    assert item["fee_after_concession"] == "0.00"
    assert item["due_amount"] == "0.00"


@pytest.mark.tc("TC-FEE-07-A06")
def test_concession_unmapped_fee_type(admin, w1, year_id, fee_world):
    r = apply(admin, w1["student"], year_id, conc(fee_world["lab"]["id"]))
    assert r.status_code == 404
    assert f"Fee mapping not found for fee_type_id={fee_world['lab']['id']}" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-07-A07")
def test_concession_invalid_approver(admin, w1, year_id):
    r = apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], approver="trustee"))
    assert r.status_code == 400
    assert "Invalid approver 'trustee'. Must be one of:" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-07-A08")
def test_concession_short_reason(admin, w1, year_id):
    assert apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], reason="abcd")).status_code == 422


@pytest.mark.tc("TC-FEE-07-A09")
def test_concession_bulk_is_atomic(admin, w1, year_id, fee_world):
    r = apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "1000.00"), conc(fee_world["lab"]["id"], "100.00"))
    assert r.status_code == 404
    _, row = summary_row(admin, w1["student"], year_id, w1["tuition"]["id"])
    assert h.D(row["concession_amount"]) == 0


@pytest.mark.tc("TC-FEE-07-A10")
def test_concession_three_decimals_rejected(admin, w1, year_id):
    assert apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "100.555")).status_code == 422


@pytest.mark.tc("TC-FEE-07-A10")
def test_concession_empty_list_and_zero_rejected(admin, w1, year_id):
    assert apply(admin, w1["student"], year_id).status_code == 422
    assert apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "0")).status_code == 422


@pytest.mark.tc("TC-FEE-07-A11")
def test_concession_summary(admin, w1, year_id):
    h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"])), 201)
    h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "1000.00")), 201)
    data, row = summary_row(admin, w1["student"], year_id, w1["tuition"]["id"])
    assert row["assigned_fee"] == "12000.00"
    assert row["concession_amount"] == "3000.00"
    assert row["due_amount"] == "9000.00"
    assert row["due_date"] == "2027-03-10"
    assert row["is_settled"] is False
    assert data["grand_total_assigned"] == "12000.00"
    assert data["grand_total_concession"] == "3000.00"
    assert data["grand_total_fee_after_concession"] == "9000.00"


@pytest.mark.tc("TC-FEE-07-A12")
def test_concession_summary_requires_year(admin, w1):
    assert admin.get(f"{P}/student/{w1['student']['id']}").status_code == 422


@pytest.mark.tc("TC-FEE-07-A13")
def test_concession_summary_unknown_student(admin, year_id):
    r = admin.get(f"{P}/student/{rid()}", params={"academic_year_id": year_id})
    assert r.status_code == 404
    assert "Student not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-07-A14")
def test_concession_history(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    h.map_student(admin, cleanup, year_id, s, fee_world["tuition"]["id"], "12000.00")
    h.map_student(admin, cleanup, year_id, s, fee_world["lab"]["id"], "1000.00")
    first = h.ok(apply(admin, s, year_id, conc(fee_world["tuition"]["id"], "500.00")), 201).json()[0]
    second = h.ok(apply(admin, s, year_id, conc(fee_world["lab"]["id"], "100.00")), 201).json()[0]
    h.ok(admin.delete(f"{P}/{second['id']}"))
    rows = h.ok(admin.get(f"{P}/history/{s['id']}", params={"academic_year_id": year_id})).json()
    assert len(rows) == 2
    assert {r["id"] for r in rows} == {first["id"], second["id"]}
    assert rows[0]["id"] == second["id"]
    assert set(rows[0]) >= {"id", "date_applied", "fee_type_name", "amount", "reason", "approver", "recorded_by_staff_name"}
    assert rows[0]["amount"] == "100.00"


@pytest.mark.tc("TC-FEE-07-A15")
def test_concession_get(admin, w1, year_id):
    c = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"])), 201).json()[0]
    r = h.ok(admin.get(f"{P}/{c['id']}"))
    assert r.json()["fee_type_name"] == w1["tuition"]["type_name"]
    r = admin.get(f"{P}/{rid()}")
    assert r.status_code == 404
    assert "Concession not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-07-A16")
def test_concession_put_replaces_amount(admin, w1, year_id):
    c = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "3000.00")), 201).json()[0]
    r = h.ok(admin.put(f"{P}/{c['id']}", json={"concession_amount": "1500.00"}))
    assert r.json()["concession_amount"] == "1500.00"
    assert h.ok(admin.get(f"{P}/{c['id']}")).json()["concession_amount"] == "1500.00"


@pytest.mark.tc("TC-FEE-07-A17")
def test_concession_put_above_assigned(admin, w1, year_id):
    c = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"])), 201).json()[0]
    r = admin.put(f"{P}/{c['id']}", json={"concession_amount": "12000.01"})
    assert r.status_code == 400
    assert "Concession amount cannot exceed assigned fee 12000.00" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-07-A18")
def test_concession_put_reason_and_approver_only(admin, w1, year_id):
    c = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"])), 201).json()[0]
    r = h.ok(admin.put(f"{P}/{c['id']}", json={"reason": "Updated reason text", "approved_by": "owner"}))
    assert r.json()["concession_amount"] == "2000.00"
    assert r.json()["approved_by"] == "owner" and r.json()["reason"] == "Updated reason text"
    assert admin.put(f"{P}/{c['id']}", json={"approved_by": "trustee"}).status_code == 400


@pytest.mark.tc("TC-FEE-07-A19")
def test_concession_revoke(admin, w1, year_id):
    c = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"])), 201).json()[0]
    r = h.ok(admin.delete(f"{P}/{c['id']}"))
    assert r.json() == {"detail": "Concession revoked", "concession_id": c["id"]}
    assert h.ok(admin.get(f"{P}/{c['id']}")).json()["is_active"] is False
    item = h.summary_item(admin, w1["student"], year_id, w1["tuition"]["id"])
    assert item["fee_after_concession"] == "12000.00" and item["due_amount"] == "12000.00"
    _, row = summary_row(admin, w1["student"], year_id, w1["tuition"]["id"])
    assert h.D(row["concession_amount"]) == 0


@pytest.mark.tc("TC-FEE-07-A20")
def test_concession_revoke_twice(admin, w1, year_id):
    c = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"])), 201).json()[0]
    h.ok(admin.delete(f"{P}/{c['id']}"))
    h.ok(admin.delete(f"{P}/{c['id']}"))


@pytest.mark.tc("TC-FEE-07-A21")
def test_concession_reactivation_resets_amount(admin, w1, year_id):
    c = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"])), 201).json()[0]
    h.ok(admin.delete(f"{P}/{c['id']}"))
    again = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "500.00")), 201).json()[0]
    assert again["id"] == c["id"]
    assert again["is_active"] is True
    assert again["concession_amount"] == "500.00"


@pytest.mark.tc("TC-FEE-07-A22")
def test_payment_limit_uses_payable(admin, w2, year_id):
    t = w2["tuition"]["id"]
    r = h.pay(admin, w2["student"], year_id, "6000.01", [(t, "6000.01")])
    assert r.status_code == 400
    h.ok(h.pay(admin, w2["student"], year_id, "6000.00", [(t, "6000.00")]))
    item = h.summary_item(admin, w2["student"], year_id, t)
    assert item["due_amount"] == "0.00"
    assert item["paid_amount"] == "10000.00"


@pytest.mark.tc("TC-FEE-07-A23")
@pytest.mark.parametrize("role", ROLES)
def test_concession_write_matrix(role, role_clients, admin, year_id, w1):
    client = role_clients[role]
    allowed = role == "admin"
    t = w1["tuition"]["id"]
    r = client.post(
        f"{P}/bulk",
        json={"student_id": w1["student"]["id"], "academic_year_id": year_id, "concessions": [conc(t, "100.00")]},
    )
    assert r.status_code == (201 if allowed else 403)
    c = h.ok(apply(admin, w1["student"], year_id, conc(t, "100.00")), 201).json()[0]
    r = client.put(f"{P}/{c['id']}", json={"reason": "Matrix update check"})
    assert r.status_code == (200 if allowed else 403)
    r = client.delete(f"{P}/{c['id']}")
    assert r.status_code == (200 if allowed else 403)


@pytest.mark.tc("TC-FEE-07-A24")
@pytest.mark.parametrize("role", ROLES)
def test_concession_read_matrix(role, role_clients, admin, year_id, w1):
    c = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "100.00")), 201).json()[0]
    client = role_clients[role]
    expected = 200 if role == "admin" else 403
    sid = w1["student"]["id"]
    assert client.get(f"{P}/student/{sid}", params={"academic_year_id": year_id}).status_code == expected
    assert client.get(f"{P}/history/{sid}", params={"academic_year_id": year_id}).status_code == expected
    assert client.get(f"{P}/{c['id']}").status_code == expected


@pytest.mark.tc("TC-FEE-07-A25")
def test_parent_cannot_read_child_concessions(parent, w1, year_id):
    r = parent.get(f"{P}/student/{w1['student']['id']}", params={"academic_year_id": year_id})
    assert r.status_code == 403


@pytest.mark.tc("TC-FEE-07-A26")
def test_concession_no_token_header_isolation(anon, mismatched_admin, tenant_b, admin, w1, year_id):
    c = h.ok(apply(admin, w1["student"], year_id, conc(w1["tuition"]["id"], "100.00")), 201).json()[0]
    sid = w1["student"]["id"]
    assert anon.get(f"{P}/student/{sid}", params={"academic_year_id": year_id}).status_code == 401
    assert anon.get(f"{P}/{c['id']}").status_code == 401
    assert anon.delete(f"{P}/{c['id']}").status_code == 401
    assert mismatched_admin.get(f"{P}/{c['id']}").status_code == 403
    assert tenant_b.get(f"{P}/{c['id']}").status_code == 404
    assert tenant_b.get(f"{P}/student/{sid}", params={"academic_year_id": tenant_b.academic_year_id}).status_code == 404
