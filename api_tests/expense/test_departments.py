import uuid

import pytest

from api_tests.expense.helpers import ROLES, forbidden_roles, make_department, other_tenant_header
from api_tests.support import items_of, unique

BASE = "/expense/departments/"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A01")
def test_create_department(admin, cleanup):
    name = unique("exp_dep_")
    response = admin.post(BASE, json={"name": name, "description": "Admin office"})
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}{data['id']}")
    assert data["name"] == name
    assert data["is_active"] is True
    assert data["id"] and data["created_at"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A02")
def test_duplicate_department_case_insensitive(admin, cleanup):
    department = make_department(admin, cleanup)
    response = admin.post(BASE, json={"name": f"  {department['name'].upper()} "})
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "DUPLICATE_DEPARTMENT_NAME"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A03")
@pytest.mark.parametrize("body", [{"name": ""}, {"name": "n" * 101}, {"name": "ok", "description": "d" * 301}])
def test_create_department_validation(admin, body):
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A04")
def test_list_departments_active_only(admin, cleanup):
    active = make_department(admin, cleanup)
    inactive = make_department(admin, cleanup)
    admin.delete(f"{BASE}{inactive['id']}")
    default_ids = [row["id"] for row in items_of(admin.get(BASE, params={"limit": 1000}))]
    assert active["id"] in default_ids and inactive["id"] not in default_ids
    all_rows = items_of(admin.get(BASE, params={"active_only": "false", "limit": 1000}))
    assert inactive["id"] in [row["id"] for row in all_rows]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A05")
def test_department_dropdown(admin, cleanup):
    low = make_department(admin, cleanup, name=unique("exp_dep_a_"))
    high = make_department(admin, cleanup, name=unique("exp_dep_z_"))
    gone = make_department(admin, cleanup)
    admin.delete(f"{BASE}{gone['id']}")
    response = admin.get(f"{BASE}dropdown")
    assert response.status_code == 200
    rows = response.json()
    ids = [row["id"] for row in rows]
    assert gone["id"] not in ids
    assert ids.index(low["id"]) < ids.index(high["id"])
    assert set(rows[0]) >= {"id", "name"}


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A06")
def test_get_department(admin, cleanup):
    department = make_department(admin, cleanup)
    assert admin.get(f"{BASE}{department['id']}").json()["name"] == department["name"]
    missing = admin.get(f"{BASE}{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Expense department not found"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A07")
def test_update_department(admin, cleanup):
    first = make_department(admin, cleanup)
    second = make_department(admin, cleanup)
    new_name = unique("exp_dep_")
    response = admin.put(f"{BASE}{first['id']}", json={"name": new_name, "description": "renamed"})
    assert response.status_code == 200
    assert response.json()["name"] == new_name and response.json()["description"] == "renamed"
    clash = admin.put(f"{BASE}{second['id']}", json={"name": new_name})
    assert clash.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A08")
def test_delete_department(admin, cleanup):
    department = make_department(admin, cleanup)
    response = admin.delete(f"{BASE}{department['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert department["id"] not in [row["id"] for row in admin.get(f"{BASE}dropdown").json()]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A09")
def test_recreate_deleted_department_name(admin, cleanup):
    department = make_department(admin, cleanup)
    admin.delete(f"{BASE}{department['id']}")
    response = admin.post(BASE, json={"name": department["name"]})
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{BASE}{response.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A10")
@pytest.mark.parametrize("role", ROLES)
def test_role_matrix_reads(role_clients, admin, cleanup, role):
    department = make_department(admin, cleanup)
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get(BASE).status_code == expected
    assert client.get(f"{BASE}dropdown").status_code == expected
    assert client.get(f"{BASE}{department['id']}").status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A10")
@pytest.mark.parametrize("role", forbidden_roles(["admin"]))
def test_role_matrix_writes_denied(role_clients, admin, cleanup, role):
    department = make_department(admin, cleanup)
    client = role_clients[role]
    assert client.post(BASE, json={"name": unique("exp_dep_")}).status_code == 403
    assert client.put(f"{BASE}{department['id']}", json={"description": "x"}).status_code == 403
    assert client.delete(f"{BASE}{department['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A10")
def test_admin_writes_allowed(admin, cleanup):
    department = make_department(admin, cleanup)
    assert admin.put(f"{BASE}{department['id']}", json={"description": "x"}).status_code == 200
    assert admin.delete(f"{BASE}{department['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A10")
def test_unauthenticated(anon):
    assert anon.get(BASE).status_code == 401
    assert anon.post(BASE, json={"name": "x"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXP-04-A11")
def test_tenant_isolation(admin, tenant_b, cleanup):
    department = make_department(admin, cleanup)
    listed = items_of(tenant_b.get(BASE, params={"limit": 1000}))
    assert department["id"] not in [row["id"] for row in listed]
    assert tenant_b.get(f"{BASE}{department['id']}").status_code == 404
    assert other_tenant_header(admin).get(BASE).status_code == 403
