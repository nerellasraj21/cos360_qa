import pytest

from api_tests.masters.helpers import DENIED, RANDOM_ID, make_class, make_mapping
from api_tests.support import QA_B_TENANT

BASE = "/masters/class-subject-mappings"
READERS = ["admin", "staff", "teacher"]
NO_GRANT = ["student", "parent"]


def purge(admin, class_id):
    listing = admin.get(f"{BASE}/?class_id={class_id}&active_only=false&limit=1000")
    for item in listing.json().get("items", []):
        admin.delete(f"{BASE}/{item['id']}")


def new_class(admin, cleanup, pool, **kw):
    cls = make_class(admin, cleanup, pool["year"]["id"], **kw)
    cleanup.add(purge, admin, cls["id"])
    return cls


def single(admin, cleanup, pool, cls, section_index=0, subject_index=0, **over):
    section_id = cls["sections"][section_index]["id"] if section_index is not None else None
    return make_mapping(
        admin, cleanup, cls["id"], section_id, pool["subjects"][subject_index]["id"], pool["year"]["id"], **over
    )


def bulk(admin, pool, cls, subjects, section_id="__none__", year_id=None, **extra):
    body = {"class_id": cls["id"], "academic_year_id": year_id or pool["year"]["id"], "subjects": subjects}
    if section_id != "__none__":
        body["section_id"] = section_id
    body.update(extra)
    return admin.post(f"{BASE}/bulk", json=body)


