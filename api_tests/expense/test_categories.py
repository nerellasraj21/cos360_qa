import uuid

import pytest

from api_tests.expense.helpers import ROLES, forbidden_roles, make_category, make_type, other_tenant_header
from api_tests.support import items_of, unique

BASE = "/expense/categories/"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A01")
def test_create_category(admin, cleanup):
    name = unique("exp_cat_")
    response = admin.post(BASE, json={"name": name, "description": "Buildings"})
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}{data['id']}")
    assert data["name"] == name
    assert data["description"] == "Buildings"
    assert data["is_active"] is True
    for key in ("id", "created_at", "updated_at"):
        assert data[key]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A02")
def test_create_category_unauthenticated(anon):
    assert anon.post(BASE, json={"name": unique("exp_cat_")}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A03")
@pytest.mark.parametrize(
    "body",
    [{"description": "x"}, {"name": "n" * 101}, {"name": "ok", "description": "d" * 301}],
    ids=["missing_name", "name_101", "description_301"],
)
def test_create_category_validation(admin, body):
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A03")
def test_create_category_name_100_accepted(admin, cleanup):
    prefix = unique("exp_c")
    name = prefix + "n" * (100 - len(prefix))
    assert len(name) == 100
    response = admin.post(BASE, json={"name": name})
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{BASE}{response.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A04")
def test_create_duplicate_category(admin, cleanup):
    category = make_category(admin, cleanup)
    response = admin.post(BASE, json={"name": category["name"]})
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "DUPLICATE_CATEGORY_NAME"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A05")
def test_list_categories_newest_first(admin, cleanup):
    first = make_category(admin, cleanup)
    second = make_category(admin, cleanup)
    third = make_category(admin, cleanup)
    inactive = make_category(admin, cleanup)
    admin.delete(f"{BASE}{inactive['id']}")
    response = admin.get(BASE, params={"limit": 1000})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    ids = [row["id"] for row in items_of(response)]
    assert inactive["id"] not in ids
    positions = [ids.index(item["id"]) for item in (third, second, first)]
    assert positions == sorted(positions)


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A06")
def test_list_categories_include_inactive(admin, cleanup):
    category = make_category(admin, cleanup)
    assert admin.delete(f"{BASE}{category['id']}").status_code == 200
    rows = items_of(admin.get(BASE, params={"active_only": "false", "limit": 1000}))
    match = [row for row in rows if row["id"] == category["id"]]
    assert match and match[0]["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A07")
def test_list_categories_pagination(admin, cleanup):
    for _ in range(3):
        make_category(admin, cleanup)
    page = admin.get(BASE, params={"limit": 2, "skip": 1})
    assert page.status_code == 200
    assert len(page.json()) == 2


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A07")
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 1001}, {"skip": -1}])
def test_list_categories_bounds(admin, params):
    assert admin.get(BASE, params=params).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A08")
