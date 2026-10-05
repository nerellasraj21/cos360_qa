import pytest

from api_tests.masters.helpers import DENIED, RANDOM_ID, ROLES, make_class, make_mapping, make_year, year_body
from api_tests.support import QA_B_TENANT, items_of, unique

BASE = "/masters/academic_years"


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A01")
def test_create_year_returns_read_shape(admin, cleanup):
    body = year_body(is_active=False)
    response = admin.post(f"{BASE}/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}/{data['id']}/permanent")
    assert data["title"] == body["title"]
    assert data["start_date"] == body["start_date"]
    assert data["end_date"] == body["end_date"]
    assert data["is_active"] is False
    assert data["id"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A02")
@pytest.mark.skip(reason="Creating a year with is_active true (the default) would change the tenant's active year, which the QA rules forbid")
def test_create_year_defaults_to_active():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A03")
@pytest.mark.skip(reason="Creating an active year deactivates the baseline year, which the QA rules forbid")
def test_create_active_year_deactivates_previous():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A04")
def test_duplicate_title_rejected(admin, cleanup):
    year = make_year(admin, cleanup)
    response = admin.post(f"{BASE}/", json=year_body(title=year["title"]))
    assert response.status_code == 400
    assert response.json()["detail"] == "Academic year already exists"


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A05")
def test_title_comparison_is_case_sensitive(admin, cleanup):
    token = unique("")
    upper = make_year(admin, cleanup, title=f"Mst{token}")
    lower = make_year(admin, cleanup, title=f"mst{token}")
    assert upper["id"] != lower["id"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A06")
@pytest.mark.parametrize(
    "mutate,field",
    [
        (lambda b: b.pop("title"), "title"),
        (lambda b: b.update(start_date="not-a-date"), "start_date"),
    ],
)
def test_create_validation_errors(admin, mutate, field):
    body = year_body()
    mutate(body)
    response = admin.post(f"{BASE}/", json=body)
    assert response.status_code == 422
    assert any(field in err["loc"] for err in response.json()["detail"])


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A07")
def test_title_length_boundary(admin, cleanup):
    ok = admin.post(f"{BASE}/", json=year_body(title="y" + unique("")[:8] + "z" * 41))
    assert ok.status_code == 201, ok.text
    assert len(ok.json()["title"]) == 50
    cleanup.delete_later(admin, f"{BASE}/{ok.json()['id']}/permanent")
    too_long = admin.post(f"{BASE}/", json=year_body(title="y" + unique("") + "z" * 42))
    assert too_long.status_code == 400
    assert too_long.json()["detail"].startswith("Academic Year creation failed")


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A08")
def test_end_before_start_rejected(admin):
    response = admin.post(f"{BASE}/", json=year_body(start_date="1500-04-01", end_date="1499-03-31"))
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A09")
def test_default_list_returns_only_active_years(admin, cleanup):
    inactive = make_year(admin, cleanup)
    response = admin.get(f"{BASE}/")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"items", "total_count", "has_next"}
    assert all(item["is_active"] for item in data["items"])
    assert inactive["id"] not in [item["id"] for item in data["items"]]
    assert data["total_count"] >= 1
    assert len(data["items"]) <= 10


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A10")
def test_pagination_with_active_only_false(admin, cleanup):
    for _ in range(3):
        make_year(admin, cleanup)
    first = admin.get(f"{BASE}/?active_only=false&skip=0&limit=2").json()
    total = first["total_count"]
    assert total >= 3
    assert len(first["items"]) == 2
    assert first["has_next"] is True
    last_skip = total - 1
    last = admin.get(f"{BASE}/?active_only=false&skip={last_skip}&limit=2").json()
    assert len(last["items"]) == 1
    assert last["has_next"] is False
    exact = admin.get(f"{BASE}/?active_only=false&skip=0&limit={total}").json()
    assert exact["has_next"] is False


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A11")
def test_dropdown_shape_order_and_active_filter(admin, cleanup):
    inactive = make_year(admin, cleanup)
    default = admin.get(f"{BASE}/dropdown")
    assert default.status_code == 200
    assert inactive["id"] not in [i["id"] for i in default.json()]
    full = admin.get(f"{BASE}/dropdown?active_only=false")
    assert full.status_code == 200
    rows = full.json()
    assert inactive["id"] in [i["id"] for i in rows]
    assert all(set(i) == {"id", "title"} for i in rows)
    titles = [i["title"] for i in rows]
    assert titles == sorted(titles)


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A12")
def test_active_endpoint_lists_only_active(admin, cleanup):
    inactive = make_year(admin, cleanup)
    response = admin.get(f"{BASE}/active")
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    assert rows and all(r["is_active"] is True for r in rows)
    assert inactive["id"] not in [r["id"] for r in rows]


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A13")
def test_get_year_by_id_and_not_found(admin, cleanup):
    year = make_year(admin, cleanup)
    ok = admin.get(f"{BASE}/{year['id']}")
    assert ok.status_code == 200
    assert ok.json() == year
    missing = admin.get(f"{BASE}/{RANDOM_ID}")
    assert missing.status_code == 404
    assert "not found" in missing.json()["detail"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A14")
def test_update_title_keeps_other_fields(admin, cleanup):
    year = make_year(admin, cleanup)
    new_title = unique("msty")
    response = admin.put(f"{BASE}/{year['id']}", json={"title": new_title})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == new_title
    assert data["start_date"] == year["start_date"]
    assert data["end_date"] == year["end_date"]
    assert data["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A15")
@pytest.mark.skip(reason="Activating a year deactivates the baseline year, which the QA rules forbid")
def test_update_activates_year_and_deactivates_others():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A16")
def test_update_to_existing_title_rejected(admin, cleanup):
    a = make_year(admin, cleanup)
    b = make_year(admin, cleanup)
    response = admin.put(f"{BASE}/{b['id']}", json={"title": a["title"]})
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Academic Year update failed")


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A17")
def test_update_unknown_year_is_404(admin):
    response = admin.put(f"{BASE}/{RANDOM_ID}", json={"title": unique("msty")})
    assert response.status_code == 404
    assert response.json()["detail"].startswith("Academic Year with id")


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A18")
def test_deactivate_returns_row_and_hides_from_dropdown(admin, cleanup):
    year = make_year(admin, cleanup)
    response = admin.delete(f"{BASE}/{year['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    full = admin.get(f"{BASE}/?active_only=false&limit=1000").json()["items"]
    assert year["id"] in [i["id"] for i in full]
    assert year["id"] not in [i["id"] for i in admin.get(f"{BASE}/dropdown").json()]


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A19")
def test_deactivate_unknown_year_is_404(admin):
    assert admin.delete(f"{BASE}/{RANDOM_ID}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A20")
def test_permanent_delete_unreferenced_year(admin):
    created = admin.post(f"{BASE}/", json=year_body())
    assert created.status_code == 201
    data = created.json()
    response = admin.delete(f"{BASE}/{data['id']}/permanent")
    assert response.status_code == 200
    assert response.json() == {"message": f"Academic Year {data['title']} deleted successfully"}
    assert admin.get(f"{BASE}/{data['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A21")
def test_permanent_delete_blocked_by_mapping(admin, cleanup, pool):
    year = make_year(admin, cleanup)
    cls = make_class(admin, cleanup, year["id"], sections=("A",))
    make_mapping(admin, cleanup, cls["id"], cls["sections"][0]["id"], pool["subjects"][0]["id"], year["id"])
    response = admin.delete(f"{BASE}/{year['id']}/permanent")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail.startswith("Cannot delete academic year")
    assert "1 class subject mapping(s)" in detail


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A22")
def test_permanent_delete_blocked_by_class_foreign_key(admin, cleanup):
    year = make_year(admin, cleanup)
    make_class(admin, cleanup, year["id"], sections=None)
    response = admin.delete(f"{BASE}/{year['id']}/permanent")
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Academic Year deletion failed")


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A23")
def test_permanent_delete_unknown_year_is_404(admin):
    assert admin.delete(f"{BASE}/{RANDOM_ID}/permanent").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A24")
@pytest.mark.parametrize("role", ROLES)
def test_read_matrix(role_clients, admin, cleanup, role):
    year = make_year(admin, cleanup)
    client = role_clients[role]
    for path in (f"{BASE}/", f"{BASE}/dropdown", f"{BASE}/{year['id']}"):
        response = client.get(path)
        assert response.status_code == 200, (role, path, response.text)


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A24")
@pytest.mark.parametrize("role", ROLES)
def test_read_matrix_active_endpoint(role_clients, role):
    response = role_clients[role].get(f"{BASE}/active")
    assert response.status_code == 200, response.text


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A25")
@pytest.mark.parametrize("role", DENIED)
def test_write_matrix_denied(role_clients, admin, cleanup, role):
    year = make_year(admin, cleanup)
    client = role_clients[role]
    assert client.post(f"{BASE}/", json=year_body()).status_code == 403
    assert client.put(f"{BASE}/{year['id']}", json={"title": unique("msty")}).status_code == 403
    assert client.delete(f"{BASE}/{year['id']}").status_code == 403
    assert client.delete(f"{BASE}/{year['id']}/permanent").status_code == 403
    assert admin.get(f"{BASE}/{year['id']}").json()["title"] == year["title"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A26")
def test_unauthenticated_requests_are_401(anon):
    rid = RANDOM_ID
    assert anon.post(f"{BASE}/", json=year_body()).status_code == 401
    assert anon.get(f"{BASE}/").status_code == 401
    assert anon.get(f"{BASE}/dropdown").status_code == 401
    assert anon.get(f"{BASE}/active").status_code == 401
    assert anon.get(f"{BASE}/{rid}").status_code == 401
    assert anon.put(f"{BASE}/{rid}", json={"title": "x"}).status_code == 401
    assert anon.delete(f"{BASE}/{rid}").status_code == 401
    assert anon.delete(f"{BASE}/{rid}/permanent").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A27")
def test_tenant_isolation(admin, tenant_b, cleanup):
    year = make_year(admin, cleanup)
    listing = tenant_b.get(f"{BASE}/?active_only=false&limit=1000")
    assert listing.status_code == 200
    assert year["id"] not in [i["id"] for i in items_of(listing)]
    assert year["id"] not in [i["id"] for i in tenant_b.get(f"{BASE}/dropdown?active_only=false").json()]
    assert tenant_b.get(f"{BASE}/{year['id']}").status_code == 404
    mismatch = admin.get(f"{BASE}/", headers={"cschema": QA_B_TENANT})
    assert mismatch.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A28")
def test_create_invalidates_dropdown_cache(admin, cleanup):
    before = admin.get(f"{BASE}/dropdown?active_only=false")
    assert before.status_code == 200
    year = make_year(admin, cleanup)
    after = admin.get(f"{BASE}/dropdown?active_only=false")
    assert year["id"] in [i["id"] for i in after.json()]


@pytest.mark.api
@pytest.mark.tc("TC-MST-01-A29")
@pytest.mark.skip(reason="The test API runs with rate limiting disabled, so the 429 cannot be produced")
def test_create_rate_limit():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-MST-02-A01")
def test_login_year_list_is_public(anon):
    response = anon.get("/auth/academic-years")
    assert response.status_code == 200
    rows = response.json()
    assert rows and all("id" in r and "title" in r for r in rows)


@pytest.mark.api
@pytest.mark.tc("TC-MST-02-A02")
@pytest.mark.skip(reason="Activating a year changes the tenant's active year, which the QA rules forbid")
def test_admin_activates_year():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-MST-02-A03")
@pytest.mark.parametrize("role", ["teacher"])
def test_teacher_cannot_activate_year(role_clients, admin, cleanup, role):
    year = make_year(admin, cleanup)
    response = role_clients[role].put(f"{BASE}/{year['id']}", json={"is_active": False})
    assert response.status_code == 403
    assert response.json()["detail"].startswith("Permission not found in database")
    assert admin.get(f"{BASE}/{year['id']}").json()["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-MST-02-A04")
def test_year_list_without_limit_exposes_only_ten(admin, cleanup):
    for _ in range(12):
        make_year(admin, cleanup)
    data = admin.get(f"{BASE}/?active_only=false").json()
    assert len(data["items"]) == 10
    assert data["total_count"] >= 12
    assert data["has_next"] is True


@pytest.mark.api
@pytest.mark.tc("TC-MST-02-A05")
def test_active_endpoint_returns_single_active_year(admin, cleanup):
    make_year(admin, cleanup)
    rows = admin.get(f"{BASE}/active").json()
    assert len(rows) == 1
    assert rows[0]["is_active"] is True
