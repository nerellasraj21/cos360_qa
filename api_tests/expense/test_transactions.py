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
    txn_body,
)
from api_tests.support import items_of, unique

BASE = "/expense/transactions/"


@pytest.fixture
def expense_type(admin, cleanup):
    category = make_category(admin, cleanup)
    return make_type(admin, cleanup, category["id"])


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A01")
def test_create_cash_transaction(admin, cleanup, expense_type, logins):
    body = txn_body(expense_type["id"], "500.00", "2026-09-01")
    response = admin.post(BASE, json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "pending"
    assert data["requires_approval"] is False
    assert data["version"] == 1
    assert data["created_by_role"] == "Admin"
    assert data["amount"] == "500.00"
    assert data["org_id"] == logins["admin"]["tenant_id"]
    assert data["idempotency_key"] == body["idempotency_key"]
    assert data["expense_type_id"] == expense_type["id"]
    assert data["approved_at"] is None and data["approved_by_user_id"] is None
    assert admin.get(f"{BASE}{data['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A02")
def test_staff_creates_transaction(staff, admin, cleanup, expense_type):
    response = staff.post(BASE, json=txn_body(expense_type["id"]))
    assert response.status_code == 201, response.text
    assert response.json()["created_by_role"] == "Staff"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A03")
@pytest.mark.parametrize("role", ["teacher", "student", "parent"])
def test_other_roles_cannot_create(role_clients, expense_type, role):
    assert role_clients[role].post(BASE, json=txn_body(expense_type["id"])).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A04")
def test_create_unauthenticated(anon, expense_type):
    assert anon.post(BASE, json=txn_body(expense_type["id"])).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A05")
def test_duplicate_idempotency_key(admin, cleanup, expense_type):
    body = txn_body(expense_type["id"])
    first = admin.post(BASE, json=body)
    assert first.status_code == 201
    cleanup_id = first.json()["id"]
    assert admin.get(f"{BASE}{cleanup_id}").status_code == 200
    second = admin.post(BASE, json=body)
    assert second.status_code == 400
    assert second.json()["detail"]["error_code"] == "DUPLICATE_IDEMPOTENCY_KEY"
    rows = items_of(admin.get(BASE, params={"expense_type_id": expense_type["id"]}))
    assert len(rows) == 1


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A06")
@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.pop("expense_type_id"),
        lambda b: b.pop("idempotency_key"),
        lambda b: b.update(amount="-1"),
        lambda b: b.update(amount="10.123"),
        lambda b: b.update(description="d" * 501),
        lambda b: b.update(description=""),
        lambda b: b.update(reference_number="r" * 101),
        lambda b: b.update(vendor_name="v" * 201),
        lambda b: b.update(idempotency_key=""),
        lambda b: b.update(idempotency_key="k" * 101),
        lambda b: b.pop("transaction_date"),
    ],
    ids=[
        "no_type",
        "no_key",
        "negative",
        "three_decimals",
        "desc_501",
        "desc_empty",
        "ref_101",
        "vendor_201",
        "key_empty",
        "key_101",
        "no_date",
    ],
)
def test_create_validation(admin, expense_type, mutate):
    body = txn_body(expense_type["id"])
    mutate(body)
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A07")
def test_create_unknown_type(admin):
    response = admin.post(BASE, json=txn_body(str(uuid.uuid4())))
    assert response.status_code == 404
    assert "Expense type not found" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A08")
