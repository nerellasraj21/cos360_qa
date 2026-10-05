import uuid

import pytest

from api_tests.staff.helpers import ALL_ROLES, expected_status, granted
from api_tests.support import unique

BASE = "/staff/designations"


def pad_title(prefix: str, length: int) -> str:
    return (prefix + "x" * length)[:length]


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A01")
def test_create_designation(admin, cleanup):
    title = unique("stf_des_")
    response = admin.post(f"{BASE}/", json={"title": title})
    assert response.status_code == 201
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}/{data['id']}")
    assert data["title"] == title
    assert data["staff_count"] == 0
    assert uuid.UUID(data["id"])
    assert data["created_at"] and data["updated_at"]
    assert set(data) == {"id", "title", "created_at", "updated_at", "staff_count"}


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A02")
def test_duplicate_title_rejected(admin, make_designation):
    designation = make_designation()
    response = admin.post(f"{BASE}/", json={"title": designation["title"]})
    assert response.status_code == 400
    assert response.json()["detail"] == f"Designation title '{designation['title']}' already exists"
    titles = [item["title"] for item in admin.get("/staff/designations-legacy").json()]
    assert titles.count(designation["title"]) == 1


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A03")
def test_create_requires_title(admin):
    response = admin.post(f"{BASE}/", json={})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "title"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A04")
def test_create_100_character_title(admin, cleanup):
    title = pad_title(unique("stf_len_"), 100)
    response = admin.post(f"{BASE}/", json={"title": title})
    assert response.status_code == 201
    cleanup.delete_later(admin, f"{BASE}/{response.json()['id']}")
    assert len(response.json()["title"]) == 100


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A05")
def test_create_101_character_title_fails(admin):
    title = pad_title(unique("stf_len_"), 101)
    response = admin.post(f"{BASE}/", json={"title": title})
    assert response.status_code == 500
    assert "Error creating designation" in response.json()["detail"]
    assert title not in [item["title"] for item in admin.get("/staff/designations-legacy").json()]


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A06")
def test_create_empty_title_is_accepted(admin, cleanup):
    response = admin.post(f"{BASE}/", json={"title": ""})
    assert response.status_code == 201
    cleanup.delete_later(admin, f"{BASE}/{response.json()['id']}")
    assert response.json()["title"] == ""


