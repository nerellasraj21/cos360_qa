import pytest

from api_tests.masters.helpers import DENIED, RANDOM_ID, ROLES
from api_tests.support import QA_B_TENANT, unique

BASE = "/masters/locations"
READERS = ["admin", "staff", "teacher"]
NO_GRANT = ["student", "parent"]


def make_state(admin, cleanup, **over):
    body = {"name": unique("mststate"), "code": unique("c")[:6]}
    body.update(over)
    response = admin.post(f"{BASE}/states", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}/states/{data['id']}")
    return data


def make_district(admin, cleanup, state_id, **over):
    body = {"state_id": state_id, "name": unique("mstdist")}
    body.update(over)
    response = admin.post(f"{BASE}/districts", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}/districts/{data['id']}")
    return data


def make_mandal(admin, cleanup, district_id, **over):
    body = {"district_id": district_id, "name": unique("mstmand")}
    body.update(over)
    response = admin.post(f"{BASE}/mandals", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}/mandals/{data['id']}")
    return data


def tree(admin, cleanup):
    state = make_state(admin, cleanup)
    district = make_district(admin, cleanup, state["id"])
    mandal = make_mandal(admin, cleanup, district["id"])
    return state, district, mandal


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A01")
def test_create_state(admin, cleanup):
    body = {"name": unique("mststate"), "code": "QS"}
    response = admin.post(f"{BASE}/states", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}/states/{data['id']}")
    assert set(data) == {"id", "name", "code", "is_active"}
    assert data["name"] == body["name"] and data["code"] == "QS" and data["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A02")
def test_state_name_uniqueness(admin, cleanup):
    first = make_state(admin, cleanup)
    other = make_state(admin, cleanup)
    duplicate = admin.post(f"{BASE}/states", json={"name": first["name"]})
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == f"State name '{first['name']}' already exists"
    rename = admin.put(f"{BASE}/states/{other['id']}", json={"name": first["name"]})
    assert rename.status_code == 400
    assert rename.json()["detail"] == f"State name '{first['name']}' already exists"


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A03")
def test_list_states(admin, cleanup):
    active = make_state(admin, cleanup)
    inactive = make_state(admin, cleanup, is_active=False)
    response = admin.get(f"{BASE}/states?limit=1000")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"items", "total_count", "has_next"}
    ids = [i["id"] for i in data["items"]]
    assert active["id"] in ids and inactive["id"] in ids
    names = [i["name"] for i in data["items"]]
    assert names == sorted(names)
    only_active = admin.get(f"{BASE}/states?active_only=true&limit=1")
    assert only_active.status_code == 200
    assert len(only_active.json()["items"]) == 1
    assert all(i["is_active"] for i in only_active.json()["items"])
    everyone = admin.get(f"{BASE}/states?active_only=true&limit=1000").json()["items"]
    assert inactive["id"] not in [i["id"] for i in everyone]


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A04")
@pytest.mark.parametrize("query", ["limit=0", "limit=1001", "skip=-1"])
def test_state_list_bounds(admin, query):
    assert admin.get(f"{BASE}/states?{query}").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A05")
def test_states_dropdown_shape_and_filter(admin, cleanup):
    inactive = make_state(admin, cleanup, is_active=False)
    default = admin.get(f"{BASE}/states/dropdown")
    assert default.status_code == 200
    rows = default.json()
    assert all(set(r) == {"id", "name", "code"} for r in rows)
    assert inactive["id"] not in [r["id"] for r in rows]
    names = [r["name"] for r in rows]
    assert names == sorted(names)
    assert admin.get(f"{BASE}/states/dropdown?active_only=false").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A06")
