import pytest

from api_tests.students import helpers as h
from api_tests.support import Cleanup, unique

UNKNOWN = "00000000-0000-0000-0000-000000000001"
BASE = "/students/student-transport"
ROLES = ["admin", "staff", "teacher", "student", "parent"]


class Transport:
    pass


@pytest.fixture(scope="module")
def tr(admin):
    stack = Cleanup()
    fx = Transport()
    tag = unique("stu_t")

    def route(suffix):
        response = admin.post(
            "/masters/routes/",
            json={
                "route_name": f"{tag}route{suffix}",
                "starting_stop": "A",
                "ending_stop": "B",
                "number_of_stops": 2,
                "route_type": "Pickup",
                "trip_type": "Morning",
                "start_time": "07:00:00",
                "end_time": "08:00:00",
                "is_active": True,
            },
        )
        assert response.status_code == 201, response.text
        stack.delete_later(admin, f"/masters/routes/{response.json()['id']}")
        return response.json()["id"]

    def stop(route_id, suffix, fees=None):
        body = {
            "route_id": route_id,
            "name": f"{tag}stop{suffix}",
            "number": 1,
            "reaching_time": "07:10:00",
            "pickup_time": "07:10:00",
            "drop_time": "16:00:00",
            "is_active": True,
        }
        if fees is not None:
            body["fees"] = fees
        response = admin.post("/masters/route-stops/", json=body)
        assert response.status_code == 201, response.text
        stack.delete_later(admin, f"/masters/route-stops/{response.json()['id']}")
        return response.json()["id"]

    r1, r2 = route("1"), route("2")
    fx.stop1 = stop(r1, "1", 1000)
    fx.stop2 = stop(r2, "2")
    vehicle = admin.post(
        "/masters/vehicles/",
        json={
            "name": f"{tag}bus",
            "registration_number": tag,
            "vehicle_type": "Bus",
            "last_inspected_date": "2026-05-20",
            "pollution_renewal_date": "2026-05-25",
            "fees": 1500,
            "driver_name": "Driver",
            "co_driver_name": "Helper",
            "driving_licence_no": "TS0920110012345",
            "driving_licence_exp_date": "2031-03-31",
            "bus_insurance_vendor": "Insurer",
            "number_of_trips": 2,
            "insurance_expiry_date": "2027-03-31",
            "is_ac": False,
            "is_active": True,
        },
    )
    assert vehicle.status_code == 201, vehicle.text
    vehicle_id = vehicle.json()["id"]
    stack.delete_later(admin, f"/masters/vehicles/{vehicle_id}")
    trips = []
    for number, route_id in ((1, r1), (2, r2)):
        created = admin.post("/masters/trips/", json={"vehicle_id": vehicle_id, "route_id": route_id, "trip_number": number})
        assert created.status_code == 201, created.text
        stack.delete_later(admin, f"/masters/trips/{created.json()['id']}")
        trips.append(created.json()["id"])
    fx.trip1, fx.trip2 = trips
    pricing = admin.post(
        "/masters/transport-pricing/",
        json={
            "vehicle_id": vehicle_id,
            "route_id": r1,
            "billing_cycle": "annual",
            "cycle_name": tag,
            "amount": 12000,
            "start_date": "2026-06-01",
            "end_date": "2027-03-31",
            "is_active": True,
        },
    )
    assert pricing.status_code == 201, pricing.text
    stack.delete_later(admin, f"/masters/transport-pricing/{pricing.json()['id']}")
    fx.pricing = pricing.json()["id"]
    yield fx
    stack.run()


def assign(client, student_id, trip, stop, **extra):
    return client.post(f"{BASE}/", json={"student_id": student_id, "trip_id": trip, "stop_id": stop, **extra})


