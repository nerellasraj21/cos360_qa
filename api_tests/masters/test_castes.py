import pytest

from api_tests.masters.helpers import DENIED, RANDOM_ID, make_admission, make_class
from api_tests.support import QA_B_TENANT, unique

BASE = "/masters/castes"
SEED = "/auth/seed/caste-data"
READERS = ["admin", "staff", "teacher"]
NO_GRANT = ["student", "parent"]
SEED_CASTES = ["General", "OBC", "SC", "ST", "EWS"]
SEED_SUB_COUNT = 18


def make_caste(api, cleanup, **over):
    body = {"name": unique("mstcaste"), "code": unique("c")[:6]}
    body.update(over)
    response = api.post(f"{BASE}/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(api, f"{BASE}/{data['id']}")
    return data


def make_sub(api, cleanup, caste_id, **over):
    body = {"caste_id": caste_id, "name": unique("mstsub"), "code": "SUB"}
    body.update(over)
    response = api.post(f"{BASE}/sub-castes", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(api, f"{BASE}/sub-castes/{data['id']}")
    return data


def purge_seeded(api):
    listing = api.get(f"{BASE}/?limit=1000")
    for caste in listing.json().get("items", []):
        if caste["name"] in SEED_CASTES:
            for sub in api.get(f"{BASE}/{caste['id']}/sub-castes").json():
                api.delete(f"{BASE}/sub-castes/{sub['id']}")
            api.delete(f"{BASE}/{caste['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A01")
def test_seed_caste_data_on_empty_tenant(tenant_b, cleanup):
    existing = [c["name"] for c in tenant_b.get(f"{BASE}/?limit=1000").json()["items"]]
    if any(name in SEED_CASTES for name in existing):
        pytest.skip("tenant qa_school_b already holds seeded castes")
    cleanup.add(purge_seeded, tenant_b)
    response = tenant_b.post(SEED)
    assert response.status_code == 201, response.text
    details = response.json()["details"]
    assert sorted(details["castes_created"]) == sorted(SEED_CASTES)
    assert len(details["sub_castes_created"]) == SEED_SUB_COUNT
    assert details["total_castes"] == 5 and details["total_sub_castes"] == SEED_SUB_COUNT
    rows = {c["name"]: c for c in tenant_b.get(f"{BASE}/?limit=1000").json()["items"]}
    assert rows["General"]["code"] == "GEN" and rows["SC"]["code"] == "SC"
    sc_subs = tenant_b.get(f"{BASE}/{rows['SC']['id']}/sub-castes").json()
    assert sorted(s["name"] for s in sc_subs) == sorted(["Adi Andhra", "Adi Dravida", "Mala", "Madiga", "Chamar", "Pasi"])


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A02")
def test_seed_caste_data_is_idempotent(tenant_b, cleanup):
    existing = [c["name"] for c in tenant_b.get(f"{BASE}/?limit=1000").json()["items"]]
    if any(name in SEED_CASTES for name in existing):
        pytest.skip("tenant qa_school_b already holds seeded castes")
    cleanup.add(purge_seeded, tenant_b)
    assert tenant_b.post(SEED).status_code == 201
    again = tenant_b.post(SEED)
    assert again.status_code == 201
    details = again.json()["details"]
    assert details["castes_created"] == [] and details["sub_castes_created"] == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A03")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_seed_caste_data_admin_only(role_clients, role):
    response = role_clients[role].post(SEED)
    assert response.status_code == 403
    assert response.json()["detail"] == "Only administrators can seed data"


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A03")
def test_seed_caste_data_needs_authentication(anon):
    assert anon.post(SEED).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A04")
def test_create_caste(admin, cleanup):
    body = {"name": unique("mstcaste"), "code": "QC"}
    response = admin.post(f"{BASE}/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}/{data['id']}")
    assert set(data) == {"id", "name", "code", "is_active"}
    assert data["name"] == body["name"] and data["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A05")
def test_caste_name_uniqueness(admin, cleanup):
    a = make_caste(admin, cleanup)
    b = make_caste(admin, cleanup)
    dup = admin.post(f"{BASE}/", json={"name": a["name"]})
    assert dup.status_code == 400
    assert dup.json()["detail"] == f"Caste name '{a['name']}' already exists"
    rename = admin.put(f"{BASE}/{b['id']}", json={"name": a["name"]})
    assert rename.status_code == 400
    assert rename.json()["detail"] == f"Caste name '{a['name']}' already exists"


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A06")
def test_list_castes(admin, cleanup):
    active = make_caste(admin, cleanup)
    inactive = make_caste(admin, cleanup, is_active=False)
    data = admin.get(f"{BASE}/?limit=1000").json()
    assert set(data) == {"items", "total_count", "has_next"}
    ids = [c["id"] for c in data["items"]]
    assert active["id"] in ids and inactive["id"] in ids
    only = admin.get(f"{BASE}/?active_only=true&limit=1000").json()["items"]
    assert active["id"] in [c["id"] for c in only] and inactive["id"] not in [c["id"] for c in only]
    assert admin.get(f"{BASE}/?limit=0").status_code == 422
    assert admin.get(f"{BASE}/?limit=1001").status_code == 422
    assert admin.get(f"{BASE}/?skip=-1").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A07")
def test_caste_dropdown_shape(admin, cleanup):
    make_caste(admin, cleanup, is_active=False)
    rows = admin.get(f"{BASE}/dropdown").json()
    assert all(set(r) == {"id", "name", "code"} for r in rows)
    names = [r["name"] for r in rows]
    assert names == sorted(names)
    assert admin.get(f"{BASE}/dropdown?active_only=false").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A08")
def test_get_and_update_caste(admin, cleanup):
    caste = make_caste(admin, cleanup)
    assert admin.get(f"{BASE}/{caste['id']}").json() == caste
    new = unique("mstcaste")
    updated = admin.put(f"{BASE}/{caste['id']}", json={"name": new, "is_active": False})
    assert updated.status_code == 200
    assert updated.json()["name"] == new and updated.json()["is_active"] is False
    missing = admin.get(f"{BASE}/{RANDOM_ID}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == f"Caste with id {RANDOM_ID} not found"
    assert admin.put(f"{BASE}/{RANDOM_ID}", json={"name": "x"}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A09")
def test_create_sub_caste(admin, cleanup):
    caste = make_caste(admin, cleanup)
    sub = make_sub(admin, cleanup, caste["id"])
    assert set(sub) == {"id", "caste_id", "name", "code", "is_active"}
    assert sub["caste_id"] == caste["id"] and sub["is_active"] is True
    missing = admin.post(f"{BASE}/sub-castes", json={"caste_id": RANDOM_ID, "name": unique("mstsub")})
    assert missing.status_code == 404
    assert missing.json()["detail"] == f"Caste with id {RANDOM_ID} not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A10")
def test_duplicate_sub_caste_names_allowed(admin, cleanup):
    caste = make_caste(admin, cleanup)
    name = unique("mstsub")
    first = make_sub(admin, cleanup, caste["id"], name=name)
    second = make_sub(admin, cleanup, caste["id"], name=name)
    assert first["id"] != second["id"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A11")
def test_sub_caste_lists(admin, cleanup):
    caste = make_caste(admin, cleanup)
    active = make_sub(admin, cleanup, caste["id"])
    inactive = make_sub(admin, cleanup, caste["id"], is_active=False)
    full = admin.get(f"{BASE}/{caste['id']}/sub-castes")
    assert full.status_code == 200
    assert sorted(s["id"] for s in full.json()) == sorted([active["id"], inactive["id"]])
    dropdown = admin.get(f"{BASE}/{caste['id']}/sub-castes/dropdown")
    assert dropdown.status_code == 200
    assert dropdown.json() == [
        {"id": active["id"], "name": active["name"], "code": active["code"], "caste_id": caste["id"]}
    ]


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A12")
def test_get_update_sub_caste_and_reparent(admin, cleanup):
    c1 = make_caste(admin, cleanup)
    c2 = make_caste(admin, cleanup)
    sub = make_sub(admin, cleanup, c1["id"])
    assert admin.get(f"{BASE}/sub-castes/{sub['id']}").json() == sub
    moved = admin.put(f"{BASE}/sub-castes/{sub['id']}", json={"caste_id": c2["id"]})
    assert moved.status_code == 200 and moved.json()["caste_id"] == c2["id"]
    bad = admin.put(f"{BASE}/sub-castes/{sub['id']}", json={"caste_id": RANDOM_ID})
    assert bad.status_code == 404
    assert admin.get(f"{BASE}/sub-castes/{RANDOM_ID}").status_code == 404
    assert admin.put(f"{BASE}/sub-castes/{RANDOM_ID}", json={"name": "x"}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A13")
def test_delete_caste_with_sub_castes(admin, cleanup):
    caste = make_caste(admin, cleanup)
    sub = make_sub(admin, cleanup, caste["id"])
    blocked = admin.delete(f"{BASE}/{caste['id']}")
    assert blocked.status_code == 400
    assert "has 1 sub-caste(s)" in blocked.json()["detail"]
    assert admin.delete(f"{BASE}/sub-castes/{sub['id']}").status_code == 200
    ok = admin.delete(f"{BASE}/{caste['id']}")
    assert ok.status_code == 200
    assert ok.json() == {"message": "Caste deleted successfully"}
    assert admin.get(f"{BASE}/{caste['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A14")
def test_delete_caste_used_by_student(admin, cleanup, pool):
    caste = make_caste(admin, cleanup)
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=("A",))
    make_admission(
        admin, cleanup, pool["year"]["id"], cls["id"], cls["sections"][0]["id"], student_extra={"caste_id": caste["id"]}
    )
    response = admin.delete(f"{BASE}/{caste['id']}")
    assert response.status_code == 400
    assert "being used by 1 student(s)" in response.json()["detail"]
    assert admin.get(f"{BASE}/{caste['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A15")
def test_delete_sub_caste(admin, cleanup):
    caste = make_caste(admin, cleanup)
    sub = admin.post(f"{BASE}/sub-castes", json={"caste_id": caste["id"], "name": unique("mstsub")}).json()
    response = admin.delete(f"{BASE}/sub-castes/{sub['id']}")
    assert response.status_code == 200
    assert response.json() == {"message": "Sub-caste deleted successfully"}
    assert admin.delete(f"{BASE}/sub-castes/{RANDOM_ID}").status_code == 404


def caste_read_paths(caste, sub):
    return [
        f"{BASE}/",
        f"{BASE}/dropdown",
        f"{BASE}/{caste['id']}",
        f"{BASE}/{caste['id']}/sub-castes",
        f"{BASE}/{caste['id']}/sub-castes/dropdown",
        f"{BASE}/sub-castes/{sub['id']}",
    ]


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A16")
@pytest.mark.parametrize("role", READERS)
def test_caste_read_matrix_granted(role_clients, admin, cleanup, role):
    caste = make_caste(admin, cleanup)
    sub = make_sub(admin, cleanup, caste["id"])
    for path in caste_read_paths(caste, sub):
        assert role_clients[role].get(path).status_code == 200, (role, path)


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A17")
@pytest.mark.parametrize("role", NO_GRANT)
def test_caste_read_matrix_denied(role_clients, admin, cleanup, role):
    caste = make_caste(admin, cleanup)
    sub = make_sub(admin, cleanup, caste["id"])
    for path in caste_read_paths(caste, sub):
        assert role_clients[role].get(path).status_code == 403, (role, path)


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A18")
@pytest.mark.parametrize("role", DENIED)
def test_caste_write_denied(role_clients, admin, cleanup, role):
    caste = make_caste(admin, cleanup)
    sub = make_sub(admin, cleanup, caste["id"])
    client = role_clients[role]
    assert client.post(f"{BASE}/", json={"name": unique("mstcaste")}).status_code == 403
    assert client.post(f"{BASE}/sub-castes", json={"caste_id": caste["id"], "name": unique("mstsub")}).status_code == 403
    assert client.put(f"{BASE}/{caste['id']}", json={"name": unique("mstcaste")}).status_code == 403
    assert client.put(f"{BASE}/sub-castes/{sub['id']}", json={"name": unique("mstsub")}).status_code == 403
    assert client.delete(f"{BASE}/{caste['id']}").status_code == 403
    assert client.delete(f"{BASE}/sub-castes/{sub['id']}").status_code == 403
    assert admin.get(f"{BASE}/{caste['id']}").json() == caste


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A19")
def test_caste_endpoints_need_authentication(anon):
    rid = RANDOM_ID
    for path in ("/", "/dropdown", f"/{rid}", f"/{rid}/sub-castes", f"/{rid}/sub-castes/dropdown", f"/sub-castes/{rid}"):
        assert anon.get(f"{BASE}{path}").status_code == 401, path
    assert anon.post(f"{BASE}/", json={"name": "x"}).status_code == 401
    assert anon.post(f"{BASE}/sub-castes", json={"caste_id": rid, "name": "x"}).status_code == 401
    for path in (f"/{rid}", f"/sub-castes/{rid}"):
        assert anon.put(f"{BASE}{path}", json={"name": "x"}).status_code == 401, path
        assert anon.delete(f"{BASE}{path}").status_code == 401, path


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A20")
def test_caste_tenant_isolation(admin, tenant_b, cleanup):
    caste = make_caste(admin, cleanup)
    assert caste["id"] not in [c["id"] for c in tenant_b.get(f"{BASE}/?limit=1000").json()["items"]]
    assert tenant_b.get(f"{BASE}/{caste['id']}").status_code == 404
    twin = tenant_b.post(f"{BASE}/", json={"name": caste["name"]})
    assert twin.status_code == 201, twin.text
    cleanup.delete_later(tenant_b, f"{BASE}/{twin.json()['id']}")
    assert admin.get(f"{BASE}/", headers={"cschema": QA_B_TENANT}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-MST-13-A21")
def test_caste_dropdown_is_fresh_after_create(admin, cleanup):
    admin.get(f"{BASE}/dropdown")
    caste = make_caste(admin, cleanup)
    after = admin.get(f"{BASE}/dropdown").json()
    assert caste["id"] in [r["id"] for r in after]