def test_create_with_inactive_type(admin, cleanup, expense_type):
    admin.put(f"/expense/types/{expense_type['id']}", json={"is_active": False})
    response = admin.post(BASE, json=txn_body(expense_type["id"]))
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "INACTIVE_EXPENSE_TYPE"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A09")
def test_create_with_department(admin, cleanup, expense_type):
    department = make_department(admin, cleanup)
    data = make_txn(admin, cleanup, expense_type["id"], department_id=department["id"])
    assert data["department_id"] == department["id"]
    assert admin.get(f"{BASE}{data['id']}").json()["department_id"] == department["id"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A10")
def test_create_with_bad_department(admin, cleanup, expense_type):
    unknown = admin.post(BASE, json=txn_body(expense_type["id"], department_id=str(uuid.uuid4())))
    assert unknown.status_code == 404
    assert "Expense department not found" in unknown.text
    department = make_department(admin, cleanup)
    admin.delete(f"/expense/departments/{department['id']}")
    inactive = admin.post(BASE, json=txn_body(expense_type["id"], department_id=department["id"]))
    assert inactive.status_code == 400
    assert inactive.json()["detail"]["error_code"] == "INACTIVE_DEPARTMENT"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A11")
def test_create_zero_amount(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "0.00")
    assert data["amount"] == "0.00"
    assert data["requires_approval"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A12")
def test_create_amount_upper_bound(admin, cleanup, expense_type):
    window = Window()
    data = make_txn(admin, cleanup, expense_type["id"], "99999999.99", window.day(1, 5))
    assert data["amount"] == "99999999.99"
    over = admin.post(BASE, json=txn_body(expense_type["id"], "100000000.00", window.day(1, 6)))
    assert over.status_code >= 400


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A13")
def test_create_long_payment_method(admin, expense_type):
    response = admin.post(BASE, json=txn_body(expense_type["id"], payment_method="NEFT_TRANSFER_REFERENCE"))
    assert response.status_code >= 400


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A14")
def test_create_without_academic_year(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"])
    assert data["academic_year_id"] is None
    assert admin.get(f"{BASE}{data['id']}").json()["academic_year_id"] is None


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A15")
def test_create_with_academic_year(admin, cleanup, expense_type, academic_year_id):
    data = make_txn(admin, cleanup, expense_type["id"], academic_year_id=academic_year_id)
    assert data["academic_year_id"] == academic_year_id


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A16")
def test_idempotency_key_is_per_tenant(admin, tenant_b, cleanup, expense_type):
    key = unique("exp_idem_")
    first = admin.post(BASE, json=txn_body(expense_type["id"], idempotency_key=key))
    assert first.status_code == 201
    category_b = tenant_b.post("/expense/categories/", json={"name": unique("exp_cat_")})
    assert category_b.status_code == 201, category_b.text
    cleanup.delete_later(tenant_b, f"/expense/categories/{category_b.json()['id']}")
    type_b = tenant_b.post(
        "/expense/types/", json={"name": unique("exp_typ_"), "category_id": category_b.json()["id"]}
    )
    assert type_b.status_code == 201, type_b.text
    cleanup.delete_later(tenant_b, f"/expense/types/{type_b.json()['id']}")
    second = tenant_b.post(BASE, json=txn_body(type_b.json()["id"], idempotency_key=key))
    assert second.status_code == 201, second.text


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A17")
def test_tenant_b_cannot_use_type_of_a(admin, tenant_b, expense_type):
    response = tenant_b.post(BASE, json=txn_body(expense_type["id"]))
    assert response.status_code == 404
    assert "Expense type not found" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-EXP-06-A04")
def test_token_with_other_tenant_header(admin, tenant_b, expense_type):
    mismatched = other_tenant_header(admin)
    assert mismatched.post(BASE, json=txn_body(expense_type["id"])).status_code == 403
    assert mismatched.get(BASE).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXP-01-A01")
def test_default_list_limit_is_100(admin):
    default = admin.get(BASE)
    assert default.status_code == 200
    assert len(default.json()) <= 100
    wide = admin.get(BASE, params={"limit": 1000}).json()
    if len(wide) > 100:
        assert len(default.json()) == 100
    one = admin.get(BASE, params={"limit": 1}).json()
    assert len(one) == min(1, len(wide))


@pytest.mark.api
@pytest.mark.tc("TC-EXP-01-A02")
def test_overview_lists_are_arrays(admin):
    for path in ("/expense/categories/", "/expense/types/", BASE):
        response = admin.get(path)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.api
@pytest.mark.tc("TC-EXP-07-A01")
def test_list_newest_first(admin, cleanup, expense_type):
    created = [make_txn(admin, cleanup, expense_type["id"]) for _ in range(3)]
    rows = items_of(admin.get(BASE, params={"expense_type_id": expense_type["id"]}))
    assert [row["id"] for row in rows] == [row["id"] for row in reversed(created)]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-07-A02")
def test_list_status_filter(admin, cleanup, expense_type):
    pending = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    approved = make_txn(admin, cleanup, expense_type["id"], "1600.00")
    assert admin.post(f"{BASE}{approved['id']}/approval", json={"action": "approve", "approval_comment": "ok"}).status_code == 200
    scope = {"expense_type_id": expense_type["id"]}
    pending_ids = [r["id"] for r in items_of(admin.get(BASE, params={**scope, "status_filter": "pending"}))]
    approved_ids = [r["id"] for r in items_of(admin.get(BASE, params={**scope, "status_filter": "approved"}))]
    assert pending_ids == [pending["id"]]
    assert approved_ids == [approved["id"]]
    bogus = admin.get(BASE, params={**scope, "status_filter": "bogus"})
    assert bogus.status_code == 200 and bogus.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-EXP-07-A03")
def test_list_type_filter(admin, cleanup, expense_type):
    other = make_type(admin, cleanup, expense_type["category_id"])
    mine = make_txn(admin, cleanup, expense_type["id"])
    make_txn(admin, cleanup, other["id"])
    rows = items_of(admin.get(BASE, params={"expense_type_id": expense_type["id"]}))
    assert [row["id"] for row in rows] == [mine["id"]]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-07-A04")
def test_list_department_filter_ignored(admin, cleanup, expense_type):
    department = make_department(admin, cleanup)
    with_dep = make_txn(admin, cleanup, expense_type["id"], department_id=department["id"])
    without = make_txn(admin, cleanup, expense_type["id"])
    rows = items_of(admin.get(BASE, params={"expense_type_id": expense_type["id"], "department_id": department["id"]}))
    assert {row["id"] for row in rows} == {with_dep["id"], without["id"]}


@pytest.mark.api
@pytest.mark.tc("TC-EXP-07-A05")
def test_list_pagination_bounds(admin, cleanup, expense_type):
    for _ in range(3):
        make_txn(admin, cleanup, expense_type["id"])
    page = admin.get(BASE, params={"expense_type_id": expense_type["id"], "limit": 2, "skip": 1})
    assert page.status_code == 200 and len(page.json()) == 2
    assert admin.get(BASE, params={"limit": 0}).status_code == 422
    assert admin.get(BASE, params={"limit": 1001}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-07-A06")
def test_get_transaction(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"])
    fetched = admin.get(f"{BASE}{data['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == data
    missing = admin.get(f"{BASE}{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Expense transaction not found"
    assert admin.get(f"{BASE}not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-07-A07")
def test_response_shape(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "12.50")
    assert isinstance(data["amount"], str) and Decimal(data["amount"]) == Decimal("12.50")
    assert isinstance(data["requires_approval"], bool)
    for key in ("approved_by_user_id", "approved_by_role", "approved_at", "approval_comment"):
        assert data[key] is None
    for key in ("id", "org_id", "status", "version", "created_at", "updated_at", "transaction_date"):
        assert key in data


@pytest.mark.api
@pytest.mark.tc("TC-EXP-07-A08")
@pytest.mark.parametrize("role", ROLES)
def test_role_matrix_list_and_get(role_clients, admin, cleanup, expense_type, role):
    data = make_txn(admin, cleanup, expense_type["id"])
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get(BASE).status_code == expected
    assert client.get(f"{BASE}{data['id']}").status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-EXP-07-A09")
def test_tenant_isolation_list_and_get(admin, tenant_b, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"])
    rows = items_of(tenant_b.get(BASE, params={"limit": 1000}))
    assert data["id"] not in [row["id"] for row in rows]
    assert tenant_b.get(f"{BASE}{data['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXP-08-A01")
def test_update_pending_transaction(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"])
    response = admin.put(f"{BASE}{data['id']}", json={"description": "changed", "vendor_name": "new vendor"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["description"] == "changed" and body["vendor_name"] == "new vendor"
    assert body["status"] == "pending"
    assert body["version"] == 1
    assert body["amount"] == data["amount"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-08-A02")
def test_update_approved_transaction(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    admin.post(f"{BASE}{data['id']}/approval", json={"action": "approve", "approval_comment": "ok"})
    response = admin.put(f"{BASE}{data['id']}", json={"description": "late edit"})
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "TRANSACTION_ALREADY_APPROVED"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-08-A03")
def test_update_rejected_transaction(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    admin.post(f"{BASE}{data['id']}/approval", json={"action": "reject", "approval_comment": "no"})
    response = admin.put(f"{BASE}{data['id']}", json={"description": "fixed"})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-08-A04")
def test_update_amount_recalculates_approval(admin, cleanup, expense_type):
    window = Window()
    data = make_txn(admin, cleanup, expense_type["id"], "500.00", window.day(2, 3))
    assert data["requires_approval"] is False
    raised = admin.put(f"{BASE}{data['id']}", json={"amount": "1500.00"})
    assert raised.status_code == 200
    assert raised.json()["requires_approval"] is True
    queue = admin.get(f"{BASE}pending/approval").json()
    assert data["id"] in [row["id"] for row in queue]
    lowered = admin.put(f"{BASE}{data['id']}", json={"amount": "100.00"})
    assert lowered.json()["requires_approval"] is False
    queue = admin.get(f"{BASE}pending/approval").json()
    assert data["id"] not in [row["id"] for row in queue]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-08-A05")
def test_update_ignores_key_and_status(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"])
    response = admin.put(
        f"{BASE}{data['id']}", json={"idempotency_key": unique("exp_new_"), "status": "approved", "description": "d2"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["idempotency_key"] == data["idempotency_key"]
    assert body["status"] == "pending"
    assert body["description"] == "d2"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-08-A06")
def test_update_with_inactive_department(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"])
    department = make_department(admin, cleanup)
    admin.delete(f"/expense/departments/{department['id']}")
    response = admin.put(f"{BASE}{data['id']}", json={"department_id": department["id"]})
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "INACTIVE_DEPARTMENT"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-08-A07")
def test_update_unknown_and_malformed(admin):
    missing = admin.put(f"{BASE}{uuid.uuid4()}", json={"description": "x"})
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Expense transaction not found"
    assert admin.put(f"{BASE}not-a-uuid", json={"description": "x"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-08-A08")
@pytest.mark.parametrize("role", forbidden_roles(["admin"]))
def test_update_denied_roles(role_clients, admin, cleanup, expense_type, role):
    data = make_txn(admin, cleanup, expense_type["id"])
    assert role_clients[role].put(f"{BASE}{data['id']}", json={"description": "x"}).status_code == 403
    assert admin.get(f"{BASE}{data['id']}").json()["description"] == data["description"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-08-A08")
def test_update_negative_amount_rejected(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"])
    assert admin.put(f"{BASE}{data['id']}", json={"amount": "-5"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-08-A09")
def test_update_tenant_isolation(admin, tenant_b, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"])
    assert tenant_b.put(f"{BASE}{data['id']}", json={"description": "hijack"}).status_code == 404
    assert admin.get(f"{BASE}{data['id']}").json()["description"] == data["description"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-09-A01")
def test_admin_delete_not_routed(admin, cleanup, expense_type):
    data = make_txn(admin, cleanup, expense_type["id"])
    response = admin.delete(f"{BASE}{data['id']}")
    assert response.status_code == 405
    assert admin.get(f"{BASE}{data['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXP-09-A02")
@pytest.mark.parametrize("role", ["staff", "teacher"])
def test_other_roles_delete_not_2xx(role_clients, admin, cleanup, expense_type, role):
    data = make_txn(admin, cleanup, expense_type["id"])
    response = role_clients[role].delete(f"{BASE}{data['id']}")
    assert response.status_code in (403, 405)
    assert admin.get(f"{BASE}{data['id']}").status_code == 200
