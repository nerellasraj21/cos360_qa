import uuid

import pytest

from api_tests.support import items_of, unique
from api_tests.transport.helpers import ROLES, READ_ROLES, make_route, make_stop, make_trip, make_vehicle, other_tenant_header

BASE = "/masters/routes/"


def route_body(**over):
    body = {
        "route_name": unique("trn_route_"),
        "starting_stop": "School",
        "ending_stop": "Market",
        "number_of_stops": 3,
        "start_time": "07:00:00",
        "end_time": "08:30:00",
    }
    body.update(over)
    return body


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A01")
def test_create_route(admin, cleanup):
    body = route_body()
    response = admin.post(BASE, json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}{data['id']}")
    assert data["is_active"] is True
    assert data["start_time"] == "07:00:00" and data["end_time"] == "08:30:00"
    assert data["route_type"] is None
    assert data["route_name"] == body["route_name"]
    assert data["number_of_stops"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A02")
def test_create_route_with_types(admin, cleanup):
    route = make_route(admin, cleanup, route_type="Upward", trip_type="First Trip")
    assert route["route_type"] == "Upward" and route["trip_type"] == "First Trip"


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A03")
def test_duplicate_route_name(admin, cleanup):
    route = make_route(admin, cleanup)
    response = admin.post(BASE, json=route_body(route_name=route["route_name"]))
    assert response.status_code == 400
    assert f"Route '{route['route_name']}' already exists" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A04")
@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.pop("route_name"),
        lambda b: b.pop("start_time"),
        lambda b: b.pop("number_of_stops"),
        lambda b: b.update(number_of_stops="abc"),
        lambda b: b.update(start_time="25:00"),
    ],
    ids=["no_name", "no_start", "no_stops", "stops_text", "bad_time"],
)
def test_create_route_validation(admin, mutate):
    body = route_body()
    mutate(body)
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A04")
def test_end_time_before_start_accepted(admin, cleanup):
    make_route(admin, cleanup, start_time="09:00:00", end_time="07:00:00")


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A05")
def test_all_routes_excludes_inactive(admin, cleanup):
    active = make_route(admin, cleanup)
    gone = make_route(admin, cleanup)
    admin.delete(f"{BASE}{gone['id']}")
    ids = [row["id"] for row in items_of(admin.get(f"{BASE}all_routes"))]
    assert active["id"] in ids and gone["id"] not in ids


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A06")
def test_get_route_by_id(admin, cleanup):
    route = make_route(admin, cleanup)
    inactive = make_route(admin, cleanup)
    admin.delete(f"{BASE}{inactive['id']}")
    assert admin.get(f"{BASE}routeid/{route['id']}").status_code == 200
    assert admin.get(f"{BASE}routeid/{inactive['id']}").status_code == 200
    missing = admin.get(f"{BASE}routeid/{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["detail"] == "Route not found"
    assert admin.get(f"{BASE}routeid/not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A07")
def test_route_dropdown(admin, cleanup):
    low = make_route(admin, cleanup, route_name=unique("trn_route_a_"))
    high = make_route(admin, cleanup, route_name=unique("trn_route_z_"))
    rows = admin.get(f"{BASE}dropdown", params={"active_only": "false"}).json()
    ids = [row["id"] for row in rows]
    assert ids.index(low["id"]) < ids.index(high["id"])
    assert set(rows[0]) >= {"id", "route_name"}


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A08")
def test_route_dropdown_after_rename(admin, cleanup):
    route = make_route(admin, cleanup)
    new_name = unique("trn_route_")
    assert admin.patch(f"{BASE}{route['id']}", json={"route_name": new_name}).status_code == 200
    rows = admin.get(f"{BASE}dropdown", params={"active_only": "false"}).json()
    match = [row for row in rows if row["id"] == route["id"]]
    assert match and match[0]["route_name"] in (route["route_name"], new_name)


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A09")
def test_stops_by_route(admin, cleanup):
    route = make_route(admin, cleanup)
    first = make_stop(admin, cleanup, route["id"], 1)
    second = make_stop(admin, cleanup, route["id"], 2)
    response = admin.get(f"{BASE}stops-by-route", params={"route_name": route["route_name"]})
    assert response.status_code == 200
    assert {row["id"] for row in response.json()} == {first["id"], second["id"]}


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A10")
def test_stops_by_route_errors(admin):
    missing = admin.get(f"{BASE}stops-by-route", params={"route_name": unique("trn_none_")})
    assert missing.status_code == 404 and "Route not found" in missing.text
    assert admin.get(f"{BASE}stops-by-route").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A11")
def test_put_route(admin, cleanup):
    first = make_route(admin, cleanup)
    second = make_route(admin, cleanup)
    new_name = unique("trn_route_")
    ok = admin.put(f"{BASE}{first['id']}", json=route_body(route_name=new_name))
    assert ok.status_code == 200 and ok.json()["route_name"] == new_name
    clash = admin.put(f"{BASE}{second['id']}", json=route_body(route_name=new_name))
    assert clash.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A12")
def test_patch_route_deactivate(admin, cleanup):
    route = make_route(admin, cleanup)
    response = admin.patch(f"{BASE}{route['id']}", json={"is_active": False})
    assert response.status_code == 200
    assert route["id"] not in [row["id"] for row in items_of(admin.get(f"{BASE}all_routes"))]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A13")
def test_delete_route_keeps_stops_and_trips(admin, cleanup):
    route = make_route(admin, cleanup)
    stop = make_stop(admin, cleanup, route["id"], 1)
    vehicle = make_vehicle(admin, cleanup)
    trip = make_trip(admin, cleanup, vehicle["id"], route["id"])
    response = admin.delete(f"{BASE}{route['id']}")
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert admin.get(f"/masters/route-stops/{stop['id']}").json()["is_active"] is True
    assert admin.get(f"/masters/trips/{trip['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A14")
def test_deleted_route_name_still_taken(admin, cleanup):
    route = make_route(admin, cleanup)
    admin.delete(f"{BASE}{route['id']}")
    assert admin.post(BASE, json=route_body(route_name=route["route_name"])).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A15")
@pytest.mark.parametrize("role", ROLES)
def test_route_role_matrix(role_clients, admin, cleanup, role):
    route = make_route(admin, cleanup)
    client = role_clients[role]
    read = 200 if role in READ_ROLES else 403
    assert client.get(f"{BASE}all_routes").status_code == read
    assert client.get(f"{BASE}routeid/{route['id']}").status_code == read
    assert client.get(f"{BASE}dropdown").status_code == read
    assert client.get(f"{BASE}stops-by-route", params={"route_name": route["route_name"]}).status_code == read
    if role == "admin":
        return
    assert client.post(BASE, json=route_body()).status_code == 403
    assert client.put(f"{BASE}{route['id']}", json=route_body()).status_code == 403
    assert client.patch(f"{BASE}{route['id']}", json={"ending_stop": "x"}).status_code == 403
    assert client.delete(f"{BASE}{route['id']}").status_code == 403
    assert admin.get(f"{BASE}routeid/{route['id']}").json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A15")
def test_route_unauthenticated(anon):
    assert anon.get(f"{BASE}all_routes").status_code == 401
    assert anon.post(BASE, json=route_body()).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TRN-04-A16")
def test_route_tenant_isolation(admin, tenant_b, cleanup):
    route = make_route(admin, cleanup)
    assert route["id"] not in [row["id"] for row in items_of(tenant_b.get(f"{BASE}all_routes"))]
    assert tenant_b.get(f"{BASE}routeid/{route['id']}").status_code == 404
    reuse = tenant_b.post(BASE, json=route_body(route_name=route["route_name"]))
    assert reuse.status_code == 201, reuse.text
    cleanup.delete_later(tenant_b, f"{BASE}{reuse.json()['id']}")
    assert other_tenant_header(admin).get(f"{BASE}all_routes").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TRN-01-A01")
def test_admin_transport_hub_calls(admin):
    assert admin.get(f"{BASE}all_routes").status_code == 200
    assert admin.get("/masters/vehicles/").status_code == 200
