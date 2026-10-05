import uuid

import pytest

from api_tests.fee import helpers as h
from api_tests.support import items_of, unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api


def rid():
    return str(uuid.uuid4())


def cat_body(year_id, name=None, **extra):
    return {"category_name": name or unique("fee_cat_"), "academic_year_id": year_id, **extra}


def type_body(year_id, category_id, term_id, name=None, **extra):
    return {
        "type_name": name or unique("fee_type_"),
        "fee_category_id": category_id,
        "fee_term_id": term_id,
        "academic_year_id": year_id,
        **extra,
    }


@pytest.fixture
def cat(admin, cleanup, year_id):
    return h.make_category(admin, cleanup, year_id)


@pytest.fixture
def term(admin, cleanup, year_id):
    return h.make_term(admin, cleanup, year_id)


@pytest.mark.tc("TC-FEE-01-A01")
def test_category_create(admin, cleanup, year_id):
    name = unique("fee_cat_")
    r = h.ok(admin.post("/fee/categories/", json=cat_body(year_id, name)), 201)
    data = r.json()
    cleanup.delete_later(admin, f"/fee/categories/{data['id']}")
    assert data["category_name"] == name
    assert data["category_status"] == "active"
    assert data["academic_year_id"] == year_id
    assert data["academic_year_title"]
    assert set(data) >= {"id", "category_name", "category_status", "academic_year_id", "academic_year_title"}


@pytest.mark.tc("TC-FEE-01-A02")
def test_category_duplicate_name(admin, cleanup, year_id, cat):
    r = admin.post("/fee/categories/", json=cat_body(year_id, cat["category_name"]))
    assert r.status_code == 400
    assert f"Category name '{cat['category_name']}' already exists for this academic year" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-01-A03")
def test_category_same_name_second_year(admin, cleanup, year_id, second_year_id, cat):
    r = admin.post("/fee/categories/", json=cat_body(second_year_id, cat["category_name"]))
    h.ok(r, 201)
    cleanup.delete_later(admin, f"/fee/categories/{r.json()['id']}")


@pytest.mark.tc("TC-FEE-01-A04")
def test_category_unknown_year(admin):
    r = admin.post("/fee/categories/", json=cat_body(rid()))
    assert r.status_code == 404
    assert "Academic year with id" in h.detail_text(r) and "not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-01-A05")
def test_category_validation(admin, year_id):
    assert admin.post("/fee/categories/", json={"academic_year_id": year_id}).status_code == 422
    assert admin.post("/fee/categories/", json={"category_name": unique("fee_"), "academic_year_id": "x"}).status_code == 422


@pytest.mark.tc("TC-FEE-01-A06")
def test_category_pagination(admin, cleanup, year_id):
    for _ in range(3):
        h.make_category(admin, cleanup, year_id)
    first = h.ok(admin.get("/fee/categories/", params={"limit": 2, "offset": 0})).json()
    second = h.ok(admin.get("/fee/categories/", params={"limit": 2, "offset": 2})).json()
    assert isinstance(first, list) and 0 < len(first) <= 2
    assert 0 < len(second) <= 2
    assert {c["id"] for c in first}.isdisjoint({c["id"] for c in second})


@pytest.mark.tc("TC-FEE-01-A07")
@pytest.mark.parametrize("limit", [0, 501])
def test_category_limit_bounds(admin, limit):
    assert admin.get("/fee/categories/", params={"limit": limit}).status_code == 422


@pytest.mark.tc("TC-FEE-01-A08")
def test_category_dropdown(admin, cleanup, year_id):
    prefix = unique("fee_ord_")
    created = [h.make_category(admin, cleanup, year_id, name=f"{prefix}_{s}") for s in ("c", "a", "b")]
    r = h.ok(admin.get("/fee/categories/dropdown", params={"academic_year_id": year_id}))
    items = r.json()
    assert all(set(i) == {"id", "category_name"} for i in items)
    mine = [i["category_name"] for i in items if i["category_name"].startswith(prefix)]
    assert mine == [f"{prefix}_a", f"{prefix}_b", f"{prefix}_c"]
    assert {c["id"] for c in created} <= {i["id"] for i in items}


@pytest.mark.tc("TC-FEE-01-A08")
def test_category_dropdown_filters_year(admin, cleanup, year_id, second_year_id):
    other = h.make_category(admin, cleanup, second_year_id)
    items = h.ok(admin.get("/fee/categories/dropdown", params={"academic_year_id": year_id})).json()
    assert other["id"] not in {i["id"] for i in items}


