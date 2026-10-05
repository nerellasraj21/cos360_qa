import uuid

import pytest

from api_tests.expense.helpers import ROLES, make_category, make_txn, make_type, other_tenant_header

BASE = "/expense/audit/"


@pytest.fixture
def txn(admin, cleanup):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    return make_txn(admin, cleanup, expense_type["id"])


@pytest.mark.api
@pytest.mark.tc("TC-EXP-15-A01")
def test_writes_do_not_create_audit_rows(admin, cleanup, txn):
    admin.put(f"/expense/transactions/{txn['id']}", json={"description": "audited?"})
    response = admin.get(f"{BASE}logs", params={"transaction_id": txn["id"]})
    assert response.status_code == 200
    assert response.json() == []
    category = make_category(admin, cleanup)
    scoped = admin.get(f"{BASE}logs", params={"action": "create", "limit": 500})
    assert scoped.status_code == 200
    assert category["id"] not in [row.get("entity_id") for row in scoped.json()]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-15-A02")
def test_logs_limit_bounds(admin):
    assert admin.get(f"{BASE}logs", params={"action": "create", "limit": 500}).status_code == 200
    assert admin.get(f"{BASE}logs", params={"limit": 501}).status_code == 422
    assert admin.get(f"{BASE}logs", params={"limit": 0}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-15-A03")
def test_unknown_log(admin):
    response = admin.get(f"{BASE}logs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Audit log not found"
    assert admin.get(f"{BASE}logs/not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-15-A04")
def test_transaction_logs_have_no_existence_check(admin, txn):
    assert admin.get(f"{BASE}transactions/{txn['id']}/logs").json() == []
    assert admin.get(f"{BASE}transactions/{uuid.uuid4()}/logs").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-EXP-15-A05")
def test_transaction_audit_summary(admin, txn):
    response = admin.get(f"{BASE}transactions/{txn['id']}/summary")
    assert response.status_code == 200
    assert response.json() == {
        "transaction_id": txn["id"],
        "total_entries": 0,
        "action_breakdown": {},
        "first_entry": None,
        "last_entry": None,
        "unique_actors": 0,
    }


@pytest.mark.api
@pytest.mark.tc("TC-EXP-15-A06")
def test_delete_log_forbidden_for_admin(admin):
    response = admin.delete(f"{BASE}logs/{uuid.uuid4()}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Only administrators can delete audit logs"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-15-A07")
@pytest.mark.skip(reason="needs a direct database insert of an audit row; tests may not touch the database directly")
def test_inserted_audit_row_is_readable():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXP-15-A08")
@pytest.mark.parametrize("role", ROLES)
def test_role_matrix(role_clients, txn, role):
    expected = 200 if role == "admin" else 403
    client = role_clients[role]
    assert client.get(f"{BASE}logs").status_code == expected
    assert client.get(f"{BASE}transactions/{txn['id']}/logs").status_code == expected
    assert client.get(f"{BASE}transactions/{txn['id']}/summary").status_code == expected
    assert client.get(f"{BASE}logs/{uuid.uuid4()}").status_code == (404 if role == "admin" else 403)


@pytest.mark.api
@pytest.mark.tc("TC-EXP-15-A08")
def test_unauthenticated(anon):
    assert anon.get(f"{BASE}logs").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXP-15-A09")
def test_tenant_isolation(admin, tenant_b, txn):
    assert tenant_b.get(f"{BASE}logs", params={"transaction_id": txn["id"]}).json() == []
    assert tenant_b.get(f"{BASE}transactions/{txn['id']}/summary").json()["total_entries"] == 0
    assert other_tenant_header(admin).get(f"{BASE}logs").status_code == 403
