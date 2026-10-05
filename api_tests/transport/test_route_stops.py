import uuid

import pytest

from api_tests.support import items_of
from api_tests.transport.helpers import ROLES, READ_ROLES, make_route, make_stop, other_tenant_header, stop_body

BASE = "/masters/route-stops/"


@pytest.fixture
def route(admin, cleanup):
    return make_route(admin, cleanup)


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A01")
def test_create_stop(admin, cleanup, route):
    body = stop_body(route["id"], 1, fees=1200)
    response = admin.post(BASE, json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}{data['id']}")
    assert data["route_name"] == route["route_name"]
    assert data["fees"] == 1200.0
    assert data["pickup_time"] == "07:10:00" and data["drop_time"] == "08:20:00"
    assert data["reaching_time"] == "07:10:00"
    assert data["is_active"] is True and data["number"] == 1


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A02")
def test_duplicate_stop_number(admin, cleanup, route):
    make_stop(admin, cleanup, route["id"], 1)
    response = admin.post(BASE, json=stop_body(route["id"], 1))
    assert response.status_code == 400
    assert "Stop number 1 already exists on this route" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A03")
def test_same_number_on_other_route(admin, cleanup, route):
    other = make_route(admin, cleanup)
    make_stop(admin, cleanup, route["id"], 1)
    make_stop(admin, cleanup, other["id"], 1)


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A04")
@pytest.mark.parametrize(
    "mutate",
    [lambda b: b.pop("reaching_time"), lambda b: b.pop("route_id"), lambda b: b.update(number="x")],
    ids=["no_reaching_time", "no_route", "number_text"],
)
def test_create_stop_validation(admin, route, mutate):
    body = stop_body(route["id"], 1)
    mutate(body)
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A05")
def test_create_stop_unknown_route(admin):
    response = admin.post(BASE, json=stop_body(str(uuid.uuid4()), 1))
    assert response.status_code >= 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A06")
def test_create_stop_fractional_fee(admin, cleanup, route):
    response = admin.post(BASE, json=stop_body(route["id"], 1, fees=25.5))
    if response.status_code == 201:
        cleanup.delete_later(admin, f"{BASE}{response.json()['id']}")
        assert admin.get(f"{BASE}{response.json()['id']}").json()["fees"] == 25.5
    else:
        assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A07")
def test_list_ignores_route_filter(admin, cleanup, route):
    other = make_route(admin, cleanup)
    mine = make_stop(admin, cleanup, route["id"], 1)
    theirs = make_stop(admin, cleanup, other["id"], 1)
    rows = items_of(admin.get(BASE, params={"route_id": route["id"]}))
    ids = [row["id"] for row in rows]
    assert mine["id"] in ids and theirs["id"] in ids
    assert all(row["is_active"] for row in rows)


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A08")
def test_get_stop(admin, cleanup, route):
    stop = make_stop(admin, cleanup, route["id"], 1)
    fetched = admin.get(f"{BASE}{stop['id']}")
    assert fetched.status_code == 200 and fetched.json()["route_name"] == route["route_name"]
    missing = admin.get(f"{BASE}{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["detail"] == "Route stop not found"
    assert admin.get(f"{BASE}not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A09")
def test_put_stop(admin, cleanup, route):
    stop = make_stop(admin, cleanup, route["id"], 1)
    body = stop_body(route["id"], 1, name="renamed", pickup_time="07:30:00", drop_time="09:00:00", fees=900)
    response = admin.put(f"{BASE}{stop['id']}", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "renamed" and data["pickup_time"] == "07:30:00" and data["fees"] == 900.0


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A10")
def test_patch_stop_number_clash(admin, cleanup, route):
    make_stop(admin, cleanup, route["id"], 1)
    second = make_stop(admin, cleanup, route["id"], 2)
    response = admin.patch(f"{BASE}{second['id']}", json={"number": 1})
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A11")
def test_patch_drop_time_persists(admin, cleanup, route):
    stop = make_stop(admin, cleanup, route["id"], 1)
    response = admin.patch(f"{BASE}{stop['id']}", json={"drop_time": "08:45:00"})
    assert response.status_code == 200
    assert admin.get(f"{BASE}{stop['id']}").json()["drop_time"] == "08:45:00"


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A12")
def test_delete_stop(admin, cleanup, route):
    stop = make_stop(admin, cleanup, route["id"], 1)
    response = admin.delete(f"{BASE}{stop['id']}")
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert stop["id"] not in [row["id"] for row in items_of(admin.get(BASE))]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A13")
def test_deleted_stop_number_stays_taken(admin, cleanup, route):
    stop = make_stop(admin, cleanup, route["id"], 1)
    admin.delete(f"{BASE}{stop['id']}")
    assert admin.post(BASE, json=stop_body(route["id"], 1)).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A14")
@pytest.mark.parametrize("role", ROLES)
def test_stop_role_matrix(role_clients, admin, cleanup, route, role):
    stop = make_stop(admin, cleanup, route["id"], 1)
    client = role_clients[role]
    read = 200 if role in READ_ROLES else 403
    assert client.get(BASE).status_code == read
    assert client.get(f"{BASE}{stop['id']}").status_code == read
    if role == "admin":
        return
    assert client.post(BASE, json=stop_body(route["id"], 5)).status_code == 403
    assert client.put(f"{BASE}{stop['id']}", json=stop_body(route["id"], 1)).status_code == 403
    assert client.patch(f"{BASE}{stop['id']}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{BASE}{stop['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A14")
def test_stop_unauthenticated(anon):
    assert anon.get(BASE).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TRN-05-A15")
def test_stop_tenant_isolation(admin, tenant_b, cleanup, route):
    stop = make_stop(admin, cleanup, route["id"], 1)
    assert stop["id"] not in [row["id"] for row in items_of(tenant_b.get(BASE))]
    assert tenant_b.get(f"{BASE}{stop['id']}").status_code == 404
    assert other_tenant_header(admin).get(BASE).status_code == 403