@pytest.mark.tc("TC-FEE-01-A09")
def test_category_dropdown_cache_invalidated(admin, cleanup, year_id):
    h.ok(admin.get("/fee/categories/dropdown", params={"academic_year_id": year_id}))
    new = h.make_category(admin, cleanup, year_id)
    items = h.ok(admin.get("/fee/categories/dropdown", params={"academic_year_id": year_id})).json()
    assert new["id"] in {i["id"] for i in items}


@pytest.mark.tc("TC-FEE-01-A10")
def test_category_get(admin, cat, year_id):
    r = h.ok(admin.get(f"/fee/categories/{cat['id']}"))
    assert r.json()["academic_year_title"] == cat["academic_year_title"]
    assert admin.get("/fee/categories/not-a-uuid").status_code == 422


@pytest.mark.tc("TC-FEE-01-A10")
@pytest.mark.xfail(strict=True, reason="FEE-B01: GET /fee/categories/{unknown id} returns 500 because get_fee_category_by_id swallows its own 404")
def test_category_get_unknown(admin):
    missing = rid()
    r = admin.get(f"/fee/categories/{missing}")
    assert r.status_code == 404
    assert f"Fee category with id {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-01-A11")
def test_category_rename_to_sibling_name(admin, cleanup, year_id, cat):
    other = h.make_category(admin, cleanup, year_id)
    r = admin.put(f"/fee/categories/{other['id']}", json={"category_name": cat["category_name"]})
    assert r.status_code == 400
    assert "already exists for this academic year" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-01-A12")
def test_category_update_self_name_and_status(admin, cat):
    h.ok(admin.put(f"/fee/categories/{cat['id']}", json={"category_name": cat["category_name"]}))
    r = h.ok(admin.put(f"/fee/categories/{cat['id']}", json={"category_status": "inactive"}))
    assert r.json()["category_status"] == "inactive"
    assert admin.get(f"/fee/categories/{cat['id']}").json()["category_status"] == "inactive"


@pytest.mark.tc("TC-FEE-01-A13")
def test_category_move_to_year_with_same_name(admin, cleanup, year_id, second_year_id):
    name = unique("fee_cat_")
    a = h.make_category(admin, cleanup, year_id, name=name)
    h.make_category(admin, cleanup, second_year_id, name=name)
    r = admin.put(f"/fee/categories/{a['id']}", json={"academic_year_id": second_year_id})
    assert r.status_code == 400
    assert "already exists" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-01-A14")
def test_category_delete_unused(admin, year_id):
    c = h.ok(admin.post("/fee/categories/", json=cat_body(year_id)), 201).json()
    r = h.ok(admin.delete(f"/fee/categories/{c['id']}"))
    assert r.json()["id"] == c["id"]
    ids = {i["id"] for i in items_of(admin.get("/fee/categories/", params={"limit": 500}))}
    assert c["id"] not in ids


@pytest.mark.tc("TC-FEE-01-A14")
@pytest.mark.xfail(strict=True, reason="FEE-B01: GET /fee/categories/{deleted id} returns 500 instead of 404")
def test_category_get_after_delete(admin, year_id):
    c = h.ok(admin.post("/fee/categories/", json=cat_body(year_id)), 201).json()
    h.ok(admin.delete(f"/fee/categories/{c['id']}"))
    assert admin.get(f"/fee/categories/{c['id']}").status_code == 404


@pytest.mark.tc("TC-FEE-01-A15")
def test_category_delete_with_type_blocked(admin, cleanup, year_id, cat, term):
    h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    r = admin.delete(f"/fee/categories/{cat['id']}")
    assert r.status_code == 400
    assert f"Cannot delete fee category '{cat['category_name']}' because it is being used by 1 fee type(s)" in h.detail_text(r)
    assert admin.get(f"/fee/categories/{cat['id']}").status_code == 200


@pytest.mark.tc("TC-FEE-01-A16")
def test_category_health(admin):
    r = h.ok(admin.get("/fee/categories/health"))
    assert r.json()["status"] == "healthy" and r.json()["module"] == "fee_categories"


