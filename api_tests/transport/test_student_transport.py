import uuid

import pytest

from api_tests.support import items_of
from api_tests.transport.helpers import (
    assign_body,
    make_assignment,
    make_chain,
    make_pricing,
    make_route,
    make_stop,
    make_student,
    make_trip,
    make_vehicle,
    other_tenant_header,
)

BASE = "/students/student-transport/"


@pytest.fixture
def setup(admin, cleanup, academic_year_id):
    chain = make_chain(admin, cleanup, fees=1200)
    student = make_student(admin, cleanup, academic_year_id)
    return {"chain": chain, "student": student}


def _ids(setup):
    return setup["student"]["student_id"], setup["chain"]["trip"]["id"], setup["chain"]["stop"]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A01")
def test_create_assignment(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    data = make_assignment(admin, cleanup, student_id, trip_id, stop_id, fee_per_term=1200)
    assert data["fee_per_term"] == 1200.0
    assert data["pricing"] is None
    assert data["student"]["id"] == student_id
    assert data["trip"]["id"] == trip_id
    assert data["trip"]["route"]["id"] == setup["chain"]["route"]["id"]
    assert data["trip"]["vehicle"]["id"] == setup["chain"]["vehicle"]["id"]
    assert data["stop"]["id"] == stop_id


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A02")
def test_fee_defaults_from_stop(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    body = {"student_id": student_id, "trip_id": trip_id, "stop_id": stop_id}
    response = admin.post(BASE, json=body)
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{BASE}{response.json()['id']}")
    assert response.json()["fee_per_term"] == 1200.0


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A03")
def test_no_fee_and_stop_without_fee(admin, cleanup, academic_year_id):
    route = make_route(admin, cleanup)
    stop = make_stop(admin, cleanup, route["id"], 1, fees=None)
    vehicle = make_vehicle(admin, cleanup)
    trip = make_trip(admin, cleanup, vehicle["id"], route["id"])
    student = make_student(admin, cleanup, academic_year_id)
    response = admin.post(BASE, json={"student_id": student["student_id"], "trip_id": trip["id"], "stop_id": stop["id"]})
    assert response.status_code == 400
    assert "This stop has no default fee" in response.text
    assert "enter the amount manually" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A04")
@pytest.mark.parametrize("fee", [-1, 0])
def test_non_positive_fee_rejected(admin, setup, fee):
    student_id, trip_id, stop_id = _ids(setup)
    response = admin.post(BASE, json=assign_body(student_id, trip_id, stop_id, fee_per_term=fee))
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A05")
def test_duplicate_student_trip(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    response = admin.post(BASE, json=assign_body(student_id, trip_id, stop_id))
    assert response.status_code == 422
    assert "Student already has transport assignment for this trip" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A06")
def test_student_on_second_trip(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    second_route = make_route(admin, cleanup)
    second_stop = make_stop(admin, cleanup, second_route["id"], 1, fees=800)
    second_trip = make_trip(admin, cleanup, setup["chain"]["vehicle"]["id"], second_route["id"], 2)
    make_assignment(admin, cleanup, student_id, second_trip["id"], second_stop["id"], fee_per_term=800)
    rows = admin.get(f"{BASE}student/{student_id}").json()
    assert len(rows) == 2


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A07")
def test_unknown_references(admin, setup):
    student_id, trip_id, stop_id = _ids(setup)
    unknown_student = admin.post(BASE, json=assign_body(str(uuid.uuid4()), trip_id, stop_id))
    assert unknown_student.status_code == 404 and "Student not found" in unknown_student.text
    unknown_trip = admin.post(BASE, json=assign_body(student_id, str(uuid.uuid4()), stop_id))
    assert unknown_trip.status_code == 404 and "Trip not found" in unknown_trip.text
    unknown_stop = admin.post(BASE, json=assign_body(student_id, trip_id, str(uuid.uuid4())))
    assert unknown_stop.status_code == 404 and "Route stop not found" in unknown_stop.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A08")
def test_stop_of_another_route(admin, cleanup, setup):
    student_id, trip_id, _ = _ids(setup)
    other_route = make_route(admin, cleanup)
    foreign_stop = make_stop(admin, cleanup, other_route["id"], 1)
    response = admin.post(BASE, json=assign_body(student_id, trip_id, foreign_stop["id"]))
    assert response.status_code == 400
    assert "The selected stop does not belong to the route of the selected trip" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A09")
def test_assignment_with_pricing_plan(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    plan = make_pricing(admin, cleanup, setup["chain"]["vehicle"]["id"], setup["chain"]["route"]["id"])
    body = {"student_id": student_id, "trip_id": trip_id, "stop_id": stop_id, "pricing_id": plan["id"]}
    response = admin.post(BASE, json=body)
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{BASE}{response.json()['id']}")
    data = response.json()
    assert data["pricing"]["cycle_name"] == plan["cycle_name"]
    assert data["pricing"]["billing_cycle"] == "annual"
    assert data["pricing"]["amount"] == "12000.00"
    assert data["fee_per_term"] == 1200.0


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A10")
def test_inactive_or_unknown_pricing(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    plan = make_pricing(admin, cleanup, setup["chain"]["vehicle"]["id"], setup["chain"]["route"]["id"])
    admin.delete(f"/masters/transport-pricing/{plan['id']}")
    for pricing_id in (plan["id"], str(uuid.uuid4())):
        response = admin.post(BASE, json=assign_body(student_id, trip_id, stop_id, pricing_id=pricing_id))
        assert response.status_code == 404
        assert "Transport pricing not found or inactive" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A11")
def test_zero_stop_fee_means_no_default(admin, cleanup, academic_year_id):
    route = make_route(admin, cleanup)
    stop = make_stop(admin, cleanup, route["id"], 1, fees=0)
    vehicle = make_vehicle(admin, cleanup)
    trip = make_trip(admin, cleanup, vehicle["id"], route["id"])
    student = make_student(admin, cleanup, academic_year_id)
    explicit_zero = admin.post(
        BASE, json=assign_body(student["student_id"], trip["id"], stop["id"], fee_per_term=0)
    )
    assert explicit_zero.status_code == 422
    implicit = admin.post(BASE, json={"student_id": student["student_id"], "trip_id": trip["id"], "stop_id": stop["id"]})
    assert implicit.status_code == 400 and "no default fee" in implicit.text
    assert admin.get(BASE).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A12")
def test_list_assignments(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    created = make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    response = admin.get(BASE)
    assert response.status_code == 200
    rows = items_of(response)
    match = [row for row in rows if row["id"] == created["id"]]
    assert match
    row = match[0]
    assert row["student"]["id"] == student_id
    assert row["trip"]["route"] and row["trip"]["vehicle"] and row["stop"]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A13")
def test_patch_fee(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    created = make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    response = admin.patch(f"{BASE}{created['id']}", json={"fee_per_term": 1300})
    assert response.status_code == 200, response.text
    assert response.json()["fee_per_term"] == 1300.0


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A14")
@pytest.mark.parametrize("fee", [0, -5])
def test_patch_non_positive_fee(admin, cleanup, setup, fee):
    student_id, trip_id, stop_id = _ids(setup)
    created = make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    assert admin.patch(f"{BASE}{created['id']}", json={"fee_per_term": fee}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A15")
def test_patch_unknown_references(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    created = make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    trip = admin.patch(f"{BASE}{created['id']}", json={"trip_id": str(uuid.uuid4())})
    assert trip.status_code == 404 and "Trip not found" in trip.text
    stop = admin.patch(f"{BASE}{created['id']}", json={"stop_id": str(uuid.uuid4())})
    assert stop.status_code == 404 and "Route stop not found" in stop.text
    missing = admin.patch(f"{BASE}{uuid.uuid4()}", json={"fee_per_term": 5})
    assert missing.status_code == 404 and "Transport assignment not found" in missing.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A16")
def test_patch_clear_pricing(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    plan = make_pricing(admin, cleanup, setup["chain"]["vehicle"]["id"], setup["chain"]["route"]["id"])
    created = make_assignment(admin, cleanup, student_id, trip_id, stop_id, pricing_id=plan["id"])
    assert created["pricing"] is not None
    response = admin.patch(f"{BASE}{created['id']}", json={"pricing_id": None})
    assert response.status_code == 200
    assert response.json()["pricing"] is None


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A17")
def test_delete_assignment(admin, setup):
    student_id, trip_id, stop_id = _ids(setup)
    created = admin.post(BASE, json=assign_body(student_id, trip_id, stop_id)).json()
    response = admin.delete(f"{BASE}{created['id']}")
    assert response.status_code == 204
    after = admin.get(f"{BASE}student/{student_id}")
    assert after.status_code == 200 and after.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A18")
def test_delete_unknown_assignment(admin):
    response = admin.delete(f"{BASE}{uuid.uuid4()}")
    assert response.status_code == 404
    assert "Transport assignment not found" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A19")
@pytest.mark.parametrize("role", ["teacher", "student", "parent"])
def test_denied_roles(role_clients, admin, cleanup, setup, role):
    student_id, trip_id, stop_id = _ids(setup)
    created = make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    client = role_clients[role]
    assert client.post(BASE, json=assign_body(student_id, trip_id, stop_id)).status_code == 403
    assert client.get(BASE).status_code == 403
    assert client.patch(f"{BASE}{created['id']}", json={"fee_per_term": 1}).status_code == 403
    assert client.delete(f"{BASE}{created['id']}").status_code == 403
    assert admin.get(f"{BASE}student/{student_id}").json()[0]["fee_per_term"] == 1200.0


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A19")
def test_staff_matrix(staff, admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    response = staff.post(BASE, json=assign_body(student_id, trip_id, stop_id))
    assert response.status_code == 201, response.text
    created = response.json()
    cleanup.delete_later(admin, f"{BASE}{created['id']}")
    assert staff.get(BASE).status_code == 200
    assert staff.patch(f"{BASE}{created['id']}", json={"fee_per_term": 1500}).status_code == 200
    assert staff.delete(f"{BASE}{created['id']}").status_code == 403
    assert admin.get(f"{BASE}student/{student_id}").json()[0]["fee_per_term"] == 1500.0


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A19")
def test_assignment_unauthenticated(anon):
    assert anon.get(BASE).status_code == 401
    body = {"student_id": str(uuid.uuid4()), "trip_id": str(uuid.uuid4()), "stop_id": str(uuid.uuid4())}
    assert anon.post(BASE, json=body).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TRN-09-A20")
def test_assignment_tenant_isolation(admin, tenant_b, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    created = make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    assert created["id"] not in [row["id"] for row in items_of(tenant_b.get(BASE))]
    response = tenant_b.post(BASE, json=assign_body(student_id, trip_id, stop_id))
    assert response.status_code == 404
    assert tenant_b.patch(f"{BASE}{created['id']}", json={"fee_per_term": 1}).status_code == 404
    assert tenant_b.delete(f"{BASE}{created['id']}").status_code == 404
    assert other_tenant_header(admin).get(BASE).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TRN-11-A01")
def test_extra_fee_term_ignored(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    body = assign_body(student_id, trip_id, stop_id, fee_term_id=str(uuid.uuid4()))
    response = admin.post(BASE, json=body)
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{BASE}{response.json()['id']}")
    assert "fee_term_id" not in response.json()


@pytest.mark.api
@pytest.mark.tc("TC-TRN-11-A02")
def test_put_not_routed(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    created = make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    assert admin.put(f"{BASE}{created['id']}", json={"fee_per_term": 5}).status_code == 405


@pytest.mark.api
@pytest.mark.tc("TC-TRN-11-A03")
def test_single_get_not_routed(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    created = make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    assert admin.get(f"{BASE}{created['id']}").status_code == 405


@pytest.mark.api
@pytest.mark.tc("TC-TRN-11-A04")
def test_student_trips_router_not_mounted(admin):
    assert admin.get("/student-trips/").status_code == 404
    assert admin.get("/students/student-trips/").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TRN-11-A05")
def test_patch_delete_through_screen_paths(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    created = admin.post(BASE, json=assign_body(student_id, trip_id, stop_id)).json()
    assert admin.patch(f"{BASE}{created['id']}", json={"fee_per_term": 900}).status_code == 200
    assert admin.delete(f"{BASE}{created['id']}").status_code == 204


@pytest.mark.api
@pytest.mark.tc("TC-TRN-12-A01")
def test_assignment_creates_no_fee_data(admin, cleanup, setup, academic_year_id):
    student_id, trip_id, stop_id = _ids(setup)
    before = admin.get("/fee/student-mappings/", params={"student_id": student_id})
    history_before = admin.get(
        f"/fee/transactions/student/{student_id}/history", params={"academic_year_id": academic_year_id}
    )
    make_assignment(admin, cleanup, student_id, trip_id, stop_id, fee_per_term=1200)
    after = admin.get("/fee/student-mappings/", params={"student_id": student_id})
    history_after = admin.get(
        f"/fee/transactions/student/{student_id}/history", params={"academic_year_id": academic_year_id}
    )
    assert before.status_code == 200 and after.status_code == 200
    assert after.json() == before.json()
    assert history_after.status_code == history_before.status_code
    assert history_after.json() == history_before.json()


@pytest.mark.api
@pytest.mark.tc("TC-TRN-12-A02")
def test_delete_assignment_leaves_fee_data(admin, setup, academic_year_id):
    student_id, trip_id, stop_id = _ids(setup)
    created = admin.post(BASE, json=assign_body(student_id, trip_id, stop_id)).json()
    before = admin.get("/fee/student-mappings/", params={"student_id": student_id}).json()
    assert admin.delete(f"{BASE}{created['id']}").status_code == 204
    after = admin.get("/fee/student-mappings/", params={"student_id": student_id}).json()
    assert after == before


@pytest.mark.api
@pytest.mark.tc("TC-TRN-12-A03")
def test_fee_collection_report_unchanged(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    mine = {"class_id": setup["student"]["class_id"], "section_id": setup["student"]["section_id"]}
    before = admin.get("/reports/fees/collection-summary", params=mine)
    stats_before = admin.get("/reports/fees/collection-summary/stats", params=mine)
    make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    after = admin.get("/reports/fees/collection-summary", params=mine)
    stats_after = admin.get("/reports/fees/collection-summary/stats", params=mine)
    assert before.status_code == 200 and after.status_code == 200
    assert after.json()["total_count"] == before.json()["total_count"] == 0
    assert stats_after.status_code == stats_before.status_code


@pytest.mark.api
@pytest.mark.tc("TC-TRN-12-A04")
def test_fee_visible_only_on_assignment_endpoint(admin, cleanup, setup):
    student_id, trip_id, stop_id = _ids(setup)
    created = make_assignment(admin, cleanup, student_id, trip_id, stop_id)
    admin.patch(f"{BASE}{created['id']}", json={"fee_per_term": 1300})
    rows = items_of(admin.get(BASE))
    match = [row for row in rows if row["id"] == created["id"]]
    assert match and match[0]["fee_per_term"] == 1300.0
