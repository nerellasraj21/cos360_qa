import uuid
from decimal import Decimal

import pytest

from api_tests.support import items_of, unique
from api_tests.transport.helpers import (
    ROLES,
    make_pricing,
    make_route,
    make_vehicle,
    other_tenant_header,
    pricing_body,
)

BASE = "/masters/transport-pricing/"


@pytest.fixture
def plan(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    route = make_route(admin, cleanup)
    pricing = make_pricing(admin, cleanup, vehicle["id"], route["id"])
    return {"vehicle": vehicle, "route": route, "pricing": pricing}


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A01")
def test_create_pricing(admin, plan):
    pricing = plan["pricing"]
    assert pricing["vehicle_name"] == plan["vehicle"]["name"]
    assert pricing["route_name"] == plan["route"]["route_name"]
    assert pricing["amount"] == "12000.00"
    assert pricing["billing_cycle"] == "annual" and pricing["is_active"] is True
    assert pricing["start_date"] == "2026-04-01" and pricing["end_date"] == "2027-03-31"


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A02")
def test_overlapping_plan_rejected(admin, plan):
    body = pricing_body(
        plan["vehicle"]["id"], plan["route"]["id"], start_date="2026-12-01", end_date="2027-06-01"
    )
    response = admin.post(BASE, json=body)
    assert response.status_code == 400
    assert "Overlapping pricing exists" in response.text
    assert plan["pricing"]["id"] in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A03")
def test_adjacent_plan_allowed(admin, cleanup, plan):
    make_pricing(
        admin,
        cleanup,
        plan["vehicle"]["id"],
        plan["route"]["id"],
        start_date="2027-03-31",
        end_date="2028-03-30",
    )


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A04")
def test_different_cycle_and_null_route_do_not_overlap(admin, cleanup, plan):
    make_pricing(admin, cleanup, plan["vehicle"]["id"], plan["route"]["id"], billing_cycle="monthly")
    make_pricing(admin, cleanup, plan["vehicle"]["id"], None)


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A05")
def test_end_date_not_after_start(admin, plan):
    body = pricing_body(plan["vehicle"]["id"], start_date="2030-01-01", end_date="2030-01-01")
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A06")
@pytest.mark.parametrize(
    "over",
    [{"billing_cycle": "weekly"}, {"amount": "0"}, {"cycle_name": None}, {"amount": "10.005"}, {"amount": "-1"}],
    ids=["weekly", "zero", "no_cycle_name", "three_decimals", "negative"],
)
def test_create_pricing_validation(admin, plan, over):
    body = pricing_body(plan["vehicle"]["id"], start_date="2031-01-01", end_date="2031-12-31")
    for key, value in over.items():
        if value is None:
            body.pop(key)
        else:
            body[key] = value
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A06")
def test_amount_upper_bound(admin, cleanup, plan):
    pricing = make_pricing(
        admin, cleanup, plan["vehicle"]["id"], None, amount="99999999.99", start_date="2032-01-01", end_date="2032-12-31"
    )
    assert pricing["amount"] == "99999999.99"
    body = pricing_body(plan["vehicle"]["id"], None, amount="100000000.00", start_date="2033-01-01", end_date="2033-12-31")
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A07")
def test_unknown_vehicle_and_route(admin, plan):
    unknown_vehicle = admin.post(BASE, json=pricing_body(str(uuid.uuid4()), None, start_date="2034-01-01", end_date="2034-12-31"))
    assert unknown_vehicle.status_code == 404 and "Vehicle not found" in unknown_vehicle.text
    body = pricing_body(plan["vehicle"]["id"], str(uuid.uuid4()), start_date="2034-01-01", end_date="2034-12-31")
    unknown_route = admin.post(BASE, json=body)
    assert unknown_route.status_code == 404 and "Route not found" in unknown_route.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A08")
def test_list_filters_and_order(admin, cleanup, plan):
    other_vehicle = make_vehicle(admin, cleanup)
    older = plan["pricing"]
    newer = make_pricing(
        admin, cleanup, plan["vehicle"]["id"], plan["route"]["id"], billing_cycle="monthly",
        start_date="2027-06-01", end_date="2027-07-01",
    )
    foreign = make_pricing(admin, cleanup, other_vehicle["id"], None)
    gone = make_pricing(admin, cleanup, plan["vehicle"]["id"], None, start_date="2035-01-01", end_date="2035-12-31")
    admin.delete(f"{BASE}{gone['id']}")
    by_vehicle = items_of(admin.get(BASE, params={"vehicle_id": plan["vehicle"]["id"]}))
    ids = [row["id"] for row in by_vehicle]
    assert ids == [newer["id"], older["id"]]
    assert foreign["id"] not in ids and gone["id"] not in ids
    monthly = items_of(admin.get(BASE, params={"vehicle_id": plan["vehicle"]["id"], "billing_cycle": "monthly"}))
    assert [row["id"] for row in monthly] == [newer["id"]]
    everything = [row["id"] for row in items_of(admin.get(BASE))]
    assert foreign["id"] in everything


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A09")
def test_pricing_dropdown(admin, cleanup, plan):
    expired = make_pricing(
        admin, cleanup, plan["vehicle"]["id"], None, cycle_name="a_" + unique("trn_"),
        start_date="2020-01-01", end_date="2020-12-31",
    )
    response = admin.get(f"{BASE}dropdown", params={"vehicle_id": plan["vehicle"]["id"]})
    assert response.status_code == 200
    rows = response.json()
    assert set(rows[0]) == {"id", "cycle_name", "billing_cycle", "amount"}
    names = [row["cycle_name"] for row in rows]
    assert names == sorted(names)
    assert expired["id"] in [row["id"] for row in rows]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A10")
def test_dropdown_requires_vehicle(admin):
    assert admin.get(f"{BASE}dropdown").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A11")
def test_get_pricing(admin, plan):
    pricing = plan["pricing"]
    assert admin.get(f"{BASE}{pricing['id']}").status_code == 200
    admin.delete(f"{BASE}{pricing['id']}")
    inactive = admin.get(f"{BASE}{pricing['id']}")
    assert inactive.status_code == 200 and inactive.json()["is_active"] is False
    missing = admin.get(f"{BASE}{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["detail"] == "Transport pricing not found"
    assert admin.get(f"{BASE}not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A12")
def test_put_pricing(admin, plan):
    pricing = plan["pricing"]
    body = pricing_body(
        plan["vehicle"]["id"], plan["route"]["id"], amount="13500.00", cycle_name=pricing["cycle_name"]
    )
    response = admin.put(f"{BASE}{pricing['id']}", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["amount"] == "13500.00"


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A13")
def test_patch_start_date_after_end(admin, plan):
    response = admin.patch(f"{BASE}{plan['pricing']['id']}", json={"start_date": "2027-03-31"})
    assert response.status_code == 400
    assert "end_date must be after start_date" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A14")
def test_patch_into_overlap(admin, cleanup, plan):
    later = make_pricing(
        admin, cleanup, plan["vehicle"]["id"], plan["route"]["id"], start_date="2027-03-31", end_date="2028-03-30"
    )
    response = admin.patch(f"{BASE}{later['id']}", json={"start_date": "2026-12-01"})
    assert response.status_code == 400
    assert "Overlapping pricing exists" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A15")
def test_delete_frees_range(admin, plan, cleanup):
    pricing = plan["pricing"]
    response = admin.delete(f"{BASE}{pricing['id']}")
    assert response.status_code == 200 and response.json()["is_active"] is False
    replacement = admin.post(BASE, json=pricing_body(plan["vehicle"]["id"], plan["route"]["id"]))
    assert replacement.status_code == 201, replacement.text
    cleanup.delete_later(admin, f"{BASE}{replacement.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A16")
def test_third_overlap_is_a_clean_400(admin, cleanup):
    vehicle = make_vehicle(admin, cleanup)
    first = make_pricing(admin, cleanup, vehicle["id"], None, start_date="2036-01-01", end_date="2036-06-30")
    second = admin.post(
        BASE, json=pricing_body(vehicle["id"], None, start_date="2036-06-30", end_date="2036-12-31")
    )
    assert second.status_code == 201
    cleanup.delete_later(admin, f"{BASE}{second.json()['id']}")
    assert first["id"]
    response = admin.post(
        BASE, json=pricing_body(vehicle["id"], None, start_date="2036-03-01", end_date="2036-09-30")
    )
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A17")
@pytest.mark.parametrize("role", ROLES)
def test_pricing_role_matrix(role_clients, plan, admin, role):
    client = role_clients[role]
    pricing = plan["pricing"]
    expected = 200 if role == "admin" else 403
    assert client.get(BASE).status_code == expected
    assert client.get(f"{BASE}dropdown", params={"vehicle_id": plan["vehicle"]["id"]}).status_code == expected
    assert client.get(f"{BASE}{pricing['id']}").status_code == expected
    if role == "admin":
        return
    body = pricing_body(plan["vehicle"]["id"], None, start_date="2037-01-01", end_date="2037-12-31")
    assert client.post(BASE, json=body).status_code == 403
    assert client.put(f"{BASE}{pricing['id']}", json=body).status_code == 403
    assert client.patch(f"{BASE}{pricing['id']}", json={"cycle_name": "x"}).status_code == 403
    assert client.delete(f"{BASE}{pricing['id']}").status_code == 403
    assert admin.get(f"{BASE}{pricing['id']}").json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A17")
def test_pricing_unauthenticated(anon):
    assert anon.get(BASE).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TRN-08-A18")
def test_pricing_tenant_isolation(admin, tenant_b, plan):
    pricing = plan["pricing"]
    assert pricing["id"] not in [row["id"] for row in items_of(tenant_b.get(BASE))]
    assert tenant_b.get(f"{BASE}{pricing['id']}").status_code == 404
    response = tenant_b.post(BASE, json=pricing_body(plan["vehicle"]["id"], None))
    assert response.status_code == 404 and "Vehicle not found" in response.text
    assert other_tenant_header(admin).get(BASE).status_code == 403
    assert Decimal(pricing["amount"]) == Decimal("12000.00")