def sub_item(pool, index, **over):
    item = {"subject_id": pool["subjects"][index]["id"]}
    item.update(over)
    return item


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A01")
def test_create_mapping_shape(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    section = cls["sections"][0]
    data = single(admin, cleanup, pool, cls, order=1, exclude_marks=True)
    assert data["class_name"] == cls["name"]
    assert data["section_name"] == section["name"]
    assert data["subject_name"] == pool["subjects"][0]["name"]
    assert data["academic_year_name"] == pool["year"]["title"]
    assert data["order"] == 1 and data["exclude_marks"] is True and data["is_active"] is True
    assert data["section_id"] == section["id"]
    assert {"id", "created_at", "updated_at"} <= set(data)


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A02")
def test_create_class_level_mapping(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    data = single(admin, cleanup, pool, cls, section_index=None)
    assert data["section_id"] is None and data["section_name"] is None


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A03")
def test_duplicate_single_mapping_is_conflict(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    single(admin, cleanup, pool, cls)
    body = {
        "class_id": cls["id"],
        "section_id": cls["sections"][0]["id"],
        "subject_id": pool["subjects"][0]["id"],
        "academic_year_id": pool["year"]["id"],
    }
    response = admin.post(f"{BASE}/", json=body)
    assert response.status_code == 409, response.text


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A04")
def test_create_mapping_missing_class_id(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    body = {
        "section_id": cls["sections"][0]["id"],
        "subject_id": pool["subjects"][0]["id"],
        "academic_year_id": pool["year"]["id"],
    }
    assert admin.post(f"{BASE}/", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A04")
def test_create_mapping_unknown_subject(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    body = {
        "class_id": cls["id"],
        "section_id": cls["sections"][0]["id"],
        "subject_id": RANDOM_ID,
        "academic_year_id": pool["year"]["id"],
    }
    bad = admin.post(f"{BASE}/", json=body)
    assert bad.status_code == 400
    assert bad.json()["detail"] == "Class, section, subject or academic year not found."


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A05")
def test_list_default_active_only_and_order(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    m1 = single(admin, cleanup, pool, cls, section_index=1, subject_index=0, order=2)
    m2 = single(admin, cleanup, pool, cls, section_index=0, subject_index=1, order=5)
    m3 = single(admin, cleanup, pool, cls, section_index=0, subject_index=2, order=1)
    off = single(admin, cleanup, pool, cls, section_index=0, subject_index=3, is_active=False)
    response = admin.get(f"{BASE}/?class_id={cls['id']}")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"items", "total_count", "has_next"}
    ids = [i["id"] for i in data["items"]]
    assert off["id"] not in ids
    assert data["total_count"] == 3 and data["has_next"] is False
    expected = sorted([m1, m2, m3], key=lambda m: (m["section_id"], m["order"]))
    assert ids == [m["id"] for m in expected]


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A06")
def test_list_filters_combine(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    a0 = single(admin, cleanup, pool, cls, section_index=0, subject_index=0)
    a1 = single(admin, cleanup, pool, cls, section_index=0, subject_index=1, is_active=False)
    single(admin, cleanup, pool, cls, section_index=1, subject_index=0)
    query = (
        f"?class_id={cls['id']}&section_id={cls['sections'][0]['id']}"
        f"&academic_year_id={pool['year']['id']}&active_only=false"
    )
    rows = admin.get(f"{BASE}/{query}").json()["items"]
    assert sorted(r["id"] for r in rows) == sorted([a0["id"], a1["id"]])
    other_year = admin.get(f"{BASE}/?class_id={cls['id']}&academic_year_id={pool['year2']['id']}&active_only=false")
    assert other_year.json()["items"] == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A07")
@pytest.mark.parametrize("query", ["limit=0", "limit=1001", "skip=-1"])
def test_list_bounds(admin, query):
    assert admin.get(f"{BASE}/?{query}").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A08")
def test_list_pagination(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    for i in range(3):
        single(admin, cleanup, pool, cls, subject_index=i, order=i + 1)
    first = admin.get(f"{BASE}/?class_id={cls['id']}&skip=0&limit=2").json()
    assert len(first["items"]) == 2 and first["total_count"] == 3 and first["has_next"] is True
    second = admin.get(f"{BASE}/?class_id={cls['id']}&skip=2&limit=2").json()
    assert len(second["items"]) == 1 and second["has_next"] is False


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A09")
def test_by_class_repeats_subject_per_section_and_orders(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    single(admin, cleanup, pool, cls, section_index=0, subject_index=0, order=3)
    single(admin, cleanup, pool, cls, section_index=1, subject_index=0, order=3)
    single(admin, cleanup, pool, cls, section_index=0, subject_index=1, order=1)
    single(admin, cleanup, pool, cls, section_index=0, subject_index=2)
    response = admin.get(f"{BASE}/by-class/{cls['id']}")
    assert response.status_code == 200
    rows = response.json()
    first_subject = pool["subjects"][0]["id"]
    assert [r["subject_id"] for r in rows].count(first_subject) == 2
    orders = [r["order"] for r in rows]
    assert orders[0] is None
    assert orders[1:] == sorted(orders[1:])


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A10")
def test_by_class_with_filters(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    a = single(admin, cleanup, pool, cls, section_index=0, subject_index=0)
    b = single(admin, cleanup, pool, cls, section_index=0, subject_index=1, is_active=False)
    single(admin, cleanup, pool, cls, section_index=1, subject_index=0)
    query = f"?section_id={cls['sections'][0]['id']}&academic_year_id={pool['year']['id']}&active_only=false"
    rows = admin.get(f"{BASE}/by-class/{cls['id']}{query}").json()
    assert sorted(r["id"] for r in rows) == sorted([a["id"], b["id"]])


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A11")
def test_by_classes_includes_empty_keys(admin, cleanup, pool):
    c1 = new_class(admin, cleanup, pool)
    c2 = new_class(admin, cleanup, pool)
    m = single(admin, cleanup, pool, c1)
    response = admin.get(f"{BASE}/by-classes?class_ids={c1['id']}&class_ids={c2['id']}")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {c1["id"], c2["id"]}
    assert [r["id"] for r in data[c1["id"]]] == [m["id"]]
    assert data[c2["id"]] == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A12")
def test_by_classes_requires_class_ids(admin):
    assert admin.get(f"{BASE}/by-classes").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A13")
def test_dropdown_shape(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    m = single(admin, cleanup, pool, cls, order=4, exclude_marks=True)
    off = single(admin, cleanup, pool, cls, subject_index=1, is_active=False)
    response = admin.get(f"{BASE}/dropdown?class_id={cls['id']}")
    assert response.status_code == 200
    rows = response.json()
    assert [r["id"] for r in rows] == [m["id"]]
    assert off["id"] not in [r["id"] for r in rows]
    assert rows[0] == {
        "id": m["id"],
        "class_name": cls["name"],
        "section_name": cls["sections"][0]["name"],
        "subject_name": pool["subjects"][0]["name"],
        "exclude_marks": True,
        "order": 4,
    }


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A14")
def test_dropdown_with_class_level_mapping(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    single(admin, cleanup, pool, cls, section_index=None)
    response = admin.get(f"{BASE}/dropdown?class_id={cls['id']}")
    assert response.status_code == 200, response.text


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A15")
def test_get_mapping_by_id(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    m = single(admin, cleanup, pool, cls)
    ok = admin.get(f"{BASE}/{m['id']}")
    assert ok.status_code == 200 and ok.json()["id"] == m["id"]
    missing = admin.get(f"{BASE}/{RANDOM_ID}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Class-subject mapping not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A16")
def test_update_mapping_flags(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    m = single(admin, cleanup, pool, cls, exclude_marks=True)
    response = admin.put(f"{BASE}/{m['id']}", json={"exclude_marks": False, "order": 5, "is_active": False})
    assert response.status_code == 200
    data = response.json()
    assert data["exclude_marks"] is False and data["order"] == 5 and data["is_active"] is False
    assert data["class_name"] == m["class_name"] and data["subject_name"] == m["subject_name"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A17")
def test_update_mapping_bad_subject(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    m = single(admin, cleanup, pool, cls)
    response = admin.put(f"{BASE}/{m['id']}", json={"subject_id": RANDOM_ID})
    assert response.status_code == 400
    assert response.json()["detail"] == "Update failed"


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A18")
def test_update_delete_unknown_mapping(admin):
    assert admin.put(f"{BASE}/{RANDOM_ID}", json={"order": 1}).status_code == 404
    assert admin.delete(f"{BASE}/{RANDOM_ID}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A19")
def test_delete_mapping(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    m = single(admin, cleanup, pool, cls)
    assert admin.delete(f"{BASE}/{m['id']}").status_code == 204
    assert admin.get(f"{BASE}/{m['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A20")
@pytest.mark.parametrize("role", READERS)
def test_mapping_read_matrix_granted(role_clients, admin, cleanup, pool, role):
    cls = new_class(admin, cleanup, pool)
    m = single(admin, cleanup, pool, cls)
    client = role_clients[role]
    paths = [
        f"{BASE}/?class_id={cls['id']}",
        f"{BASE}/by-class/{cls['id']}",
        f"{BASE}/by-classes?class_ids={cls['id']}",
        f"{BASE}/dropdown?class_id={cls['id']}",
        f"{BASE}/{m['id']}",
    ]
    for path in paths:
        assert client.get(path).status_code == 200, (role, path)


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A21")
@pytest.mark.parametrize("role", NO_GRANT)
def test_mapping_read_matrix_denied(role_clients, admin, cleanup, pool, role):
    cls = new_class(admin, cleanup, pool)
    m = single(admin, cleanup, pool, cls)
    client = role_clients[role]
    paths = [
        f"{BASE}/?class_id={cls['id']}",
        f"{BASE}/by-class/{cls['id']}",
        f"{BASE}/by-classes?class_ids={cls['id']}",
        f"{BASE}/dropdown?class_id={cls['id']}",
        f"{BASE}/{m['id']}",
    ]
    for path in paths:
        assert client.get(path).status_code == 403, (role, path)


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A22")
@pytest.mark.parametrize("role", DENIED)
def test_mapping_write_denied(role_clients, admin, cleanup, pool, role):
    cls = new_class(admin, cleanup, pool)
    m = single(admin, cleanup, pool, cls)
    client = role_clients[role]
    body = {
        "class_id": cls["id"],
        "section_id": cls["sections"][1]["id"],
        "subject_id": pool["subjects"][1]["id"],
        "academic_year_id": pool["year"]["id"],
    }
    assert client.post(f"{BASE}/", json=body).status_code == 403
    assert client.put(f"{BASE}/{m['id']}", json={"order": 9}).status_code == 403
    assert client.delete(f"{BASE}/{m['id']}").status_code == 403
    assert admin.get(f"{BASE}/{m['id']}").json()["order"] == m["order"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A23")
def test_mapping_endpoints_need_authentication(anon, pool):
    body = {
        "class_id": RANDOM_ID,
        "subject_id": RANDOM_ID,
        "academic_year_id": pool["year"]["id"],
    }
    assert anon.post(f"{BASE}/", json=body).status_code == 401
    for path in ("/", f"/by-class/{RANDOM_ID}", f"/by-classes?class_ids={RANDOM_ID}", "/dropdown", f"/{RANDOM_ID}"):
        assert anon.get(f"{BASE}{path}").status_code == 401, path
    assert anon.put(f"{BASE}/{RANDOM_ID}", json={"order": 1}).status_code == 401
    assert anon.delete(f"{BASE}/{RANDOM_ID}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A24")
def test_mapping_tenant_isolation(admin, tenant_b, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    m = single(admin, cleanup, pool, cls)
    assert tenant_b.get(f"{BASE}/?class_id={cls['id']}&active_only=false").json()["items"] == []
    assert tenant_b.get(f"{BASE}/by-class/{cls['id']}").json() == []
    assert tenant_b.get(f"{BASE}/by-classes?class_ids={cls['id']}").json() == {cls["id"]: []}
    assert tenant_b.get(f"{BASE}/{m['id']}").status_code == 404
    assert admin.get(f"{BASE}/", headers={"cschema": QA_B_TENANT}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-MST-09-A25")
@pytest.mark.skip(reason="The test API runs with rate limiting disabled, so the 429 cannot be produced")
def test_mapping_create_rate_limit():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A01")
def test_bulk_create(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    section = cls["sections"][0]
    response = bulk(
        admin,
        pool,
        cls,
        [sub_item(pool, 0, order=1), sub_item(pool, 1, order=2, exclude_marks=True)],
        section_id=section["id"],
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["success"] is True
    assert data["created_count"] == 2 and data["updated_count"] == 0 and data["deactivated_count"] == 0
    assert data["sections_processed"] == 1
    assert len(data["mappings"]) == 2
    by_subject = {m["subject_id"]: m for m in data["mappings"]}
    second = by_subject[pool["subjects"][1]["id"]]
    assert second["exclude_marks"] is True and second["order"] == 2
    assert second["class_name"] == cls["name"] and second["section_name"] == section["name"]
    assert second["subject_name"] == pool["subjects"][1]["name"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A02")
def test_bulk_second_call_updates_and_keeps_others(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    sid = cls["sections"][0]["id"]
    assert bulk(admin, pool, cls, [sub_item(pool, 0, order=1), sub_item(pool, 1, order=2)], section_id=sid).status_code == 201
    response = bulk(admin, pool, cls, [sub_item(pool, 0, order=5), sub_item(pool, 2)], section_id=sid)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["updated_count"] == 1 and data["created_count"] == 1 and data["deactivated_count"] == 0
    rows = {r["subject_id"]: r for r in admin.get(f"{BASE}/by-class/{cls['id']}?section_id={sid}").json()}
    assert set(rows) == {pool["subjects"][i]["id"] for i in (0, 1, 2)}
    assert rows[pool["subjects"][0]["id"]]["order"] == 5
    assert rows[pool["subjects"][1]["id"]]["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A03")
def test_bulk_empty_subject_list(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    response = bulk(admin, pool, cls, [], section_id=cls["sections"][0]["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["mappings"] == [] and data["created_count"] == 0 and data["updated_count"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A04")
def test_bulk_without_section_fans_out_to_active_sections(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool, sections=("A", "B", "C"))
    c = next(s for s in cls["sections"] if s["name"] == "C")
    assert admin.put(f"/masters/class_sections/sections/{c['id']}", json={"id": None, "is_active": False}).status_code == 200
    response = bulk(admin, pool, cls, [sub_item(pool, 0)])
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["sections_processed"] == 2
    used = {m["section_id"] for m in data["mappings"]}
    assert used == {s["id"] for s in cls["sections"] if s["name"] in ("A", "B")}
    assert c["id"] not in used


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A05")
def test_bulk_without_active_sections(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool, sections=None)
    response = bulk(admin, pool, cls, [sub_item(pool, 0)])
    assert response.status_code == 404
    assert response.json()["detail"] == "No active sections found for this class"


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A06")
def test_bulk_section_of_another_class(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    other = new_class(admin, cleanup, pool)
    response = bulk(admin, pool, cls, [sub_item(pool, 0)], section_id=other["sections"][0]["id"])
    assert response.status_code == 404
    assert response.json()["detail"] == "Section not found or does not belong to the specified class"


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A07")
def test_bulk_unknown_class_and_year(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    unknown_class = admin.post(
        f"{BASE}/bulk",
        json={
            "class_id": RANDOM_ID,
            "section_id": None,
            "academic_year_id": pool["year"]["id"],
            "subjects": [sub_item(pool, 0)],
        },
    )
    assert unknown_class.status_code == 404
    assert unknown_class.json()["detail"] == "Class not found"
    unknown_year = bulk(admin, pool, cls, [sub_item(pool, 0)], year_id=RANDOM_ID)
    assert unknown_year.status_code == 404
    assert unknown_year.json()["detail"] == "Academic year not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A08")
def test_bulk_skips_unknown_subject(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    response = bulk(
        admin,
        pool,
        cls,
        [{"subject_id": RANDOM_ID}, sub_item(pool, 0)],
        section_id=cls["sections"][0]["id"],
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["created_count"] == 1
    assert [m["subject_id"] for m in data["mappings"]] == [pool["subjects"][0]["id"]]


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A09")
def test_bulk_duplicate_subject_in_request_collapses(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    sid = cls["sections"][0]["id"]
    response = bulk(admin, pool, cls, [sub_item(pool, 0, order=1), sub_item(pool, 0, order=7)], section_id=sid)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["created_count"] == 1
    rows = admin.get(f"{BASE}/by-class/{cls['id']}?section_id={sid}&active_only=false").json()
    assert len(rows) == 1 and rows[0]["order"] == 7


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A10")
def test_bulk_validation_errors(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    good = {"class_id": cls["id"], "academic_year_id": pool["year"]["id"], "subjects": [sub_item(pool, 0)]}
    for missing in ("class_id", "academic_year_id", "subjects"):
        body = dict(good)
        body.pop(missing)
        assert admin.post(f"{BASE}/bulk", json=body).status_code == 422, missing
    bad = dict(good, subjects=[{"subject_id": "not-a-uuid"}])
    assert admin.post(f"{BASE}/bulk", json=bad).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A11")
def test_by_class_reflects_latest_bulk(admin, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    sid = cls["sections"][0]["id"]
    bulk(admin, pool, cls, [sub_item(pool, 0, order=1), sub_item(pool, 1, order=2)], section_id=sid)
    bulk(admin, pool, cls, [sub_item(pool, 0, order=5), sub_item(pool, 2, order=3)], section_id=sid)
    rows = admin.get(f"{BASE}/by-class/{cls['id']}?section_id={sid}").json()
    got = {r["subject_id"]: r["order"] for r in rows}
    assert got[pool["subjects"][0]["id"]] == 5
    assert got[pool["subjects"][2]["id"]] == 3
    assert all(r["is_active"] for r in rows)


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A12")
@pytest.mark.parametrize("role", DENIED)
def test_bulk_denied(role_clients, admin, cleanup, pool, role):
    cls = new_class(admin, cleanup, pool)
    body = {
        "class_id": cls["id"],
        "section_id": cls["sections"][0]["id"],
        "academic_year_id": pool["year"]["id"],
        "subjects": [sub_item(pool, 0)],
    }
    assert role_clients[role].post(f"{BASE}/bulk", json=body).status_code == 403
    assert admin.get(f"{BASE}/by-class/{cls['id']}").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A13")
def test_bulk_needs_authentication(anon, pool):
    body = {"class_id": RANDOM_ID, "academic_year_id": pool["year"]["id"], "subjects": []}
    assert anon.post(f"{BASE}/bulk", json=body).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A14")
def test_bulk_tenant_isolation(admin, tenant_b, cleanup, pool):
    cls = new_class(admin, cleanup, pool)
    response = tenant_b.post(
        f"{BASE}/bulk",
        json={
            "class_id": cls["id"],
            "section_id": None,
            "academic_year_id": tenant_b.academic_year_id,
            "subjects": [sub_item(pool, 0)],
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Class not found"
    assert admin.get(f"{BASE}/by-class/{cls['id']}").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-10-A15")
@pytest.mark.skip(reason="The test API runs with rate limiting disabled, so the 429 cannot be produced")
def test_bulk_rate_limit():
    pass