def test_category_dropdown(admin, cleanup):
    low = make_category(admin, cleanup, name=unique("exp_cat_a_"))
    high = make_category(admin, cleanup, name=unique("exp_cat_z_"))
    gone = make_category(admin, cleanup)
    admin.delete(f"{BASE}{gone['id']}")
    response = admin.get(f"{BASE}dropdown")
    assert response.status_code == 200
    rows = response.json()
    assert all(set(row) >= {"id", "name"} for row in rows)
    ids = [row["id"] for row in rows]
    assert gone["id"] not in ids
    assert ids.index(low["id"]) < ids.index(high["id"])
    names = [row["name"] for row in rows]
    assert names == sorted(names)


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A09")
def test_get_category(admin, cleanup):
    category = make_category(admin, cleanup)
    inactive = make_category(admin, cleanup)
    admin.delete(f"{BASE}{inactive['id']}")
    assert admin.get(f"{BASE}{category['id']}").json()["name"] == category["name"]
    response = admin.get(f"{BASE}{inactive['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    missing = admin.get(f"{BASE}{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Expense category not found"
    assert admin.get(f"{BASE}not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A10")
def test_update_category(admin, cleanup):
    first = make_category(admin, cleanup)
    second = make_category(admin, cleanup)
    new_name = unique("exp_cat_")
    response = admin.put(f"{BASE}{first['id']}", json={"name": new_name})
    assert response.status_code == 200
    assert response.json()["name"] == new_name
    clash = admin.put(f"{BASE}{second['id']}", json={"name": new_name})
    assert clash.status_code == 400
    assert clash.json()["detail"]["error_code"] == "DUPLICATE_CATEGORY_NAME"
    assert admin.put(f"{BASE}{uuid.uuid4()}", json={"name": unique("exp_cat_")}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A11")
def test_deactivate_category_via_update(admin, cleanup):
    category = make_category(admin, cleanup)
    response = admin.put(f"{BASE}{category['id']}", json={"is_active": False})
    assert response.status_code == 200
    ids = [row["id"] for row in admin.get(f"{BASE}dropdown").json()]
    assert category["id"] not in ids


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A12")
def test_delete_category_is_soft(admin, cleanup):
    category = make_category(admin, cleanup)
    response = admin.delete(f"{BASE}{category['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert category["id"] not in [row["id"] for row in items_of(admin.get(BASE, params={"limit": 1000}))]
    assert category["id"] not in [row["id"] for row in admin.get(f"{BASE}dropdown").json()]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A13")
def test_delete_category_keeps_active_types(admin, cleanup):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    assert admin.delete(f"{BASE}{category['id']}").status_code == 200
    fetched = admin.get(f"/expense/types/{expense_type['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A14")
def test_recreate_deleted_category_name(admin, cleanup):
    category = make_category(admin, cleanup)
    admin.delete(f"{BASE}{category['id']}")
    response = admin.post(BASE, json={"name": category["name"]})
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{BASE}{response.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A15")
@pytest.mark.parametrize("role", ROLES)
def test_role_matrix_create(role_clients, admin, cleanup, role):
    response = role_clients[role].post(BASE, json={"name": unique("exp_cat_")})
    if role == "admin":
        assert response.status_code == 201
        cleanup.delete_later(admin, f"{BASE}{response.json()['id']}")
    else:
        assert response.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A16")
@pytest.mark.parametrize("role", ROLES)
def test_role_matrix_reads(role_clients, admin, cleanup, role):
    category = make_category(admin, cleanup)
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get(BASE).status_code == expected
    assert client.get(f"{BASE}dropdown").status_code == expected
    assert client.get(f"{BASE}{category['id']}").status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A17")
@pytest.mark.parametrize("role", forbidden_roles(["admin"]))
def test_role_matrix_update_delete_denied(role_clients, admin, cleanup, role):
    category = make_category(admin, cleanup)
    client = role_clients[role]
    assert client.put(f"{BASE}{category['id']}", json={"description": "changed"}).status_code == 403
    assert client.delete(f"{BASE}{category['id']}").status_code == 403
    assert admin.get(f"{BASE}{category['id']}").json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A17")
def test_admin_update_delete_allowed(admin, cleanup):
    category = make_category(admin, cleanup)
    assert admin.put(f"{BASE}{category['id']}", json={"description": "changed"}).status_code == 200
    assert admin.delete(f"{BASE}{category['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A18")
def test_tenant_isolation(admin, tenant_b, cleanup):
    category = make_category(admin, cleanup)
    listed = items_of(tenant_b.get(BASE, params={"limit": 1000}))
    assert category["id"] not in [row["id"] for row in listed]
    assert tenant_b.get(f"{BASE}{category['id']}").status_code == 404
    assert tenant_b.put(f"{BASE}{category['id']}", json={"description": "x"}).status_code == 404
    assert tenant_b.delete(f"{BASE}{category['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A19")
def test_token_with_other_tenant_header(admin, tenant_b):
    mismatched = other_tenant_header(admin)
    assert mismatched.get(BASE).status_code == 403
    assert mismatched.post(BASE, json={"name": unique("exp_cat_")}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXP-02-A02")
def test_no_token_and_no_tenant_header():
    from api_tests.support import Api

    assert Api().get(BASE).status_code == 400
