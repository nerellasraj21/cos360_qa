import uuid

import pytest

from api_tests.support import items_of, unique
from api_tests.transport.helpers import (
    ROLES,
    READ_ROLES,
    make_route,
    make_stop,
    make_trip,
    make_vehicle,
    other_tenant_header,
    vehicle_body,
)

BASE = "/masters/vehicles/"


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A01")
def test_create_vehicle(admin, cleanup):
    body = vehicle_body()
    response = admin.post(BASE, json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}{data['id']}")
    assert data["is_active"] is True
    assert data["last_inspected_date"] == "2026-09-01" and data["pollution_renewal_date"] == "2026-09-01"
    assert data["registration_number"] == body["registration_number"]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A02")
def test_create_vehicle_extended_fields(admin, cleanup):
    vehicle = make_vehicle(
        admin,
        cleanup,
        driver_name="R. Kumar",
        driving_licence_no="DL-QA-1",
        fees=1200.50,
        is_ac=True,
        number_of_trips=2,
    )
    assert vehicle["driver_name"] == "R. Kumar"
    assert vehicle["driving_licence_no"] == "DL-QA-1"
    assert vehicle["fees"] == 1200.5
    assert vehicle["is_ac"] is True and vehicle["number_of_trips"] == 2


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A03")
def test_duplicate_registration(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    response = admin.post(BASE, json=vehicle_body(registration_number=vehicle["registration_number"]))
    assert response.status_code == 400
    assert f"Vehicle '{vehicle['registration_number']}' already registered" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A04")
def test_extra_fee_fields_dropped(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup, fee_category_id=str(uuid.uuid4()), fee_type_id=str(uuid.uuid4()))
    assert "fee_category_id" not in vehicle and "fee_type_id" not in vehicle


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A05")
@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.pop("name"),
        lambda b: b.pop("vehicle_type"),
        lambda b: b.update(last_inspected_date="not-a-date"),
        lambda b: b.pop("pollution_renewal_date"),
    ],
    ids=["no_name", "no_type", "bad_date", "no_pollution"],
)
def test_create_vehicle_validation(admin, mutate):
    body = vehicle_body()
    mutate(body)
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A06")
def test_list_excludes_inactive(admin, cleanup):
    active = make_vehicle(admin, cleanup)
    gone = make_vehicle(admin, cleanup)
    admin.delete(f"{BASE}{gone['id']}")
    ids = [row["id"] for row in items_of(admin.get(BASE))]
    assert active["id"] in ids and gone["id"] not in ids


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A07")
def test_vehicle_dropdown(admin, cleanup):
    active = make_vehicle(admin, cleanup)
    gone = make_vehicle(admin, cleanup)
    admin.delete(f"{BASE}{gone['id']}")
    rows = admin.get(f"{BASE}dropdown").json()
    ids = [row["id"] for row in rows]
    assert active["id"] in ids and gone["id"] not in ids
    assert set(rows[0]) >= {"id", "name"}
    everything = [row["id"] for row in admin.get(f"{BASE}dropdown", params={"active_only": "false"}).json()]
    assert gone["id"] in everything


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A08")
def test_get_vehicle(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    inactive = make_vehicle(admin, cleanup)
    admin.delete(f"{BASE}{inactive['id']}")
    assert admin.get(f"{BASE}{vehicle['id']}").status_code == 200
    assert admin.get(f"{BASE}{inactive['id']}").status_code == 200
    missing = admin.get(f"{BASE}{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["detail"] == "Vehicle not found"
    assert admin.get(f"{BASE}not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A09")
def test_vehicle_routes_and_trips(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route_b = make_route(admin, cleanup, route_name=unique("trn_route_b_"))
    route_a = make_route(admin, cleanup, route_name=unique("trn_route_a_"))
    trip_two = make_trip(admin, cleanup, vehicle["id"], route_b["id"], 2)
    trip_one = make_trip(admin, cleanup, vehicle["id"], route_a["id"], 1)
    routes = admin.get(f"{BASE}{vehicle['id']}/routes").json()
    assert [row["id"] for row in routes] == [route_a["id"], route_b["id"]]
    assert set(routes[0]) >= {"id", "route_name"}
    trips = admin.get(f"{BASE}{vehicle['id']}/trips").json()
    assert [row["id"] for row in trips] == [trip_one["id"], trip_two["id"]]
    assert set(trips[0]) >= {"id", "trip_number", "route_id", "route_name"}


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A10")
def test_vehicle_route_stops(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    second = make_stop(admin, cleanup, route["id"], 2)
    first = make_stop(admin, cleanup, route["id"], 1)
    inactive = make_stop(admin, cleanup, route["id"], 3)
    admin.delete(f"/masters/route-stops/{inactive['id']}")
    make_trip(admin, cleanup, vehicle["id"], route["id"])
    response = admin.get(f"{BASE}{vehicle['id']}/routes/{route['id']}/stops")
    assert response.status_code == 200
    rows = response.json()
    assert [row["id"] for row in rows] == [first["id"], second["id"]]
    assert set(rows[0]) >= {"pickup_time", "drop_time", "fees", "number", "name"}


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A11")
def test_vehicle_route_stops_unassigned(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    response = admin.get(f"{BASE}{vehicle['id']}/routes/{route['id']}/stops")
    assert response.status_code == 404
    assert "Vehicle is not assigned to this route" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A12")
def test_vehicle_without_trips(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    assert admin.get(f"{BASE}{vehicle['id']}/routes").json() == []
    assert admin.get(f"{BASE}{vehicle['id']}/trips").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A13")
def test_put_vehicle(admin, cleanup):
    first = make_vehicle(admin, cleanup)
    second = make_vehicle(admin, cleanup)
    new_reg = unique("TRN").upper()
    body = vehicle_body(registration_number=new_reg, name="renamed bus")
    ok = admin.put(f"{BASE}{first['id']}", json=body)
    assert ok.status_code == 200, ok.text
    assert ok.json()["registration_number"] == new_reg and ok.json()["name"] == "renamed bus"
    clash = admin.put(f"{BASE}{second['id']}", json=vehicle_body(registration_number=new_reg))
    assert clash.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A14")
def test_patch_vehicle(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    response = admin.patch(f"{BASE}{vehicle['id']}", json={"driver_name": "R. Kumar", "is_active": False})
    assert response.status_code == 200
    assert response.json()["driver_name"] == "R. Kumar"
    assert vehicle["id"] not in [row["id"] for row in items_of(admin.get(BASE))]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A15")
def test_delete_vehicle_keeps_trip(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    trip = make_trip(admin, cleanup, vehicle["id"], route["id"])
    response = admin.delete(f"{BASE}{vehicle['id']}")
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert admin.get(f"/masters/trips/{trip['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A16")
@pytest.mark.parametrize("role", ROLES)
def test_vehicle_role_matrix(role_clients, admin, cleanup, role):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    make_trip(admin, cleanup, vehicle["id"], route["id"])
    client = role_clients[role]
    read = 200 if role in READ_ROLES else 403
    assert client.get(BASE).status_code == read
    assert client.get(f"{BASE}dropdown").status_code == read
    assert client.get(f"{BASE}{vehicle['id']}").status_code == read
    assert client.get(f"{BASE}{vehicle['id']}/routes").status_code == read
    assert client.get(f"{BASE}{vehicle['id']}/trips").status_code == read
    assert client.get(f"{BASE}{vehicle['id']}/routes/{route['id']}/stops").status_code == read
    if role == "admin":
        return
    assert client.post(BASE, json=vehicle_body()).status_code == 403
    assert client.put(f"{BASE}{vehicle['id']}", json=vehicle_body()).status_code == 403
    assert client.patch(f"{BASE}{vehicle['id']}", json={"driver_name": "x"}).status_code == 403
    assert client.delete(f"{BASE}{vehicle['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A16")
def test_vehicle_unauthenticated(anon):
    assert anon.get(BASE).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TRN-06-A17")
def test_vehicle_tenant_isolation(admin, tenant_b, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    make_trip(admin, cleanup, vehicle["id"], route["id"])
    assert vehicle["id"] not in [row["id"] for row in items_of(tenant_b.get(BASE))]
    assert tenant_b.get(f"{BASE}{vehicle['id']}").status_code == 404
    assert tenant_b.get(f"{BASE}{vehicle['id']}/routes").json() == []
    assert tenant_b.get(f"{BASE}{vehicle['id']}/trips").json() == []
    assert tenant_b.get(f"{BASE}{vehicle['id']}/routes/{route['id']}/stops").status_code == 404
    assert other_tenant_header(admin).get(BASE).status_code == 403