@pytest.mark.tc("TC-FEE-01-A17")
@pytest.mark.parametrize("role", ROLES)
def test_category_write_matrix(role, role_clients, admin, cleanup, year_id, cat):
    client = role_clients[role]
    allowed = role == "admin"
    r = client.post("/fee/categories/", json=cat_body(year_id))
    if allowed:
        h.ok(r, 201)
        cleanup.delete_later(admin, f"/fee/categories/{r.json()['id']}")
    else:
        assert r.status_code == 403
    r = client.put(f"/fee/categories/{cat['id']}", json={"category_status": "active"})
    assert r.status_code == (200 if allowed else 403)
    target = h.make_category(admin, cleanup, year_id)
    r = client.delete(f"/fee/categories/{target['id']}")
    if allowed:
        assert r.status_code == 200
    else:
        assert r.status_code == 403
        assert admin.get(f"/fee/categories/{target['id']}").status_code == 200


@pytest.mark.tc("TC-FEE-01-A18")
@pytest.mark.parametrize("role", ROLES)
def test_category_read_matrix(role, role_clients, cat, year_id):
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get("/fee/categories/").status_code == expected
    assert client.get(f"/fee/categories/{cat['id']}").status_code == expected
    assert client.get("/fee/categories/dropdown", params={"academic_year_id": year_id}).status_code == expected


@pytest.mark.tc("TC-FEE-01-A19")
def test_category_no_token(anon, cat, year_id):
    assert anon.get("/fee/categories/").status_code == 401
    assert anon.get(f"/fee/categories/{cat['id']}").status_code == 401
    assert anon.post("/fee/categories/", json=cat_body(year_id)).status_code == 401
    assert anon.put(f"/fee/categories/{cat['id']}", json={"category_status": "active"}).status_code == 401
    assert anon.delete(f"/fee/categories/{cat['id']}").status_code == 401


@pytest.mark.tc("TC-FEE-01-A20")
def test_category_tenant_isolation(admin, tenant_b, mismatched_admin, cat):
    assert tenant_b.get(f"/fee/categories/{cat['id']}").status_code in (404, 500)
    ids = {c["id"] for c in items_of(tenant_b.get("/fee/categories/", params={"limit": 500}))}
    assert cat["id"] not in ids
    assert mismatched_admin.get(f"/fee/categories/{cat['id']}").status_code == 403


@pytest.mark.tc("TC-FEE-02-A01")
def test_type_create(admin, cleanup, year_id, cat, term):
    body = type_body(year_id, cat["id"], term["id"])
    r = h.ok(admin.post("/fee/types/", json=body), 201)
    data = r.json()
    cleanup.delete_later(admin, f"/fee/types/{data['id']}")
    assert data["fee_status"] == "active"
    assert data["fee_category_name"] == cat["category_name"]
    assert data["fee_term_name"] == term["term_name"]
    assert data["academic_year_name"]
    assert [d["fee_term_date"] for d in data["fee_term_dates"]] == h.Q4_DATES


@pytest.mark.tc("TC-FEE-02-A02")
def test_type_duplicate_name_same_category(admin, cleanup, year_id, cat, term):
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    r = admin.post("/fee/types/", json=type_body(year_id, cat["id"], term["id"], t["type_name"]))
    assert r.status_code == 400
    assert f"Fee type name '{t['type_name']}' already exists for this fee category" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-02-A03")
def test_type_same_name_other_category(admin, cleanup, year_id, cat, term):
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    other = h.make_category(admin, cleanup, year_id)
    r = h.ok(admin.post("/fee/types/", json=type_body(year_id, other["id"], term["id"], t["type_name"])), 201)
    cleanup.delete_later(admin, f"/fee/types/{r.json()['id']}")


@pytest.mark.tc("TC-FEE-02-A04")
def test_type_unknown_references(admin, year_id, cat, term):
    r = admin.post("/fee/types/", json=type_body(year_id, rid(), term["id"]))
    assert r.status_code == 404 and "Fee category with id" in h.detail_text(r)
    r = admin.post("/fee/types/", json=type_body(year_id, cat["id"], rid()))
    assert r.status_code == 404 and "Fee term with id" in h.detail_text(r)
    r = admin.post("/fee/types/", json=type_body(rid(), cat["id"], term["id"]))
    assert r.status_code == 404 and "Academic year with id" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-02-A05")
def test_type_invalid_status(admin, year_id, cat, term):
    r = admin.post("/fee/types/", json=type_body(year_id, cat["id"], term["id"], fee_status="paused"))
    assert r.status_code == 422