def assigned(admin, cleanup, student_id, trip, stop, **extra):
    response = assign(admin, student_id, trip, stop, **extra)
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{BASE}/{response.json()['id']}")
    return response.json()


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A01")
def test_assign_with_all_fields(admin, tr, family, cleanup):
    body = assigned(
        admin, cleanup, family.c1.student_id, tr.trip1, tr.stop1, fee_per_term=1500, pricing_id=tr.pricing
    )
    assert body["fee_per_term"] == 1500
    assert body["pricing_id"] == tr.pricing
    assert body["student"]["id"] == family.c1.student_id
    assert body["trip"]["id"] == tr.trip1 and body["trip"]["route"]["id"] and body["trip"]["vehicle"]["id"]
    assert body["stop"]["id"] == tr.stop1
    assert body["pricing"]["id"] == tr.pricing


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A02")
def test_fee_defaults_from_stop(admin, tr, family, cleanup):
    body = assigned(admin, cleanup, family.c1.student_id, tr.trip1, tr.stop1)
    assert body["fee_per_term"] == 1000


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A02")
def test_stop_without_fee_needs_explicit_fee(admin, tr, family):
    response = assign(admin, family.c1.student_id, tr.trip2, tr.stop2)
    assert response.status_code == 400
    assert "no default fee" in response.json()["detail"]["message"]


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A03")
def test_duplicate_trip_assignment(admin, tr, family, cleanup):
    assigned(admin, cleanup, family.c1.student_id, tr.trip1, tr.stop1)
    again = assign(admin, family.c1.student_id, tr.trip1, tr.stop1)
    assert again.status_code == 422
    assert again.json()["detail"]["message"] == "Student already has transport assignment for this trip"


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A04")
def test_unknown_references(admin, tr, family):
    sid = family.c1.student_id
    assert assign(admin, UNKNOWN, tr.trip1, tr.stop1, fee_per_term=5).status_code == 404
    assert assign(admin, sid, UNKNOWN, tr.stop1, fee_per_term=5).status_code == 404
    assert assign(admin, sid, tr.trip1, UNKNOWN, fee_per_term=5).status_code == 404
    unknown_pricing = assign(admin, sid, tr.trip1, tr.stop1, fee_per_term=5, pricing_id=UNKNOWN)
    assert unknown_pricing.status_code == 404
    assert "pricing" in unknown_pricing.json()["detail"]["message"].lower()


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A05")
@pytest.mark.parametrize("fee", [0, -1])
def test_fee_boundary_on_create(admin, tr, family, fee):
    assert assign(admin, family.c1.student_id, tr.trip1, tr.stop1, fee_per_term=fee).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A06")
