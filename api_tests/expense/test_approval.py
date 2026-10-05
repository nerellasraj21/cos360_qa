import uuid

import pytest

from api_tests.expense.helpers import (
    ROLES,
    approve_body,
    forbidden_roles,
    make_category,
    make_txn,
    make_type,
    other_tenant_header,
)

BASE = "/expense/transactions/"


@pytest.fixture
def expense_type(admin, cleanup):
    category = make_category(admin, cleanup)
    return make_type(admin, cleanup, category["id"])


def _approval(client, transaction_id, **kwargs):
    return client.post(f"{BASE}{transaction_id}/approval", json=approve_body(**kwargs))


@pytest.mark.api
@pytest.mark.tc("TC-EXP-11-A01")
def test_threshold_exact_is_exempt(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1000.00")
    assert data["requires_approval"] is False
    assert data["status"] == "pending"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-11-A02")
def test_threshold_one_cent_over_requires_approval(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1000.01")
    assert data["requires_approval"] is True
    assert data["status"] == "pending"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-11-A03")
@pytest.mark.parametrize("method", ["check", "CHECK", "wire_transfer"])
def test_check_and_wire_require_approval(admin, cleanup, expense_type, method):
    data = make_txn(admin, cleanup, expense_type["id"], "5.00", payment_method=method)
    assert data["requires_approval"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXP-11-A04")
@pytest.mark.parametrize("method", ["cheque", "bank_transfer", "upi", "cash"])
def test_client_payment_methods_do_not_require_approval(admin, cleanup, expense_type, method):
    data = make_txn(admin, cleanup, expense_type["id"], "5.00", payment_method=method)
    assert data["requires_approval"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXP-11-A05")
def test_override_true_forces_approval(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "5.00", requires_approval_override=True)
    assert data["requires_approval"] is True
    assert data["requires_approval_override"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXP-11-A05")
def test_override_false_exempts_large_amount(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1000.01", requires_approval_override=False)
    assert data["requires_approval"] is False
    assert data["requires_approval_override"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXP-11-A06")
def test_exempt_transaction_cannot_be_approved(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "500.00")
    response = _approval(admin, data["id"])
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "TRANSACTION_NO_APPROVAL_REQUIRED"
    assert admin.get(f"{BASE}{data['id']}").json()["status"] == "pending"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-11-A07")
def test_status_never_paid_or_cancelled(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    seen = {data["status"]}
    seen.add(_approval(admin, data["id"], action="approve").json()["status"])
    seen.add(admin.put(f"{BASE}{data['id']}", json={"description": "x"}).json().get("status", "approved"))
    assert seen <= {"pending", "approved", "rejected"}
    for status in ("paid", "cancelled"):
        assert admin.get(BASE, params={"expense_type_id": expense_type["id"], "status_filter": status}).json() == []


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A01")
def test_approve_flagged_transaction(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    response = _approval(admin, data["id"], comment="OK")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert body["approved_by_role"] == "Admin"
    assert body["approved_at"] is not None
    assert body["approved_by_user_id"] is not None
    assert body["approval_comment"] == "OK"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A02")
def test_reject_flagged_transaction(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    response = _approval(admin, data["id"], action="reject", comment="too high")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["approval_comment"] == "too high"
    assert body["approved_at"] is not None


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A03")
def test_approve_twice(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    assert _approval(admin, data["id"]).status_code == 200
    second = _approval(admin, data["id"])
    assert second.status_code == 400
    detail = second.json()["detail"]
    assert detail["error_code"] == "TRANSACTION_NOT_PENDING"
    assert "approved" in detail["message"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A04")
def test_approve_rejected_transaction(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    _approval(admin, data["id"], action="reject")
    response = _approval(admin, data["id"], action="approve")
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "TRANSACTION_NOT_PENDING"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A05")
def test_approve_exempt_pending_transaction(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "500.00")
    response = _approval(admin, data["id"])
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "TRANSACTION_NO_APPROVAL_REQUIRED"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A06")
def test_invalid_action(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    response = _approval(admin, data["id"], action="bogus")
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "INVALID_APPROVAL_ACTION"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A07")
@pytest.mark.parametrize(
    "body",
    [
        {"action": "approve", "approval_comment": ""},
        {"action": "approve", "approval_comment": "c" * 501},
        {"approval_comment": "ok"},
        {"action": "approve"},
    ],
    ids=["empty_comment", "comment_501", "no_action", "no_comment"],
)
def test_approval_validation(admin, cleanup, expense_type, body):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    assert admin.post(f"{BASE}{data['id']}/approval", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A07")
def test_comment_500_accepted(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    assert _approval(admin, data["id"], comment="c" * 500).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A08")
def test_approval_unknown_and_malformed(admin):
    assert _approval(admin, uuid.uuid4()).status_code == 404
    assert _approval(admin, "not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A09")
def test_pending_queue_contents_and_order(admin, cleanup, expense_type):
    flagged_one = make_txn(admin, cleanup, expense_type["id"], "1200.00")
    flagged_two = make_txn(admin, cleanup, expense_type["id"], "1300.00")
    exempt = make_txn(admin, cleanup, expense_type["id"], "100.00")
    approved = make_txn(admin, cleanup, expense_type["id"], "1400.00")
    _approval(admin, approved["id"])
    response = admin.get(f"{BASE}pending/approval")
    assert response.status_code == 200
    rows = response.json()
    ids = [row["id"] for row in rows]
    assert exempt["id"] not in ids and approved["id"] not in ids
    assert ids.index(flagged_one["id"]) < ids.index(flagged_two["id"])
    assert all(row["status"] == "pending" and row["requires_approval"] is True for row in rows)


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A10")
def test_pending_queue_limit_not_applied(admin, cleanup, expense_type):
    first = make_txn(admin, cleanup, expense_type["id"], "1200.00")
    second = make_txn(admin, cleanup, expense_type["id"], "1300.00")
    rows = admin.get(f"{BASE}pending/approval", params={"limit": 1}).json()
    ids = [row["id"] for row in rows]
    assert first["id"] in ids and second["id"] in ids
    assert admin.get(f"{BASE}pending/approval", params={"limit": 0}).status_code == 422
    assert admin.get(f"{BASE}pending/approval", params={"limit": 501}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A11")
def test_edit_after_approval_blocked(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    _approval(admin, data["id"])
    response = admin.put(f"{BASE}{data['id']}", json={"description": "x"})
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "TRANSACTION_ALREADY_APPROVED"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A12")
@pytest.mark.parametrize("role", forbidden_roles(["admin"]))
def test_approve_denied_roles(role_clients, admin, cleanup, expense_type, role):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    assert _approval(role_clients[role], data["id"]).status_code == 403
    assert admin.get(f"{BASE}{data['id']}").json()["status"] == "pending"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A12")
def test_approve_unauthenticated(anon, admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    assert _approval(anon, data["id"]).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A13")
@pytest.mark.parametrize("role", ROLES)
def test_pending_queue_role_matrix(role_clients, role):
    expected = 200 if role in ("admin", "staff") else 403
    assert role_clients[role].get(f"{BASE}pending/approval").status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A14")
def test_creator_can_approve_own(admin, cleanup, expense_type, logins):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    assert data["created_by_user_id"]
    response = _approval(admin, data["id"])
    assert response.status_code == 200
    assert response.json()["approved_by_user_id"] == data["created_by_user_id"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-12-A15")
def test_approval_tenant_isolation(admin, tenant_b, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    assert _approval(tenant_b, data["id"]).status_code == 404
    assert admin.get(f"{BASE}{data['id']}").json()["status"] == "pending"
    assert _approval(other_tenant_header(admin), data["id"]).status_code == 403