@pytest.mark.tc("TC-FEE-02-A06")
def test_type_missing_term(admin, year_id, cat):
    body = type_body(year_id, cat["id"], rid())
    body.pop("fee_term_id")
    assert admin.post("/fee/types/", json=body).status_code == 422


@pytest.mark.tc("TC-FEE-02-A07")
def test_type_list_pagination(admin, cleanup, year_id, cat, term):
    for _ in range(3):
        h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    r = h.ok(admin.get("/fee/types/", params={"limit": 2, "offset": 2}))
    data = r.json()
    assert isinstance(data, list) and 0 < len(data) <= 2
    assert all(i["fee_category_name"] and i["fee_term_name"] for i in data)


@pytest.mark.tc("TC-FEE-02-A08")
def test_type_dropdown(admin, cleanup, year_id, cat, term):
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    items = h.ok(admin.get("/fee/types/dropdown")).json()
    assert all(set(i) == {"id", "type_name"} for i in items)
    assert t["id"] in {i["id"] for i in items}


@pytest.mark.tc("TC-FEE-02-A09")
def test_type_dropdown_filtered_by_category(admin, cleanup, year_id, cat, term):
    other = h.make_category(admin, cleanup, year_id)
    mine = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    foreign = h.make_type(admin, cleanup, year_id, other["id"], term["id"])
    r = h.ok(admin.get("/fee/types/dropdown", params={"fee_category_id": cat["id"]}))
    ids = {i["id"] for i in r.json()}
    assert mine["id"] in ids and foreign["id"] not in ids


@pytest.mark.tc("TC-FEE-02-A10")
def test_type_get(admin, cleanup, year_id, cat, term):
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    assert h.ok(admin.get(f"/fee/types/{t['id']}")).json()["id"] == t["id"]


@pytest.mark.tc("TC-FEE-02-A10")
@pytest.mark.xfail(strict=True, reason="FEE-B02: GET /fee/types/{unknown id} returns 500 because get_fee_type_by_id swallows its own 404")
def test_type_get_unknown(admin):
    assert admin.get(f"/fee/types/{rid()}").status_code == 404


@pytest.mark.tc("TC-FEE-02-A11")
def test_type_change_term(admin, cleanup, year_id, cat, term):
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    t3 = h.make_term(admin, cleanup, year_id, h.T3_DATES)
    r = h.ok(admin.put(f"/fee/types/{t['id']}", json={"fee_term_id": t3["id"]}))
    assert r.json()["fee_term_id"] == t3["id"]
    got = admin.get(f"/fee/types/{t['id']}").json()
    assert got["fee_term_name"] == t3["term_name"]
    assert len(got["fee_term_dates"]) == 3


@pytest.mark.tc("TC-FEE-02-A11")
@pytest.mark.xfail(strict=True, reason="FEE-B03: PUT /fee/types/{id} response carries the old term name and dates after fee_term_id changes (a following GET is correct)")
def test_type_change_term_response_is_fresh(admin, cleanup, year_id, cat, term):
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    t3 = h.make_term(admin, cleanup, year_id, h.T3_DATES)
    r = h.ok(admin.put(f"/fee/types/{t['id']}", json={"fee_term_id": t3["id"]}))
    assert r.json()["fee_term_name"] == t3["term_name"]
    assert len(r.json()["fee_term_dates"]) == 3


@pytest.mark.tc("TC-FEE-02-A12")
def test_type_rename_to_sibling(admin, cleanup, year_id, cat, term):
    a = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    b = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    r = admin.put(f"/fee/types/{b['id']}", json={"type_name": a["type_name"]})
    assert r.status_code == 400
    assert "already exists for this fee category" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-02-A13")
def test_type_delete_unused(admin, cleanup, year_id, cat, term):
    t = h.ok(admin.post("/fee/types/", json=type_body(year_id, cat["id"], term["id"])), 201).json()
    h.ok(admin.delete(f"/fee/types/{t['id']}"))
    ids = {i["id"] for i in items_of(admin.get("/fee/types/dropdown"))}
    assert t["id"] not in ids