def test_get_state(admin, cleanup):
    state = make_state(admin, cleanup)
    assert admin.get(f"{BASE}/states/{state['id']}").json() == state
    missing = admin.get(f"{BASE}/states/{RANDOM_ID}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == f"State with id {RANDOM_ID} not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A07")
def test_update_state(admin, cleanup):
    state = make_state(admin, cleanup)
    new = unique("mststate")
    response = admin.put(f"{BASE}/states/{state['id']}", json={"name": new, "is_active": False})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == new and data["is_active"] is False and data["code"] == state["code"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A08")
def test_delete_state(admin, cleanup):
    empty = admin.post(f"{BASE}/states", json={"name": unique("mststate")}).json()
    response = admin.delete(f"{BASE}/states/{empty['id']}")
    assert response.status_code == 200
    assert response.json() == {"message": "State deleted successfully"}
    assert admin.get(f"{BASE}/states/{empty['id']}").status_code == 404
    state = make_state(admin, cleanup)
    make_district(admin, cleanup, state["id"])
    blocked = admin.delete(f"{BASE}/states/{state['id']}")
    assert blocked.status_code == 400
    assert "has 1 district(s)" in blocked.json()["detail"]
    assert blocked.json()["detail"].endswith("Please delete districts first.")
    assert admin.delete(f"{BASE}/states/{RANDOM_ID}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A09")
def test_create_district(admin, cleanup):
    state = make_state(admin, cleanup)
    district = make_district(admin, cleanup, state["id"], code="QD")
    assert district["state_id"] == state["id"] and district["is_active"] is True and district["code"] == "QD"
    missing = admin.post(f"{BASE}/districts", json={"state_id": RANDOM_ID, "name": unique("mstdist")})
    assert missing.status_code == 404
    assert missing.json()["detail"] == f"State with id {RANDOM_ID} not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A10")
def test_district_lists_and_dropdown(admin, cleanup):
    state = make_state(admin, cleanup)
    active = make_district(admin, cleanup, state["id"])
    inactive = make_district(admin, cleanup, state["id"], is_active=False)
    full = admin.get(f"{BASE}/states/{state['id']}/districts")
    assert full.status_code == 200
    assert sorted(d["id"] for d in full.json()) == sorted([active["id"], inactive["id"]])
    dropdown = admin.get(f"{BASE}/states/{state['id']}/districts/dropdown")
    assert dropdown.status_code == 200
    assert dropdown.json() == [
        {"id": active["id"], "name": active["name"], "code": active["code"], "state_id": state["id"]}
    ]
    assert admin.get(f"{BASE}/states/{RANDOM_ID}/districts").status_code == 404
    unknown = admin.get(f"{BASE}/states/{RANDOM_ID}/districts/dropdown")
    assert unknown.status_code == 200 and unknown.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A11")
def test_get_update_district_and_reparent(admin, cleanup):
    s1 = make_state(admin, cleanup)
    s2 = make_state(admin, cleanup)
    district = make_district(admin, cleanup, s1["id"])
    assert admin.get(f"{BASE}/districts/{district['id']}").json() == district
    moved = admin.put(f"{BASE}/districts/{district['id']}", json={"state_id": s2["id"]})
    assert moved.status_code == 200 and moved.json()["state_id"] == s2["id"]
    bad = admin.put(f"{BASE}/districts/{district['id']}", json={"state_id": RANDOM_ID})
    assert bad.status_code == 404
    assert admin.get(f"{BASE}/districts/{RANDOM_ID}").status_code == 404
    assert admin.put(f"{BASE}/districts/{RANDOM_ID}", json={"name": "x"}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A12")
def test_delete_district(admin, cleanup):
    state = make_state(admin, cleanup)
    with_mandals = make_district(admin, cleanup, state["id"])
    make_mandal(admin, cleanup, with_mandals["id"])
    blocked = admin.delete(f"{BASE}/districts/{with_mandals['id']}")
    assert blocked.status_code == 400
    assert "has 1 mandal(s)" in blocked.json()["detail"]
    assert blocked.json()["detail"].endswith("Please delete mandals first.")
    empty = admin.post(f"{BASE}/districts", json={"state_id": state["id"], "name": unique("mstdist")}).json()
    ok = admin.delete(f"{BASE}/districts/{empty['id']}")
    assert ok.status_code == 200
    assert ok.json() == {"message": "District deleted successfully"}
    assert admin.delete(f"{BASE}/districts/{RANDOM_ID}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A13")
def test_create_mandal(admin, cleanup):
    state = make_state(admin, cleanup)
    district = make_district(admin, cleanup, state["id"])
    mandal = make_mandal(admin, cleanup, district["id"])
    assert mandal["district_id"] == district["id"] and mandal["is_active"] is True
    assert set(mandal) == {"id", "district_id", "name", "is_active"}
    missing = admin.post(f"{BASE}/mandals", json={"district_id": RANDOM_ID, "name": unique("mstmand")})
    assert missing.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A14")
def test_mandal_lists_and_dropdown(admin, cleanup):
    state = make_state(admin, cleanup)
    district = make_district(admin, cleanup, state["id"])
    active = make_mandal(admin, cleanup, district["id"])
    inactive = make_mandal(admin, cleanup, district["id"], is_active=False)
    full = admin.get(f"{BASE}/districts/{district['id']}/mandals")
    assert full.status_code == 200
    assert sorted(m["id"] for m in full.json()) == sorted([active["id"], inactive["id"]])
    dropdown = admin.get(f"{BASE}/districts/{district['id']}/mandals/dropdown")
    assert dropdown.status_code == 200
    assert dropdown.json() == [{"id": active["id"], "name": active["name"], "district_id": district["id"]}]
    assert admin.get(f"{BASE}/districts/{RANDOM_ID}/mandals").status_code == 404
    unknown = admin.get(f"{BASE}/districts/{RANDOM_ID}/mandals/dropdown")
    assert unknown.status_code == 200 and unknown.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A15")
def test_get_update_delete_mandal(admin, cleanup):
    _, district, mandal = tree(admin, cleanup)
    assert admin.get(f"{BASE}/mandals/{mandal['id']}").json() == mandal
    renamed = unique("mstmand")
    updated = admin.put(f"{BASE}/mandals/{mandal['id']}", json={"name": renamed, "is_active": False})
    assert updated.status_code == 200
    assert updated.json()["name"] == renamed and updated.json()["is_active"] is False
    extra = admin.post(f"{BASE}/mandals", json={"district_id": district["id"], "name": unique("mstmand")}).json()
    deleted = admin.delete(f"{BASE}/mandals/{extra['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"message": "Mandal deleted successfully"}
    assert admin.get(f"{BASE}/mandals/{RANDOM_ID}").status_code == 404
    assert admin.put(f"{BASE}/mandals/{RANDOM_ID}", json={"name": "x"}).status_code == 404
    assert admin.delete(f"{BASE}/mandals/{RANDOM_ID}").status_code == 404


def read_paths(state, district, mandal):
    return [
        f"{BASE}/states",
        f"{BASE}/states/dropdown",
        f"{BASE}/states/{state['id']}",
        f"{BASE}/states/{state['id']}/districts",
        f"{BASE}/states/{state['id']}/districts/dropdown",
        f"{BASE}/districts/{district['id']}",
        f"{BASE}/districts/{district['id']}/mandals",
        f"{BASE}/districts/{district['id']}/mandals/dropdown",
        f"{BASE}/mandals/{mandal['id']}",
    ]


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A16")
@pytest.mark.parametrize("role", READERS)
def test_location_read_matrix_granted(role_clients, admin, cleanup, role):
    state, district, mandal = tree(admin, cleanup)
    for path in read_paths(state, district, mandal):
        assert role_clients[role].get(path).status_code == 200, (role, path)


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A17")
@pytest.mark.parametrize("role", NO_GRANT)
def test_location_read_matrix_denied(role_clients, admin, cleanup, role):
    state, district, mandal = tree(admin, cleanup)
    for path in read_paths(state, district, mandal):
        assert role_clients[role].get(path).status_code == 403, (role, path)


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A18")
@pytest.mark.parametrize("role", DENIED)
def test_location_write_denied(role_clients, admin, cleanup, role):
    state, district, mandal = tree(admin, cleanup)
    client = role_clients[role]
    assert client.post(f"{BASE}/states", json={"name": unique("mststate")}).status_code == 403
    assert client.post(f"{BASE}/districts", json={"state_id": state["id"], "name": unique("mstdist")}).status_code == 403
    assert client.post(f"{BASE}/mandals", json={"district_id": district["id"], "name": unique("mstmand")}).status_code == 403
    assert client.put(f"{BASE}/states/{state['id']}", json={"name": unique("mststate")}).status_code == 403
    assert client.put(f"{BASE}/districts/{district['id']}", json={"name": unique("mstdist")}).status_code == 403
    assert client.put(f"{BASE}/mandals/{mandal['id']}", json={"name": unique("mstmand")}).status_code == 403
    assert client.delete(f"{BASE}/states/{state['id']}").status_code == 403
    assert client.delete(f"{BASE}/districts/{district['id']}").status_code == 403
    assert client.delete(f"{BASE}/mandals/{mandal['id']}").status_code == 403
    assert admin.get(f"{BASE}/states/{state['id']}").json()["name"] == state["name"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A19")
def test_location_endpoints_need_authentication(anon):
    rid = RANDOM_ID
    for path in (
        "/states",
        "/states/dropdown",
        f"/states/{rid}",
        f"/states/{rid}/districts",
        f"/states/{rid}/districts/dropdown",
        f"/districts/{rid}",
        f"/districts/{rid}/mandals",
        f"/districts/{rid}/mandals/dropdown",
        f"/mandals/{rid}",
    ):
        assert anon.get(f"{BASE}{path}").status_code == 401, path
    assert anon.post(f"{BASE}/states", json={"name": "x"}).status_code == 401
    assert anon.post(f"{BASE}/districts", json={"state_id": rid, "name": "x"}).status_code == 401
    assert anon.post(f"{BASE}/mandals", json={"district_id": rid, "name": "x"}).status_code == 401
    for path in (f"/states/{rid}", f"/districts/{rid}", f"/mandals/{rid}"):
        assert anon.put(f"{BASE}{path}", json={"name": "x"}).status_code == 401, path
        assert anon.delete(f"{BASE}{path}").status_code == 401, path


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A20")
def test_location_data_is_shared_between_tenants(admin, tenant_b, cleanup):
    state, district, mandal = tree(admin, cleanup)
    assert state["id"] in [i["id"] for i in tenant_b.get(f"{BASE}/states?limit=1000").json()["items"]]
    assert tenant_b.get(f"{BASE}/states/{state['id']}").status_code == 200
    assert [d["id"] for d in tenant_b.get(f"{BASE}/states/{state['id']}/districts").json()] == [district["id"]]
    assert tenant_b.get(f"{BASE}/mandals/{mandal['id']}").status_code == 200
    assert admin.get(f"{BASE}/states", headers={"cschema": QA_B_TENANT}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A21")
def test_states_dropdown_is_fresh_after_create(admin, cleanup):
    admin.get(f"{BASE}/states/dropdown")
    state = make_state(admin, cleanup)
    after = admin.get(f"{BASE}/states/dropdown").json()
    assert state["id"] in [r["id"] for r in after]


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A22")
@pytest.mark.skip(
    reason="The seed writes five states with districts and mandals into the shared location tables used by every tenant and suite; running it would race with the other suites"
)
def test_location_seed_is_idempotent():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-MST-12-A23")
@pytest.mark.skip(reason="The test API runs with rate limiting disabled, so the 429 cannot be produced")
def test_location_rate_limit():
    pass
