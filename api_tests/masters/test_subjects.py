import pytest

from api_tests.masters.helpers import (
    DENIED,
    RANDOM_ID,
    ROLES,
    make_category,
    make_subject,
)
from api_tests.support import QA_B_TENANT, unique

CAT = "/masters/subject_categories/categories"
ALIAS = "/subject-categories"
SUB = "/masters/subjects"
ADMIN_AND_READERS = ["admin", "staff", "teacher"]
NO_GRANT = ["student", "parent"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A01")
def test_create_category(admin, cleanup):
    name = unique("mstcat")
    response = admin.post(CAT, json={"name": name})
    assert response.status_code == 200, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{CAT}/{data['id']}")
    assert set(data) == {"id", "name"}
    assert data["name"] == name


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A02")
def test_create_category_via_alias(admin, cleanup):
    name = unique("mstcat")
    response = admin.post(ALIAS, json={"name": name})
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{CAT}/{data['id']}")
    assert data["name"] == name and set(data) == {"id", "name"}


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A03")
def test_duplicate_category_name(admin, cleanup):
    cat = make_category(admin, cleanup)
    response = admin.post(CAT, json={"name": cat["name"]})
    assert response.status_code == 400
    assert response.json()["detail"] == "Category already exists"


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A04")
def test_category_name_case_sensitive(admin, cleanup):
    token = unique("")
    make_category(admin, cleanup, name=f"Mst{token}")
    make_category(admin, cleanup, name=f"mst{token}")


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A05")
def test_category_name_length_boundary(admin, cleanup):
    ok = admin.post(CAT, json={"name": unique("c") + "x" * 91})
    assert ok.status_code == 200, ok.text
    assert len(ok.json()["name"]) == 100
    cleanup.delete_later(admin, f"{CAT}/{ok.json()['id']}")
    too_long = admin.post(CAT, json={"name": unique("c") + "x" * 92})
    assert too_long.status_code in (400, 422)


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A06")
@pytest.mark.parametrize("body", [{}, {"name": 123}])
def test_category_invalid_body(admin, body):
    assert admin.post(CAT, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A07")
@pytest.mark.parametrize("name", ["", "   "])
def test_category_blank_name_rejected(admin, name):
    assert admin.post(CAT, json={"name": name}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A08")
def test_category_pagination_and_order(admin, cleanup):
    prefix = unique("mstcatp")
    names = [f"{prefix}_{c}" for c in ("a", "b", "c")]
    for name in reversed(names):
        make_category(admin, cleanup, name=name)
    full = admin.get(f"{CAT}?limit=1000").json()
    assert set(full) == {"items", "total_count", "has_next"}
    mine = [i["name"] for i in full["items"] if i["name"].startswith(prefix)]
    assert mine == names
    total = full["total_count"]
    assert total >= 3
    first = admin.get(f"{CAT}?skip=0&limit=1").json()
    assert len(first["items"]) == 1 and first["has_next"] is True
    total = admin.get(f"{CAT}?skip=0&limit=1").json()["total_count"]
    last = admin.get(f"{CAT}?skip={total - 2}&limit=1").json()
    assert len(last["items"]) == 1
    assert last["has_next"] is ((total - 2 + 1) < last["total_count"])


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A09")
@pytest.mark.parametrize("query", ["limit=0", "limit=1001", "skip=-1"])
def test_category_list_bounds(admin, query):
    assert admin.get(f"{CAT}?{query}").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A10")
def test_category_alias_list(admin, cleanup):
    cat = make_category(admin, cleanup)
    response = admin.get(f"{ALIAS}?limit=1000")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"items", "total_count", "has_next"}
    assert cat["id"] in [i["id"] for i in data["items"]]
    assert len(admin.get(f"{ALIAS}?limit=2").json()["items"]) <= 2


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A11")
def test_category_dropdown(admin, cleanup):
    prefix = unique("mstcatd")
    names = [f"{prefix}_{c}" for c in ("a", "b", "c")]
    created = [make_category(admin, cleanup, name=name) for name in reversed(names)]
    response = admin.get(f"{CAT}/dropdown")
    assert response.status_code == 200
    rows = response.json()
    assert {c["id"] for c in created} <= {r["id"] for r in rows}
    assert all(set(r) == {"id", "name"} for r in rows)
    assert [r["name"] for r in rows if r["name"].startswith(prefix)] == names


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A12")
def test_get_category(admin, cleanup):
    cat = make_category(admin, cleanup)
    ok = admin.get(f"{CAT}/{cat['id']}")
    assert ok.status_code == 200 and ok.json() == cat
    missing = admin.get(f"{CAT}/{RANDOM_ID}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == f"Subject category with id {RANDOM_ID} not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A13")
def test_update_category(admin, cleanup):
    cat = make_category(admin, cleanup)
    new = unique("mstcat")
    response = admin.put(f"{CAT}/{cat['id']}", json={"name": new})
    assert response.status_code == 200
    assert response.json() == {"id": cat["id"], "name": new}


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A14")
def test_update_category_conflicts(admin, cleanup):
    a = make_category(admin, cleanup)
    b = make_category(admin, cleanup)
    same = admin.put(f"{CAT}/{b['id']}", json={"name": b["name"]})
    assert same.status_code == 200
    clash = admin.put(f"{CAT}/{b['id']}", json={"name": a["name"]})
    assert clash.status_code == 400
    assert clash.json()["detail"] == f"Subject category name '{a['name']}' already exists"


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A15")
def test_update_unknown_category(admin):
    assert admin.put(f"{CAT}/{RANDOM_ID}", json={"name": unique("mstcat")}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A16")
def test_delete_unused_category(admin):
    cat = admin.post(CAT, json={"name": unique("mstcat")}).json()
    response = admin.delete(f"{CAT}/{cat['id']}")
    assert response.status_code == 200
    assert response.json() == {"message": "Subject category deleted successfully"}
    assert admin.get(f"{CAT}/{cat['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A17")
def test_delete_category_used_by_subject(admin, cleanup, pool):
    cat = pool["category"]
    make_subject(admin, cleanup, pool["year"]["id"], cat["id"])
    response = admin.delete(f"{CAT}/{cat['id']}")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail.startswith(f"Cannot delete category '{cat['name']}' because it is being used by ")
    assert "subject(s)" in detail
    assert admin.get(f"{CAT}/{cat['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A18")
def test_delete_unknown_category(admin):
    assert admin.delete(f"{CAT}/{RANDOM_ID}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A19")
def test_subjects_categories_plain_list(admin, cleanup):
    cat = make_category(admin, cleanup)
    response = admin.get(f"{SUB}/categories")
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    assert cat in rows


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A20")
@pytest.mark.parametrize("role", ADMIN_AND_READERS)
def test_category_read_matrix_granted(role_clients, admin, cleanup, role):
    cat = make_category(admin, cleanup)
    client = role_clients[role]
    for path in (CAT, f"{CAT}/dropdown", f"{CAT}/{cat['id']}"):
        assert client.get(path).status_code == 200, (role, path)


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A21")
@pytest.mark.parametrize("role", NO_GRANT)
def test_category_read_denied(role_clients, admin, cleanup, role):
    cat = make_category(admin, cleanup)
    client = role_clients[role]
    for path in (CAT, f"{CAT}/dropdown", f"{CAT}/{cat['id']}"):
        assert client.get(path).status_code == 403, (role, path)


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A22")
@pytest.mark.parametrize("role", ["staff", "teacher"])
def test_category_write_denied(role_clients, admin, cleanup, role):
    cat = make_category(admin, cleanup)
    client = role_clients[role]
    assert client.post(CAT, json={"name": unique("mstcat")}).status_code == 403
    assert client.put(f"{CAT}/{cat['id']}", json={"name": unique("mstcat")}).status_code == 403
    assert client.delete(f"{CAT}/{cat['id']}").status_code == 403
    assert admin.get(f"{CAT}/{cat['id']}").json() == cat


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A22")
@pytest.mark.parametrize("role", NO_GRANT)
def test_category_write_denied_without_grant(role_clients, role):
    client = role_clients[role]
    assert client.post(CAT, json={"name": unique("mstcat")}).status_code == 403
    assert client.post(ALIAS, json={"name": unique("mstcat")}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A23")
def test_category_endpoints_need_authentication(anon):
    assert anon.post(CAT, json={"name": "x"}).status_code == 401
    assert anon.post(ALIAS, json={"name": "x"}).status_code == 401
    assert anon.get(ALIAS).status_code == 401
    assert anon.get(CAT).status_code == 401
    assert anon.get(f"{CAT}/dropdown").status_code == 401
    assert anon.get(f"{CAT}/{RANDOM_ID}").status_code == 401
    assert anon.put(f"{CAT}/{RANDOM_ID}", json={"name": "x"}).status_code == 401
    assert anon.delete(f"{CAT}/{RANDOM_ID}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A24")
def test_category_tenant_isolation(admin, tenant_b, cleanup):
    cat = make_category(admin, cleanup)
    assert cat["id"] not in [i["id"] for i in tenant_b.get(f"{CAT}?limit=1000").json()["items"]]
    assert cat["id"] not in [i["id"] for i in tenant_b.get(f"{CAT}/dropdown").json()]
    assert tenant_b.get(f"{CAT}/{cat['id']}").status_code == 404
    twin = tenant_b.post(CAT, json={"name": cat["name"]})
    assert twin.status_code == 200
    cleanup.delete_later(tenant_b, f"{CAT}/{twin.json()['id']}")
    assert admin.get(CAT, headers={"cschema": QA_B_TENANT}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-MST-07-A25")
@pytest.mark.skip(reason="The test API runs with rate limiting disabled, so the 429 cannot be produced")
def test_category_rate_limit():
    pass


def subject_body(pool, **over):
    body = {
        "name": unique("mstsub"),
        "short_code": unique("s")[:10],
        "category_id": pool["category"]["id"],
        "academic_year_id": pool["year"]["id"],
    }
    body.update(over)
    return body


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A01")
def test_create_subject(admin, cleanup, pool):
    body = subject_body(pool)
    response = admin.post(f"{SUB}/", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{SUB}/{data['id']}")
    assert data["category"] == pool["category"]
    assert data["is_active"] is True
    assert data["name"] == body["name"] and data["short_code"] == body["short_code"]
    assert data["academic_year_id"] == pool["year"]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A02")
def test_duplicate_subject_name_in_year(admin, cleanup, pool):
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    response = admin.post(f"{SUB}/", json=subject_body(pool, name=sub["name"]))
    assert response.status_code == 422
    assert "BUSINESS_RULE_ERROR" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A03")
def test_duplicate_subject_code_in_year(admin, cleanup, pool):
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    response = admin.post(f"{SUB}/", json=subject_body(pool, short_code=sub["short_code"]))
    assert response.status_code == 422
    assert "BUSINESS_RULE_ERROR" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A04")
def test_same_subject_name_in_another_year(admin, cleanup, pool):
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    other = make_subject(
        admin, cleanup, pool["year2"]["id"], pool["category"]["id"], name=sub["name"], short_code=sub["short_code"]
    )
    assert other["id"] != sub["id"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A05")
def test_blank_subject_name(admin, pool):
    response = admin.post(f"{SUB}/", json=subject_body(pool, name="   "))
    assert response.status_code in (400, 422)
    assert "VALIDATION_ERROR" in response.text or response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A06")
def test_subject_name_length_boundary(admin, cleanup, pool):
    ok = admin.post(f"{SUB}/", json=subject_body(pool, name="n" + unique("")[:8] + "x" * 41))
    assert ok.status_code == 200, ok.text
    cleanup.delete_later(admin, f"{SUB}/{ok.json()['id']}")
    assert len(ok.json()["name"]) == 50
    assert admin.post(f"{SUB}/", json=subject_body(pool, name="n" * 51)).status_code == 422
    assert admin.post(f"{SUB}/", json=subject_body(pool, name="n" * 101)).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A07")
def test_subject_code_length_boundary(admin, cleanup, pool):
    ok = admin.post(f"{SUB}/", json=subject_body(pool, short_code=unique("c")[:10]))
    assert ok.status_code == 200, ok.text
    cleanup.delete_later(admin, f"{SUB}/{ok.json()['id']}")
    assert admin.post(f"{SUB}/", json=subject_body(pool, short_code="c" * 11)).status_code == 422
    assert admin.post(f"{SUB}/", json=subject_body(pool, short_code="c" * 21)).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A08")
def test_subject_missing_or_unknown_references(admin, pool):
    body = subject_body(pool)
    body.pop("category_id")
    assert admin.post(f"{SUB}/", json=body).status_code == 422
    bad_cat = admin.post(f"{SUB}/", json=subject_body(pool, category_id=RANDOM_ID))
    assert bad_cat.status_code == 500
    assert "DATABASE_ERROR" in bad_cat.text
    bad_year = admin.post(f"{SUB}/", json=subject_body(pool, academic_year_id=RANDOM_ID))
    assert bad_year.status_code == 500
    assert "DATABASE_ERROR" in bad_year.text


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A09")
def test_subject_list_default_is_plain_array_of_active(admin, cleanup, pool):
    active = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    gone = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    assert admin.delete(f"{SUB}/{gone['id']}").status_code == 204
    response = admin.get(f"{SUB}/?academic_year_id={pool['year']['id']}")
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    ids = [r["id"] for r in rows]
    assert active["id"] in ids and gone["id"] not in ids
    assert all(r["is_active"] for r in rows)


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A10")
def test_subject_list_inactive_and_year_filter(admin, cleanup, pool):
    a = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    b = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"], is_active=False)
    other = make_subject(admin, cleanup, pool["year2"]["id"], pool["category"]["id"])
    rows = admin.get(f"{SUB}/?active_only=false&academic_year_id={pool['year']['id']}").json()
    ids = [r["id"] for r in rows]
    assert a["id"] in ids and b["id"] in ids and other["id"] not in ids
    assert all(r["academic_year_id"] == pool["year"]["id"] for r in rows)


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A11")
def test_subject_paginated(admin, cleanup, pool):
    make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    first = admin.get(f"{SUB}/paginated?skip=0&limit=1&academic_year_id={pool['year']['id']}")
    assert first.status_code == 200
    data = first.json()
    assert set(data) == {"items", "total_count", "has_next"}
    assert len(data["items"]) == 1 and data["total_count"] >= 2 and data["has_next"] is True
    total = admin.get(f"{SUB}/paginated?skip=0&limit=1&academic_year_id={pool['year']['id']}").json()["total_count"]
    last = admin.get(f"{SUB}/paginated?skip={total - 2}&limit=1&academic_year_id={pool['year']['id']}").json()
    assert len(last["items"]) == 1
    assert last["has_next"] is ((total - 2 + 1) < last["total_count"])


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A12")
@pytest.mark.parametrize("query", ["limit=1001", "limit=0", "skip=-1"])
def test_subject_paginated_bounds(admin, query):
    response = admin.get(f"{SUB}/paginated?{query}")
    assert response.status_code == 400
    assert "VALIDATION_ERROR" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A13")
def test_subject_dropdown_and_by_year(admin, cleanup, pool):
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    dropdown = admin.get(f"{SUB}/dropdown")
    assert dropdown.status_code == 200
    rows = dropdown.json()
    assert {"id": sub["id"], "name": sub["name"]} in rows
    names = [r["name"] for r in rows]
    assert names == sorted(names)
    by_year = admin.get(f"{SUB}/by-academic-year/{pool['year']['id']}")
    assert by_year.status_code == 200
    assert sub["id"] in [r["id"] for r in by_year.json()]
    assert all(r["academic_year_id"] == pool["year"]["id"] and r["is_active"] for r in by_year.json())


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A14")
def test_subjects_of_category(admin, cleanup, pool):
    cat = make_category(admin, cleanup)
    sub = make_subject(admin, cleanup, pool["year"]["id"], cat["id"])
    full = admin.get(f"{SUB}/categories/{cat['id']}/subjects")
    assert full.status_code == 200
    assert [r["id"] for r in full.json()] == [sub["id"]]
    assert full.json()[0]["category"] == cat
    small = admin.get(f"{SUB}/categories/{cat['id']}/subjects/dropdown")
    assert small.status_code == 200
    assert small.json() == [{"id": sub["id"], "name": sub["name"]}]
    admin.delete(f"{SUB}/{sub['id']}")
    assert admin.get(f"{SUB}/categories/{cat['id']}/subjects").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A15")
def test_get_subject(admin, cleanup, pool):
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    ok = admin.get(f"{SUB}/{sub['id']}")
    assert ok.status_code == 200
    assert ok.json()["category"] == pool["category"]
    missing = admin.get(f"{SUB}/{RANDOM_ID}")
    assert missing.status_code == 404
    assert "NOT_FOUND_ERROR" in missing.text


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A16")
def test_update_subject(admin, cleanup, pool):
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    new = unique("mstsub")
    response = admin.put(f"{SUB}/{sub['id']}", json={"name": new, "is_active": False})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == new and data["is_active"] is False
    assert data["category"] == pool["category"]
    assert data["short_code"] == sub["short_code"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A17")
def test_update_subject_to_existing_name(admin, cleanup, pool):
    a = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    b = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    response = admin.put(f"{SUB}/{b['id']}", json={"name": a["name"]})
    assert response.status_code == 400
    assert response.json()["detail"] == f"Subject with name '{a['name']}' already exists for this academic year"


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A18")
def test_update_unknown_subject(admin):
    response = admin.put(f"{SUB}/{RANDOM_ID}", json={"name": unique("mstsub")})
    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A19")
def test_deactivate_subject_is_idempotent(admin, cleanup, pool):
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    assert admin.delete(f"{SUB}/{sub['id']}").status_code == 204
    assert admin.delete(f"{SUB}/{sub['id']}").status_code == 204
    assert admin.get(f"{SUB}/{sub['id']}").json()["is_active"] is False
    assert sub["id"] not in [r["id"] for r in admin.get(f"{SUB}/?academic_year_id={pool['year']['id']}").json()]
    assert sub["id"] not in [r["id"] for r in admin.get(f"{SUB}/dropdown").json()]


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A20")
def test_deactivate_unknown_subject(admin):
    response = admin.delete(f"{SUB}/{RANDOM_ID}")
    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A21")
def test_subject_categories_endpoint(admin, cleanup):
    cat = make_category(admin, cleanup)
    response = admin.get(f"{SUB}/categories")
    assert response.status_code == 200
    assert cat in response.json()


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A22")
@pytest.mark.parametrize("role", ROLES)
def test_subject_read_matrix(role_clients, admin, cleanup, pool, role):
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    client = role_clients[role]
    for path in (f"{SUB}/", f"{SUB}/paginated", f"{SUB}/dropdown", f"{SUB}/{sub['id']}"):
        assert client.get(path).status_code == 200, (role, path)


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A23")
@pytest.mark.parametrize("role", DENIED)
def test_subject_write_denied(role_clients, admin, cleanup, pool, role):
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    client = role_clients[role]
    assert client.post(f"{SUB}/", json=subject_body(pool)).status_code == 403
    assert client.put(f"{SUB}/{sub['id']}", json={"name": unique("mstsub")}).status_code == 403
    assert client.delete(f"{SUB}/{sub['id']}").status_code == 403
    again = admin.get(f"{SUB}/{sub['id']}").json()
    assert again["name"] == sub["name"] and again["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A24")
def test_subject_endpoints_need_authentication(anon, pool):
    assert anon.post(f"{SUB}/", json=subject_body(pool)).status_code == 401
    for path in ("/", "/paginated", "/dropdown", "/categories", f"/{RANDOM_ID}", f"/by-academic-year/{RANDOM_ID}"):
        assert anon.get(f"{SUB}{path}").status_code == 401, path
    assert anon.get(f"{SUB}/categories/{RANDOM_ID}/subjects").status_code == 401
    assert anon.get(f"{SUB}/categories/{RANDOM_ID}/subjects/dropdown").status_code == 401
    assert anon.put(f"{SUB}/{RANDOM_ID}", json={"name": "x"}).status_code == 401
    assert anon.delete(f"{SUB}/{RANDOM_ID}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A25")
def test_subject_tenant_isolation(admin, tenant_b, cleanup, pool):
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    assert sub["id"] not in [r["id"] for r in tenant_b.get(f"{SUB}/?active_only=false").json()]
    assert sub["id"] not in [r["id"] for r in tenant_b.get(f"{SUB}/dropdown").json()]
    assert tenant_b.get(f"{SUB}/{sub['id']}").status_code == 404
    assert admin.get(f"{SUB}/", headers={"cschema": QA_B_TENANT}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A26")
def test_subject_dropdown_cache_is_invalidated_by_create_and_update(admin, cleanup, pool):
    admin.get(f"{SUB}/dropdown")
    sub = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    first = admin.get(f"{SUB}/dropdown").json()
    assert {"id": sub["id"], "name": sub["name"]} in first
    renamed = unique("mstsub")
    assert admin.put(f"{SUB}/{sub['id']}", json={"name": renamed}).status_code == 200
    second = admin.get(f"{SUB}/dropdown").json()
    assert {"id": sub["id"], "name": renamed} in second
    assert {"id": sub["id"], "name": sub["name"]} not in second


@pytest.mark.api
@pytest.mark.tc("TC-MST-08-A27")
@pytest.mark.skip(reason="The test API runs with rate limiting disabled, so the 429 cannot be produced")
def test_subject_rate_limit():
    pass
