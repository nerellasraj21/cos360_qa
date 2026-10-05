import uuid

import pytest

from api_tests.support import items_of
from api_tests.transport.helpers import (
    ROLES,
    READ_ROLES,
    make_assignment,
    make_chain,
    make_route,
    make_student,
    make_trip,
    make_vehicle,
    other_tenant_header,
)

BASE = "/masters/trips/"


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A01")
def test_create_trip(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    trip = make_trip(admin, cleanup, vehicle["id"], route["id"], 1)
    assert trip["driver_id"] is None
    assert trip["trip_number"] == 1
    assert trip["created_at"] and trip["updated_at"]
    assert trip["vehicle_id"] == vehicle["id"] and trip["route_id"] == route["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A02")
def test_duplicate_vehicle_route(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    make_trip(admin, cleanup, vehicle["id"], route["id"], 1)
    response = admin.post(BASE, json={"vehicle_id": vehicle["id"], "route_id": route["id"], "trip_number": 2})
    assert response.status_code == 400
    assert "This vehicle is already assigned to this route" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A03")
def test_same_vehicle_second_route(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    first = make_route(admin, cleanup)
    second = make_route(admin, cleanup)
    make_trip(admin, cleanup, vehicle["id"], first["id"], 1)
    make_trip(admin, cleanup, vehicle["id"], second["id"], 2)


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A04")
def test_create_trip_with_driver(admin, cleanup, logins):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    driver_id = logins["staff"]["user"]["id"]
    trip = make_trip(admin, cleanup, vehicle["id"], route["id"], 1, driver_id=driver_id)
    assert trip["driver_id"] == driver_id


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A05")
def test_create_trip_unknown_references(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    unknown_vehicle = admin.post(
        BASE, json={"vehicle_id": str(uuid.uuid4()), "route_id": route["id"], "trip_number": 1}
    )
    assert unknown_vehicle.status_code >= 400
    unknown_driver = admin.post(
        BASE,
        json={"vehicle_id": vehicle["id"], "route_id": route["id"], "trip_number": 1, "driver_id": str(uuid.uuid4())},
    )
    assert unknown_driver.status_code >= 400
    assert admin.get(f"/masters/vehicles/{vehicle['id']}/trips").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A06")
def test_create_trip_validation(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    assert admin.post(BASE, json={"route_id": route["id"], "trip_number": 1}).status_code == 422
    body = {"vehicle_id": vehicle["id"], "route_id": route["id"], "trip_number": "a"}
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A07")
def test_list_trips(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    routes = [make_route(admin, cleanup) for _ in range(3)]
    trips = [make_trip(admin, cleanup, vehicle["id"], route["id"], index + 1) for index, route in enumerate(routes)]
    admin.delete(f"/masters/vehicles/{vehicle['id']}")
    ids = [row["id"] for row in items_of(admin.get(BASE))]
    assert {trip["id"] for trip in trips} <= set(ids)


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A08")
def test_get_trip(admin, cleanup):
    chain = make_chain(admin, cleanup)
    trip = chain["trip"]
    assert admin.get(f"{BASE}{trip['id']}").json()["id"] == trip["id"]
    missing = admin.get(f"{BASE}{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["detail"] == "Trip not found"
    assert admin.get(f"{BASE}not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A09")
def test_put_trip(admin, cleanup):
    chain = make_chain(admin, cleanup)
    trip = chain["trip"]
    body = {"vehicle_id": trip["vehicle_id"], "route_id": trip["route_id"], "trip_number": 5}
    response = admin.put(f"{BASE}{trip['id']}", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["trip_number"] == 5


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A10")
def test_patch_trip_to_served_route(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    first = make_route(admin, cleanup)
    second = make_route(admin, cleanup)
    make_trip(admin, cleanup, vehicle["id"], first["id"], 1)
    other = make_trip(admin, cleanup, vehicle["id"], second["id"], 2)
    response = admin.patch(f"{BASE}{other['id']}", json={"route_id": first["id"]})
    assert response.status_code == 400
    assert "This vehicle is already assigned to this route" in response.text
    assert admin.patch(f"{BASE}{other['id']}", json={"trip_number": 9}).json()["trip_number"] == 9


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A11")
def test_delete_trip_without_assignments(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    trip = make_trip(admin, cleanup, vehicle["id"], route["id"])
    response = admin.delete(f"{BASE}{trip['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == trip["id"]
    assert admin.get(f"{BASE}{trip['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A12")
def test_delete_trip_with_assignment(admin, cleanup, academic_year_id):
    chain = make_chain(admin, cleanup)
    student = make_student(admin, cleanup, academic_year_id)
    make_assignment(admin, cleanup, student["student_id"], chain["trip"]["id"], chain["stop"]["id"])
    response = admin.delete(f"{BASE}{chain['trip']['id']}")
    assert response.status_code >= 400
    assert admin.get(f"{BASE}{chain['trip']['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A13")
@pytest.mark.parametrize("role", ROLES)
def test_trip_role_matrix(role_clients, admin, cleanup, role):
    chain = make_chain(admin, cleanup)
    trip = chain["trip"]
    client = role_clients[role]
    read = 200 if role in READ_ROLES else 403
    assert client.get(BASE).status_code == read
    assert client.get(f"{BASE}{trip['id']}").status_code == read
    if role == "admin":
        return
    other_vehicle = make_vehicle(admin, cleanup)
    other_route = make_route(admin, cleanup)
    create_body = {"vehicle_id": other_vehicle["id"], "route_id": other_route["id"], "trip_number": 1}
    write_roles = ("staff",)
    if role in write_roles:
        created = client.post(BASE, json=create_body)
        assert created.status_code == 201, created.text
        cleanup.delete_later(admin, f"{BASE}{created.json()['id']}")
        put_body = {"vehicle_id": trip["vehicle_id"], "route_id": trip["route_id"], "trip_number": 3}
        assert client.put(f"{BASE}{trip['id']}", json=put_body).status_code == 200
        assert client.patch(f"{BASE}{trip['id']}", json={"trip_number": 4}).status_code == 200
    else:
        assert client.post(BASE, json=create_body).status_code == 403
        put_body = {"vehicle_id": trip["vehicle_id"], "route_id": trip["route_id"], "trip_number": 3}
        assert client.put(f"{BASE}{trip['id']}", json=put_body).status_code == 403
        assert client.patch(f"{BASE}{trip['id']}", json={"trip_number": 4}).status_code == 403
    assert client.delete(f"{BASE}{trip['id']}").status_code == 403
    assert admin.get(f"{BASE}{trip['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A13")
def test_admin_can_delete_trip(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    trip = make_trip(admin, cleanup, vehicle["id"], route["id"])
    assert admin.delete(f"{BASE}{trip['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A13")
def test_trip_unauthenticated(anon):
    assert anon.get(BASE).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TRN-07-A14")
def test_trip_tenant_isolation(admin, tenant_b, cleanup):
    chain = make_chain(admin, cleanup)
    trip = chain["trip"]
    assert trip["id"] not in [row["id"] for row in items_of(tenant_b.get(BASE))]
    assert tenant_b.get(f"{BASE}{trip['id']}").status_code == 404
    assert other_tenant_header(admin).get(BASE).status_code == 403