@pytest.mark.tc("TC-FEE-02-A13")
@pytest.mark.xfail(strict=True, reason="FEE-B02: GET /fee/types/{deleted id} returns 500 instead of 404")
def test_type_get_after_delete(admin, year_id, cat, term):
    t = h.ok(admin.post("/fee/types/", json=type_body(year_id, cat["id"], term["id"])), 201).json()
    h.ok(admin.delete(f"/fee/types/{t['id']}"))
    assert admin.get(f"/fee/types/{t['id']}").status_code == 404


@pytest.mark.tc("TC-FEE-02-A14")
def test_type_delete_with_mappings_blocked(admin, cleanup, year_id, fee_world, new_student):
    cat = h.make_category(admin, cleanup, year_id)
    t = h.make_type(admin, cleanup, year_id, cat["id"], fee_world["q4"]["id"])
    cls = h.make_class(admin, cleanup, year_id)
    h.make_class_mapping(admin, cleanup, year_id, cls["id"], t["id"])
    student = h.make_student(admin, cleanup, year_id, cls)
    h.map_student(admin, cleanup, year_id, student, t["id"])
    r = admin.delete(f"/fee/types/{t['id']}")
    assert r.status_code == 400
    text = h.detail_text(r)
    assert f"Cannot delete fee type '{t['type_name']}' because it is being used by 2 record(s)" in text
    assert "1 fee class mapping(s), 1 fee student mapping(s)" in text
    assert admin.get(f"/fee/types/{t['id']}").status_code == 200


@pytest.mark.tc("TC-FEE-02-A15")
def test_type_health(admin):
    r = h.ok(admin.get("/fee/types/health"))
    assert r.json()["module"] == "fee_types"


@pytest.mark.tc("TC-FEE-02-A16")
@pytest.mark.parametrize("role", ROLES)
def test_type_write_matrix(role, role_clients, admin, cleanup, year_id, cat, term):
    client = role_clients[role]
    allowed = role == "admin"
    r = client.post("/fee/types/", json=type_body(year_id, cat["id"], term["id"]))
    if allowed:
        h.ok(r, 201)
        cleanup.delete_later(admin, f"/fee/types/{r.json()['id']}")
    else:
        assert r.status_code == 403
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    r = client.put(f"/fee/types/{t['id']}", json={"fee_status": "inactive"})
    assert r.status_code == (200 if allowed else 403)
    r = client.delete(f"/fee/types/{t['id']}")
    assert r.status_code == (200 if allowed else 403)
    if not allowed:
        assert admin.get(f"/fee/types/{t['id']}").status_code == 200


@pytest.mark.tc("TC-FEE-02-A17")
@pytest.mark.parametrize("role", ROLES)
def test_type_read_matrix(role, role_clients, admin, cleanup, year_id, cat, term):
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get("/fee/types/").status_code == expected
    assert client.get(f"/fee/types/{t['id']}").status_code == expected
    assert client.get("/fee/types/dropdown").status_code == expected


@pytest.mark.tc("TC-FEE-02-A18")
def test_type_no_token_and_header_mismatch(anon, mismatched_admin, admin, cleanup, year_id, cat, term):
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    assert anon.get("/fee/types/").status_code == 401
    assert anon.get(f"/fee/types/{t['id']}").status_code == 401
    assert anon.post("/fee/types/", json=type_body(year_id, cat["id"], term["id"])).status_code == 401
    assert mismatched_admin.get("/fee/types/").status_code == 403


@pytest.mark.tc("TC-FEE-02-A19")
def test_type_tenant_isolation(admin, cleanup, tenant_b, year_id, cat, term):
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    assert tenant_b.get(f"/fee/types/{t['id']}").status_code in (404, 500)
    ids = {i["id"] for i in items_of(tenant_b.get("/fee/types/", params={"limit": 500}))}
    assert t["id"] not in ids


@pytest.mark.tc("TC-FEE-01-A20")
@pytest.mark.xfail(strict=True, reason="FEE-B01: cross-tenant GET /fee/categories/{id} returns 500 instead of 404")
def test_category_tenant_isolation_get_is_404(tenant_b, cat):
    assert tenant_b.get(f"/fee/categories/{cat['id']}").status_code == 404


@pytest.mark.tc("TC-FEE-02-A19")
@pytest.mark.xfail(strict=True, reason="FEE-B02: cross-tenant GET /fee/types/{id} returns 500 instead of 404")
def test_type_tenant_isolation_get_is_404(admin, cleanup, tenant_b, year_id, cat, term):
    t = h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    assert tenant_b.get(f"/fee/types/{t['id']}").status_code == 404
