import uuid

import pytest

from api_tests.support import items_of, unique
from api_tests.transport.helpers import ROLES, READ_ROLES, make_route_type, make_trip_type, other_tenant_header

RT = "/masters/route-types/"
TT = "/masters/trip-types/"


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A01")
def test_create_route_type(admin, cleanup):
    name = unique("trn_rt_")
    response = admin.post(RT, json={"type_name": name})
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{RT}{data['id']}")
    assert data["type_name"] == name and data["is_active"] is True
    assert data["id"] and data["created_at"] and data["updated_at"]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A02")
def test_create_route_type_wrong_field(admin):
    assert admin.post(RT, json={"name": "X"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A03")
def test_duplicate_route_type(admin, cleanup):
    created = make_route_type(admin, cleanup)
    assert admin.post(RT, json={"type_name": created["type_name"]}).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A04")
def test_route_type_all_excludes_inactive(admin, cleanup):
    active = make_route_type(admin, cleanup)
    gone = make_route_type(admin, cleanup)
    admin.delete(f"{RT}{gone['id']}")
    ids = [row["id"] for row in items_of(admin.get(f"{RT}all"))]
    assert active["id"] in ids and gone["id"] not in ids


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A05")
def test_route_type_dropdown(admin, cleanup):
    low = make_route_type(admin, cleanup, type_name=unique("trn_rt_a_"))
    high = make_route_type(admin, cleanup, type_name=unique("trn_rt_z_"))
    gone = make_route_type(admin, cleanup)
    admin.delete(f"{RT}{gone['id']}")
    rows = admin.get(f"{RT}dropdown").json()
    ids = [row["id"] for row in rows]
    assert ids.index(low["id"]) < ids.index(high["id"])
    assert gone["id"] not in ids
    assert set(rows[0]) >= {"id", "type_name"}
    everything = [row["id"] for row in admin.get(f"{RT}dropdown", params={"active_only": "false"}).json()]
    assert gone["id"] in everything


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A06")
def test_get_route_type(admin, cleanup):
    created = make_route_type(admin, cleanup)
    inactive = make_route_type(admin, cleanup)
    admin.delete(f"{RT}{inactive['id']}")
    assert admin.get(f"{RT}{created['id']}").status_code == 200
    assert admin.get(f"{RT}{inactive['id']}").status_code == 200
    missing = admin.get(f"{RT}{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["detail"] == "Route type not found"
    assert admin.get(f"{RT}not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A07")
def test_put_route_type(admin, cleanup):
    first = make_route_type(admin, cleanup)
    second = make_route_type(admin, cleanup)
    new_name = unique("trn_rt_")
    ok = admin.put(f"{RT}{first['id']}", json={"type_name": new_name, "description": "d", "is_active": True})
    assert ok.status_code == 200 and ok.json()["type_name"] == new_name
    clash = admin.put(f"{RT}{second['id']}", json={"type_name": new_name, "is_active": True})
    assert clash.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A08")
def test_patch_route_type(admin, cleanup):
    created = make_route_type(admin, cleanup)
    response = admin.patch(f"{RT}{created['id']}", json={"description": "only description"})
    assert response.status_code == 200
    assert response.json()["description"] == "only description"
    assert response.json()["type_name"] == created["type_name"]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A09")
def test_delete_route_type(admin, cleanup):
    created = make_route_type(admin, cleanup)
    response = admin.delete(f"{RT}{created['id']}")
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert created["id"] not in [row["id"] for row in items_of(admin.get(f"{RT}all"))]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A10")
def test_deleted_route_type_name_still_taken(admin, cleanup):
    created = make_route_type(admin, cleanup)
    admin.delete(f"{RT}{created['id']}")
    assert admin.post(RT, json={"type_name": created["type_name"]}).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A11")
@pytest.mark.parametrize("role", ROLES)
def test_route_type_role_matrix(role_clients, admin, cleanup, role):
    created = make_route_type(admin, cleanup)
    client = role_clients[role]
    read = 200 if role in READ_ROLES else 403
    assert client.get(f"{RT}all").status_code == read
    assert client.get(f"{RT}dropdown").status_code == read
    assert client.get(f"{RT}{created['id']}").status_code == read
    if role == "admin":
        return
    assert client.post(RT, json={"type_name": unique("trn_rt_")}).status_code == 403
    assert client.put(f"{RT}{created['id']}", json={"type_name": unique("trn_rt_"), "is_active": True}).status_code == 403
    assert client.patch(f"{RT}{created['id']}", json={"description": "x"}).status_code == 403
    assert client.delete(f"{RT}{created['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A11")
def test_route_type_unauthenticated(anon):
    assert anon.get(f"{RT}all").status_code == 401
    assert anon.post(RT, json={"type_name": "x"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TRN-02-A12")
def test_route_type_tenant_isolation(admin, tenant_b, cleanup):
    created = make_route_type(admin, cleanup)
    assert created["id"] not in [row["id"] for row in items_of(tenant_b.get(f"{RT}all"))]
    assert created["id"] not in [row["id"] for row in tenant_b.get(f"{RT}dropdown", params={"active_only": "false"}).json()]
    assert tenant_b.get(f"{RT}{created['id']}").status_code == 404
    same = tenant_b.post(RT, json={"type_name": created["type_name"]})
    assert same.status_code == 201, same.text
    cleanup.delete_later(tenant_b, f"{RT}{same.json()['id']}")
    assert other_tenant_header(admin).get(f"{RT}all").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TRN-03-A01")
def test_create_trip_type(admin, cleanup):
    name = unique("trn_tt_")
    response = admin.post(TT, json={"type_name": name})
    assert response.status_code == 200, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{TT}{data['id']}")
    assert data["type_name"] == name and data["is_active"] is True and data["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-03-A02")
def test_trip_type_duplicate_and_wrong_field(admin, cleanup):
    created = make_trip_type(admin, cleanup)
    assert admin.post(TT, json={"type_name": created["type_name"]}).status_code == 400
    assert admin.post(TT, json={"name": "X"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-03-A03")
def test_trip_type_all_and_dropdown(admin, cleanup):
    low = make_trip_type(admin, cleanup, type_name=unique("trn_tt_a_"))
    high = make_trip_type(admin, cleanup, type_name=unique("trn_tt_z_"))
    gone = make_trip_type(admin, cleanup)
    assert admin.delete(f"{TT}{gone['id']}").status_code == 200
    all_ids = [row["id"] for row in items_of(admin.get(f"{TT}all"))]
    assert low["id"] in all_ids and gone["id"] not in all_ids
    dropdown = admin.get(f"{TT}dropdown").json()
    ids = [row["id"] for row in dropdown]
    assert ids.index(low["id"]) < ids.index(high["id"]) and gone["id"] not in ids
    assert set(dropdown[0]) >= {"id", "type_name"}


@pytest.mark.api
@pytest.mark.tc("TC-TRN-03-A04")
def test_get_trip_type(admin, cleanup):
    created = make_trip_type(admin, cleanup)
    assert admin.get(f"{TT}{created['id']}").json()["type_name"] == created["type_name"]
    missing = admin.get(f"{TT}{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["detail"] == "Trip type not found"
    assert admin.get(f"{TT}not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-03-A05")
def test_put_trip_type(admin, cleanup):
    first = make_trip_type(admin, cleanup)
    second = make_trip_type(admin, cleanup)
    new_name = unique("trn_tt_")
    ok = admin.put(f"{TT}{first['id']}", json={"type_name": new_name, "is_active": True})
    assert ok.status_code == 200 and ok.json()["type_name"] == new_name
    assert admin.put(f"{TT}{second['id']}", json={"type_name": new_name, "is_active": True}).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-03-A06")
def test_patch_trip_type(admin, cleanup):
    created = make_trip_type(admin, cleanup)
    response = admin.patch(f"{TT}{created['id']}", json={"description": "only description"})
    assert response.status_code == 200
    assert response.json()["description"] == "only description"
    assert response.json()["type_name"] == created["type_name"]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-03-A07")
def test_delete_trip_type(admin, cleanup):
    created = make_trip_type(admin, cleanup)
    response = admin.delete(f"{TT}{created['id']}")
    assert response.status_code == 200
    assert response.json() == {"message": "Trip type soft deleted"}
    assert created["id"] not in [row["id"] for row in items_of(admin.get(f"{TT}all"))]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-03-A08")
@pytest.mark.parametrize("role", ROLES)
def test_trip_type_role_matrix(role_clients, admin, cleanup, role):
    created = make_trip_type(admin, cleanup)
    client = role_clients[role]
    read = 200 if role in READ_ROLES else 403
    assert client.get(f"{TT}all").status_code == read
    assert client.get(f"{TT}dropdown").status_code == read
    assert client.get(f"{TT}{created['id']}").status_code == read
    if role == "admin":
        return
    assert client.post(TT, json={"type_name": unique("trn_tt_")}).status_code == 403
    assert client.put(f"{TT}{created['id']}", json={"type_name": unique("trn_tt_"), "is_active": True}).status_code == 403
    assert client.patch(f"{TT}{created['id']}", json={"description": "x"}).status_code == 403
    assert client.delete(f"{TT}{created['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TRN-03-A08")
def test_trip_type_unauthenticated(anon):
    assert anon.get(f"{TT}all").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TRN-03-A09")
def test_trip_type_tenant_isolation(admin, tenant_b, cleanup):
    created = make_trip_type(admin, cleanup)
    assert created["id"] not in [row["id"] for row in items_of(tenant_b.get(f"{TT}all"))]
    assert tenant_b.get(f"{TT}{created['id']}").status_code == 404
    assert other_tenant_header(admin).get(f"{TT}all").status_code == 403
