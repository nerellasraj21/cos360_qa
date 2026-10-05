import uuid

import pytest

from api_tests.expense.helpers import (
    ROLES,
    forbidden_roles,
    make_category,
    make_txn,
    make_type,
    other_tenant_header,
)
from api_tests.support import items_of, unique

BASE = "/expense/types/"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A01")
def test_create_type(admin, cleanup):
    category = make_category(admin, cleanup)
    name = unique("exp_typ_")
    response = admin.post(BASE, json={"name": name, "category_id": category["id"], "description": "Power"})
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}{data['id']}")
    assert data["name"] == name
    assert data["category_id"] == category["id"]
    assert data["is_active"] is True
    assert data["id"] and data["created_at"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A02")
def test_create_type_unauthenticated(anon):
    assert anon.post(BASE, json={"name": "x", "category_id": str(uuid.uuid4())}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A02")
@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.pop("category_id"),
        lambda b: b.update(name="n" * 101),
        lambda b: b.update(description="d" * 301),
    ],
    ids=["missing_category", "name_101", "description_301"],
)
def test_create_type_validation(admin, cleanup, mutate):
    category = make_category(admin, cleanup)
    body = {"name": unique("exp_typ_"), "category_id": category["id"]}
    mutate(body)
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A03")
def test_create_type_unknown_category(admin):
    response = admin.post(BASE, json={"name": unique("exp_typ_"), "category_id": str(uuid.uuid4())})
    assert response.status_code == 404
    assert "Expense category not found" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A04")
def test_create_type_in_inactive_category(admin, cleanup):
    category = make_category(admin, cleanup)
    admin.delete(f"/expense/categories/{category['id']}")
    response = admin.post(BASE, json={"name": unique("exp_typ_"), "category_id": category["id"]})
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "INACTIVE_CATEGORY"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A05")
def test_duplicate_type_name_in_category(admin, cleanup):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    response = admin.post(BASE, json={"name": expense_type["name"], "category_id": category["id"]})
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "DUPLICATE_TYPE_NAME"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A06")
def test_same_type_name_in_two_categories(admin, cleanup):
    first = make_category(admin, cleanup)
    second = make_category(admin, cleanup)
    name = unique("exp_typ_")
    make_type(admin, cleanup, first["id"], name=name)
    make_type(admin, cleanup, second["id"], name=name)


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A07")
def test_list_types_by_category(admin, cleanup):
    first = make_category(admin, cleanup)
    second = make_category(admin, cleanup)
    mine = make_type(admin, cleanup, first["id"])
    other = make_type(admin, cleanup, second["id"])
    rows = items_of(admin.get(BASE, params={"category_id": first["id"], "limit": 1000}))
    ids = [row["id"] for row in rows]
    assert mine["id"] in ids and other["id"] not in ids
    assert all(row["category_id"] == first["id"] for row in rows)


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A08")
def test_type_dropdown(admin, cleanup):
    category = make_category(admin, cleanup)
    low = make_type(admin, cleanup, category["id"], name=unique("exp_typ_a_"))
    high = make_type(admin, cleanup, category["id"], name=unique("exp_typ_z_"))
    gone = make_type(admin, cleanup, category["id"])
    admin.delete(f"{BASE}{gone['id']}")
    response = admin.get(f"{BASE}dropdown", params={"category_id": category["id"]})
    assert response.status_code == 200
    rows = response.json()
    assert [row["id"] for row in rows] == [low["id"], high["id"]]
    assert set(rows[0]) >= {"id", "name", "category_id"}
    assert rows[0]["category_id"] == category["id"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A09")
def test_get_type(admin, cleanup):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    assert admin.get(f"{BASE}{expense_type['id']}").json()["name"] == expense_type["name"]
    missing = admin.get(f"{BASE}{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Expense type not found"
    assert admin.get(f"{BASE}not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A10")
def test_update_type(admin, cleanup):
    first = make_category(admin, cleanup)
    second = make_category(admin, cleanup)
    inactive = make_category(admin, cleanup)
    admin.delete(f"/expense/categories/{inactive['id']}")
    expense_type = make_type(admin, cleanup, first["id"])
    new_name = unique("exp_typ_")
    renamed = admin.put(f"{BASE}{expense_type['id']}", json={"name": new_name})
    assert renamed.status_code == 200 and renamed.json()["name"] == new_name
    moved = admin.put(f"{BASE}{expense_type['id']}", json={"category_id": second["id"]})
    assert moved.status_code == 200 and moved.json()["category_id"] == second["id"]
    rejected = admin.put(f"{BASE}{expense_type['id']}", json={"category_id": inactive["id"]})
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["error_code"] == "INACTIVE_CATEGORY"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A10")
def test_move_type_into_category_with_same_name(admin, cleanup):
    first = make_category(admin, cleanup)
    second = make_category(admin, cleanup)
    name = unique("exp_typ_")
    make_type(admin, cleanup, first["id"], name=name)
    other = make_type(admin, cleanup, second["id"], name=name)
    response = admin.put(f"{BASE}{other['id']}", json={"category_id": first["id"]})
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "DUPLICATE_TYPE_NAME"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A11")
def test_delete_unused_type(admin, cleanup):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    response = admin.delete(f"{BASE}{expense_type['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    ids = [row["id"] for row in items_of(admin.get(BASE, params={"category_id": category["id"]}))]
    assert expense_type["id"] not in ids
    dropdown = [row["id"] for row in admin.get(f"{BASE}dropdown", params={"category_id": category["id"]}).json()]
    assert expense_type["id"] not in dropdown


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A12")
def test_delete_type_with_transaction(admin, cleanup):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    make_txn(admin, cleanup, expense_type["id"])
    response = admin.delete(f"{BASE}{expense_type['id']}")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "TYPE_HAS_TRANSACTIONS"
    assert detail["details"]["transaction_count"] == 1
    assert admin.get(f"{BASE}{expense_type['id']}").json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A13")
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 1001}])
def test_list_types_bounds(admin, params):
    assert admin.get(BASE, params=params).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A14")
@pytest.mark.parametrize("role", ROLES)
def test_role_matrix_reads(role_clients, admin, cleanup, role):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get(BASE).status_code == expected
    assert client.get(f"{BASE}dropdown").status_code == expected
    assert client.get(f"{BASE}{expense_type['id']}").status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A14")
@pytest.mark.parametrize("role", forbidden_roles(["admin"]))
def test_role_matrix_writes_denied(role_clients, admin, cleanup, role):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    client = role_clients[role]
    assert client.post(BASE, json={"name": unique("exp_typ_"), "category_id": category["id"]}).status_code == 403
    assert client.put(f"{BASE}{expense_type['id']}", json={"description": "x"}).status_code == 403
    assert client.delete(f"{BASE}{expense_type['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A14")
def test_admin_writes_allowed(admin, cleanup):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    assert admin.put(f"{BASE}{expense_type['id']}", json={"description": "x"}).status_code == 200
    assert admin.delete(f"{BASE}{expense_type['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A15")
def test_tenant_isolation(admin, tenant_b, cleanup):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    listed = items_of(tenant_b.get(BASE, params={"limit": 1000}))
    assert expense_type["id"] not in [row["id"] for row in listed]
    assert tenant_b.get(f"{BASE}{expense_type['id']}").status_code == 404
    response = tenant_b.post(BASE, json={"name": unique("exp_typ_"), "category_id": category["id"]})
    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXP-03-A15")
def test_token_with_other_tenant_header(admin, tenant_b):
    assert other_tenant_header(admin).get(BASE).status_code == 403