def test_patch_assignment(admin, tr, family, cleanup):
    created = assigned(admin, cleanup, family.c1.student_id, tr.trip1, tr.stop1, fee_per_term=1500)
    response = admin.patch(
        f"{BASE}/{created['id']}", json={"trip_id": tr.trip2, "stop_id": tr.stop2, "fee_per_term": 2000}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trip_id"] == tr.trip2 and body["stop_id"] == tr.stop2 and body["fee_per_term"] == 2000
    assert admin.patch(f"{BASE}/{created['id']}", json={"fee_per_term": 0}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A07")
def test_patch_and_delete_unknown_assignment(admin):
    assert admin.patch(f"{BASE}/{UNKNOWN}", json={"fee_per_term": 3}).status_code == 404
    assert admin.delete(f"{BASE}/{UNKNOWN}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A08")
def test_delete_assignment(admin, tr, family):
    created = assign(admin, family.c2.student_id, tr.trip1, tr.stop1).json()
    assert admin.delete(f"{BASE}/{created['id']}").status_code == 204
    after = admin.get(f"{BASE}/student/{family.c2.student_id}")
    assert after.status_code == 200
    assert after.json() == []
    assert admin.delete(f"{BASE}/{created['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A09")
@pytest.mark.parametrize("role", ["admin", "staff"])
def test_staff_views_list_and_by_student(role_clients, tr, family, cleanup, admin, role):
    created = assigned(admin, cleanup, family.c1.student_id, tr.trip1, tr.stop1)
    listing = role_clients[role].get(f"{BASE}/")
    assert listing.status_code == 200
    assert created["id"] in [a["id"] for a in listing.json()]
    by_student = role_clients[role].get(f"{BASE}/student/{family.c1.student_id}")
    assert by_student.status_code == 200
    assert [a["id"] for a in by_student.json()] == [created["id"]]


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A10")
def test_student_reads_only_own_assignment(admin, tr, family, cleanup):
    created = assigned(admin, cleanup, family.c1.student_id, tr.trip1, tr.stop1)
    own = family.c1_student.get(f"{BASE}/student/{family.c1.student_id}")
    assert own.status_code == 200
    assert [a["id"] for a in own.json()] == [created["id"]]
    other = family.c1_student.get(f"{BASE}/student/{family.other.student_id}")
    assert other.status_code == 403
    assert other.json()["detail"] == "You can only view your own transport assignment"


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A11")
def test_parent_reads_only_linked_children(admin, tr, family, cleanup):
    created = assigned(admin, cleanup, family.c2.student_id, tr.trip1, tr.stop1)
    linked = family.parent.get(f"{BASE}/student/{family.c2.student_id}")
    assert linked.status_code == 200
    assert [a["id"] for a in linked.json()] == [created["id"]]
    other = family.parent.get(f"{BASE}/student/{family.other.student_id}")
    assert other.status_code == 403
    assert other.json()["detail"] == "You can only view transport for your own children"


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A12")
@pytest.mark.parametrize(
    "role,status", [("admin", 201), ("staff", 201), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_assign_permission_matrix(role_clients, admin, tr, family, cleanup, role, status):
    response = assign(role_clients[role], family.other.student_id, tr.trip1, tr.stop1)
    assert response.status_code == status
    if status == 201:
        cleanup.delete_later(admin, f"{BASE}/{response.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A12")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_patch_and_list_permission_matrix(role_clients, admin, tr, family, cleanup, role, status):
    created = assigned(admin, cleanup, family.other.student_id, tr.trip1, tr.stop1)
    assert role_clients[role].patch(f"{BASE}/{created['id']}", json={"fee_per_term": 1200}).status_code == status
    assert role_clients[role].get(f"{BASE}/").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A12")
def test_delete_and_teacher_read_matrix(role_clients, admin, tr, family):
    created = assign(admin, family.other.student_id, tr.trip1, tr.stop1).json()
    for role in ("staff", "teacher", "student", "parent"):
        assert role_clients[role].delete(f"{BASE}/{created['id']}").status_code == 403
    assert admin.delete(f"{BASE}/{created['id']}").status_code == 204
    assert role_clients["teacher"].get(f"{BASE}/student/{family.other.student_id}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A13")
def test_transport_requires_token(anon, tr, family):
    sid = family.c1.student_id
    assert anon.post(f"{BASE}/", json={"student_id": sid, "trip_id": tr.trip1, "stop_id": tr.stop1}).status_code == 401
    assert anon.get(f"{BASE}/").status_code == 401
    assert anon.get(f"{BASE}/student/{sid}").status_code == 401
    assert anon.patch(f"{BASE}/{UNKNOWN}", json={"fee_per_term": 3}).status_code == 401
    assert anon.delete(f"{BASE}/{UNKNOWN}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-21-A14")
def test_transport_tenant_isolation(admin, tenant_b, tenant_b_name, tr, family, cleanup):
    assert assign(tenant_b, family.c1.student_id, tr.trip1, tr.stop1, fee_per_term=5).status_code == 404
    header = {"cschema": tenant_b_name}
    body = {"student_id": family.c1.student_id, "trip_id": tr.trip1, "stop_id": tr.stop1}
    assert admin.post(f"{BASE}/", json=body, headers=header).status_code == 403
    assert admin.get(f"{BASE}/", headers=header).status_code == 403
    created = assigned(admin, cleanup, family.c1.student_id, tr.trip1, tr.stop1)
    assert created["id"] not in [a["id"] for a in tenant_b.get(f"{BASE}/").json()]