def fetch_all(admin):
    response = admin.get(f"{BASE}/", params={"skip": 0, "limit": 100})
    assert response.status_code == 200
    return response.json()


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A07")
def test_list_pagination_first_page(admin, make_designation):
    prefix = unique("stf_pg_")
    mine = [make_designation(f"{prefix}{i:02d}")["title"] for i in range(12)]
    page = admin.get(f"{BASE}/", params={"skip": 0, "limit": 10})
    assert page.status_code == 200
    body = page.json()
    assert set(body) == {"items", "total_count", "has_next"}
    assert len(body["items"]) == 10
    assert body["total_count"] >= 12
    assert body["has_next"] is True
    for item in body["items"]:
        assert set(item) == {"id", "title", "created_at", "updated_at", "staff_count"}
    everything = fetch_all(admin)["items"]
    ordered = [item["title"] for item in everything if item["title"].startswith(prefix)]
    assert ordered == sorted(mine)


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A08")
def test_list_pagination_second_page(admin, make_designation):
    for i in range(12):
        make_designation(unique("stf_pg_"))
    second = admin.get(f"{BASE}/", params={"skip": 10, "limit": 10}).json()
    assert 1 <= len(second["items"]) <= 10
    assert second["has_next"] == (20 < second["total_count"])
    last = admin.get(f"{BASE}/", params={"skip": 0, "limit": 100}).json()
    skip = max(last["total_count"] - 2, 0)
    tail = admin.get(f"{BASE}/", params={"skip": skip, "limit": 10}).json()
    assert tail["has_next"] is False
    assert len(tail["items"]) >= 1


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A09")
def test_list_limit_boundaries(admin):
    assert admin.get(f"{BASE}/", params={"limit": 100}).status_code == 200
    assert admin.get(f"{BASE}/", params={"limit": 101}).status_code == 422
    assert admin.get(f"{BASE}/", params={"limit": 0}).status_code == 422
    assert admin.get(f"{BASE}/", params={"skip": -1}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A10")
def test_staff_count_accuracy(admin, make_designation, make_staff):
    two = make_designation()
    one = make_designation()
    zero = make_designation()
    make_staff(designation_id=two["id"])
    make_staff(designation_id=two["id"])
    make_staff(designation_id=one["id"])
    counts = {item["id"]: item["staff_count"] for item in fetch_all(admin)["items"]}
    assert counts[two["id"]] == 2
    assert counts[one["id"]] == 1
    assert counts[zero["id"]] == 0
    assert admin.get(f"{BASE}/{two['id']}").json()["staff_count"] == 2
    assert admin.get(f"{BASE}/{one['id']}").json()["staff_count"] == 1
    assert admin.get(f"{BASE}/{zero['id']}").json()["staff_count"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A11")
def test_get_designation(admin, make_designation):
    designation = make_designation()
    response = admin.get(f"{BASE}/{designation['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == designation["id"]
    assert response.json()["title"] == designation["title"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A12")
def test_get_unknown_and_malformed_id(admin):
    missing = str(uuid.uuid4())
    response = admin.get(f"{BASE}/{missing}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Designation with id {missing} not found"
    assert admin.get(f"{BASE}/abc").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A13")
def test_rename_keeps_staff_count(admin, make_designation, make_staff):
    designation = make_designation()
    make_staff(designation_id=designation["id"])
    new_title = unique("stf_ren_")
    response = admin.put(f"{BASE}/{designation['id']}", json={"title": new_title})
    assert response.status_code == 200
    assert response.json()["title"] == new_title
    assert response.json()["staff_count"] == 1


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A14")
def test_rename_to_existing_title_conflicts(admin, make_designation):
    first = make_designation()
    second = make_designation()
    response = admin.put(f"{BASE}/{second['id']}", json={"title": first["title"]})
    assert response.status_code == 400
    assert response.json()["detail"] == f"Designation title '{first['title']}' already exists"
    assert admin.get(f"{BASE}/{second['id']}").json()["title"] == second["title"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A15")
def test_update_unchanged_and_empty_body(admin, make_designation):
    designation = make_designation()
    same = admin.put(f"{BASE}/{designation['id']}", json={"title": designation["title"]})
    empty = admin.put(f"{BASE}/{designation['id']}", json={})
    assert same.status_code == 200 and empty.status_code == 200
    assert empty.json()["title"] == designation["title"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A16")
def test_update_and_delete_unknown_id(admin):
    missing = str(uuid.uuid4())
    assert admin.put(f"{BASE}/{missing}", json={"title": unique("stf_x_")}).status_code == 404
    assert admin.delete(f"{BASE}/{missing}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A17")
def test_delete_unused_designation(admin):
    created = admin.post(f"{BASE}/", json={"title": unique("stf_del_")}).json()
    response = admin.delete(f"{BASE}/{created['id']}")
    assert response.status_code == 200
    assert response.json() == {"message": "Designation deleted successfully"}
    assert admin.get(f"{BASE}/{created['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A18")
def test_delete_designation_in_use(admin, make_designation, make_staff):
    designation = make_designation()
    make_staff(designation_id=designation["id"])
    make_staff(designation_id=designation["id"])
    response = admin.delete(f"{BASE}/{designation['id']}")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail.startswith(f"Cannot delete designation '{designation['title']}' because it is being used by 2 staff member(s).")
    assert admin.get(f"{BASE}/{designation['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A19")
def test_dropdown_shape_and_order(admin, make_designation):
    prefix = unique("stf_dd_")
    titles = [make_designation(f"{prefix}{i}")["title"] for i in (3, 1, 2)]
    response = admin.get(f"{BASE}/dropdown")
    assert response.status_code == 200
    items = response.json()
    assert all(set(item) == {"id", "title"} for item in items)
    mine = [item["title"] for item in items if item["title"].startswith(prefix)]
    assert mine == sorted(titles)


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A20")
def test_dropdown_cache_cleared_on_create(admin, make_designation):
    admin.get(f"{BASE}/dropdown")
    created = make_designation()
    titles = [item["title"] for item in admin.get(f"{BASE}/dropdown").json()]
    assert created["title"] in titles


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A21")
def test_legacy_list(admin, make_designation):
    created = make_designation()
    response = admin.get("/staff/designations-legacy")
    assert response.status_code == 200
    assert {"id": created["id"], "title": created["title"]} in response.json()


UNKNOWN = "9f8e7d6c-5b4a-4c3d-8e2f-1a0b9c8d7e6f"
ENDPOINTS = [
    ("POST", f"{BASE}/", {"title": "stf_anon"}),
    ("GET", f"{BASE}/", None),
    ("GET", f"{BASE}/dropdown", None),
    ("GET", f"{BASE}/{UNKNOWN}", None),
    ("PUT", f"{BASE}/{UNKNOWN}", {"title": "stf_anon"}),
    ("DELETE", f"{BASE}/{UNKNOWN}", None),
    ("GET", "/staff/designations-legacy", None),
]


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A22")
@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_designation_endpoints_require_token(anon, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    assert anon.request(method, path, **kwargs).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A23")
def test_admin_full_cycle(admin, cleanup):
    title = unique("stf_cyc_")
    created = admin.post(f"{BASE}/", json={"title": title})
    assert created.status_code == 201
    did = created.json()["id"]
    cleanup.delete_later(admin, f"{BASE}/{did}")
    assert admin.get(f"{BASE}/{did}").status_code == 200
    assert admin.put(f"{BASE}/{did}", json={"title": title + "r"}).status_code == 200
    assert admin.get(f"{BASE}/").status_code == 200
    assert admin.get(f"{BASE}/dropdown").status_code == 200
    assert admin.get("/staff/designations-legacy").status_code == 200
    assert admin.delete(f"{BASE}/{did}").status_code == 200


def run_matrix(client, logins, role, designation_id):
    reads = [
        ("list", "GET", f"{BASE}/", None),
        ("read", "GET", f"{BASE}/{designation_id}", None),
        ("list", "GET", f"{BASE}/dropdown", None),
        ("list", "GET", "/staff/designations-legacy", None),
    ]
    for action, method, path, body in reads:
        response = client.request(method, path)
        assert response.status_code == expected_status(logins, role, "designations", action), (method, path)
    writes = [
        ("create", "POST", f"{BASE}/", {"title": unique("stf_mx_")}),
        ("update", "PUT", f"{BASE}/{designation_id}", {"title": unique("stf_mx_")}),
        ("delete", "DELETE", f"{BASE}/{designation_id}", None),
    ]
    for action, method, path, body in writes:
        if granted(logins, role, "designations", action):
            continue
        kwargs = {"json": body} if body is not None else {}
        assert client.request(method, path, **kwargs).status_code == 403, (method, path)


@pytest.mark.api
@pytest.mark.parametrize(
    "role",
    [
        pytest.param("staff", marks=pytest.mark.tc("TC-STF-01-A24")),
        pytest.param("teacher", marks=pytest.mark.tc("TC-STF-01-A25")),
        pytest.param("student", marks=pytest.mark.tc("TC-STF-01-A26")),
        pytest.param("parent", marks=pytest.mark.tc("TC-STF-01-A27")),
    ],
)
def test_designation_role_matrix(role_clients, logins, make_designation, role):
    designation = make_designation()
    run_matrix(role_clients[role], logins, role, designation["id"])
    assert role_clients["admin"].get(f"{BASE}/{designation['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STF-00-A01")
def test_role_grants_match_documented_defaults(logins):
    assert all(granted(logins, "admin", "designations", a) for a in ("create", "read", "update", "delete", "list"))
    for role in ("staff", "teacher"):
        assert granted(logins, role, "designations", "list") and granted(logins, role, "designations", "read")
        assert not any(granted(logins, role, "designations", a) for a in ("create", "update", "delete"))
    for role in ("student", "parent"):
        assert not any(granted(logins, role, "designations", a) for a in ("create", "read", "update", "delete", "list"))
    assert ALL_ROLES


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A28")
def test_designation_tenant_isolation(admin, tenant_b, make_designation, cleanup):
    created = make_designation()
    assert created["title"] not in [i["title"] for i in tenant_b.get(f"{BASE}/", params={"limit": 100}).json()["items"]]
    assert created["title"] not in [i["title"] for i in tenant_b.get(f"{BASE}/dropdown").json()]
    assert tenant_b.get(f"{BASE}/{created['id']}").status_code == 404
    assert tenant_b.put(f"{BASE}/{created['id']}", json={"title": "x"}).status_code == 404
    assert tenant_b.delete(f"{BASE}/{created['id']}").status_code == 404
    clone = tenant_b.post(f"{BASE}/", json={"title": created["title"]})
    assert clone.status_code == 201
    cleanup.delete_later(tenant_b, f"{BASE}/{clone.json()['id']}")
    assert admin.get(f"{BASE}/{created['id']}").json()["title"] == created["title"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A29")
def test_designation_foreign_tenant_header(b_header_client):
    assert b_header_client.get(f"{BASE}/").status_code == 403
    assert b_header_client.get(f"{BASE}/dropdown").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A30")
@pytest.mark.skip(reason="needs the rate limiter enabled; the test API runs with rate limiting disabled")
def test_designation_create_rate_limit():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-STF-01-A31")
def test_title_uniqueness_is_case_sensitive(admin, cleanup):
    base = unique("stf_Case_")
    first = admin.post(f"{BASE}/", json={"title": base})
    second = admin.post(f"{BASE}/", json={"title": base.lower()})
    for response in (first, second):
        assert response.status_code == 201
        cleanup.delete_later(admin, f"{BASE}/{response.json()['id']}")
