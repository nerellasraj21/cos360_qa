import pytest

from api_tests.masters.helpers import (
    DENIED,
    RANDOM_ID,
    ROLES,
    class_body,
    make_class,
    make_mapping,
    make_year,
)
from api_tests.support import QA_B_TENANT, unique

BASE = "/masters/class_sections"
CLASS_KEYS = {"id", "name", "description", "is_active", "short_code", "academic_year_id", "sections"}


def section_names(cls):
    return sorted(s["name"] for s in cls["sections"])


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A01")
def test_create_class_with_two_sections(admin, cleanup, pool):
    body = class_body(pool["year"]["id"])
    response = admin.post(f"{BASE}/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}/{data['id']}")
    assert CLASS_KEYS <= set(data)
    assert data["name"] == body["name"]
    assert len(data["sections"]) == 2
    assert all(s["class_id"] == data["id"] and s["is_active"] is True for s in data["sections"])
    assert section_names(data) == ["A", "B"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A02")
def test_create_class_without_sections(admin, cleanup, pool):
    data = make_class(admin, cleanup, pool["year"]["id"], sections=None)
    assert data["sections"] == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A03")
def test_duplicate_class_name_in_same_year(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    response = admin.post(f"{BASE}/", json=class_body(pool["year"]["id"], name=cls["name"]))
    assert response.status_code == 400
    assert response.json()["detail"] == f"Class '{cls['name']}' already exists for this academic year"


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A04")
def test_duplicate_sections_in_payload_leave_no_class(admin, pool):
    body = class_body(pool["year"]["id"], sections=("A", "A"))
    response = admin.post(f"{BASE}/", json=body)
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Error creating class with sections")
    names = [c["name"] for c in admin.get(f"{BASE}/read_all?academic_year_id={pool['year']['id']}").json()]
    assert body["name"] not in names


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A05")
def test_section_names_repeat_across_classes(admin, cleanup, pool):
    a = make_class(admin, cleanup, pool["year"]["id"])
    b = make_class(admin, cleanup, pool["year"]["id"])
    assert section_names(a) == section_names(b) == ["A", "B"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A06")
@pytest.mark.parametrize("missing", ["short_code", "name", "academic_year_id"])
def test_create_class_missing_required_field(admin, pool, missing):
    body = class_body(pool["year"]["id"])
    body.pop(missing)
    response = admin.post(f"{BASE}/", json=body)
    assert response.status_code == 422
    assert any(missing in err["loc"] for err in response.json()["detail"])


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A07")
def test_class_length_boundaries(admin, cleanup, pool):
    year = pool["year"]["id"]
    ok = admin.post(f"{BASE}/", json=class_body(year, sections=None, name="n" + unique("")[:8] + "x" * 41, short_code="s" * 10))
    assert ok.status_code == 201, ok.text
    cleanup.delete_later(admin, f"{BASE}/{ok.json()['id']}")
    assert len(ok.json()["name"]) == 50
    long_name = admin.post(f"{BASE}/", json=class_body(year, sections=None, name="n" + unique("") + "x" * 42))
    assert long_name.status_code == 400
    long_code = admin.post(f"{BASE}/", json=class_body(year, sections=None, short_code="s" * 11))
    assert long_code.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A08")
def test_create_class_unknown_year(admin):
    response = admin.post(f"{BASE}/", json=class_body(RANDOM_ID))
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A09")
def test_same_class_name_in_another_year(admin, cleanup, pool):
    first = make_class(admin, cleanup, pool["year"]["id"])
    second = admin.post(f"{BASE}/", json=class_body(pool["year2"]["id"], name=first["name"]))
    assert second.status_code == 201, second.text
    cleanup.delete_later(admin, f"{BASE}/{second.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A10")
def test_read_all_filters_by_year(admin, cleanup, pool):
    c1 = make_class(admin, cleanup, pool["year"]["id"])
    c2 = make_class(admin, cleanup, pool["year2"]["id"])
    filtered = admin.get(f"{BASE}/read_all?academic_year_id={pool['year']['id']}")
    assert filtered.status_code == 200
    ids = [c["id"] for c in filtered.json()]
    assert c1["id"] in ids and c2["id"] not in ids
    mine = next(c for c in filtered.json() if c["id"] == c1["id"])
    assert section_names(mine) == ["A", "B"]
    names = [c["name"] for c in filtered.json()]
    assert names == sorted(names)
    everything = [c["id"] for c in admin.get(f"{BASE}/read_all").json()]
    assert c1["id"] in everything and c2["id"] in everything


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A10")
def test_read_all_active_only(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"], is_active=False)
    default = [c["id"] for c in admin.get(f"{BASE}/read_all?academic_year_id={pool['year']['id']}").json()]
    assert cls["id"] in default
    active = [c["id"] for c in admin.get(f"{BASE}/read_all?academic_year_id={pool['year']['id']}&active_only=true").json()]
    assert cls["id"] not in active


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A11")
def test_read_all_with_no_classes_is_empty_list(admin, cleanup):
    year = make_year(admin, cleanup)
    response = admin.get(f"{BASE}/read_all?academic_year_id={year['id']}")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A12")
def test_get_class_by_id(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    response = admin.get(f"{BASE}/by_class_id/{cls['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == cls["id"]
    assert section_names(data) == ["A", "B"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A13")
def test_get_class_by_unknown_id(admin):
    response = admin.get(f"{BASE}/by_class_id/{RANDOM_ID}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Class not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A14")
@pytest.mark.parametrize("role", ROLES)
def test_class_read_matrix(role_clients, admin, cleanup, pool, role):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    client = role_clients[role]
    assert client.get(f"{BASE}/read_all?academic_year_id={pool['year']['id']}").status_code == 200
    assert client.get(f"{BASE}/by_class_id/{cls['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A15")
@pytest.mark.parametrize("role", DENIED)
def test_class_create_denied(role_clients, pool, role):
    response = role_clients[role].post(f"{BASE}/", json=class_body(pool["year"]["id"]))
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A16")
def test_class_endpoints_need_authentication(anon, pool):
    assert anon.post(f"{BASE}/", json=class_body(pool["year"]["id"])).status_code == 401
    assert anon.get(f"{BASE}/read_all").status_code == 401
    assert anon.get(f"{BASE}/by_class_id/{RANDOM_ID}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A17")
def test_class_tenant_isolation(admin, tenant_b, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    assert cls["id"] not in [c["id"] for c in tenant_b.get(f"{BASE}/read_all").json()]
    assert tenant_b.get(f"{BASE}/by_class_id/{cls['id']}").status_code == 404
    assert admin.get(f"{BASE}/read_all", headers={"cschema": QA_B_TENANT}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-MST-03-A18")
@pytest.mark.skip(reason="The test API runs with rate limiting disabled, so the 429 cannot be produced")
def test_class_create_rate_limit():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A01")
def test_update_class_name_keeps_sections(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    new_name = unique("mstc")
    response = admin.put(f"{BASE}/{cls['id']}", json={"name": new_name, "academic_year_id": pool["year"]["id"]})
    assert response.status_code == 200
    assert response.json() == {"message": "Class and sections updated successfully"}
    data = admin.get(f"{BASE}/by_class_id/{cls['id']}").json()
    assert data["name"] == new_name
    assert sorted(s["id"] for s in data["sections"]) == sorted(s["id"] for s in cls["sections"])


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A02")
def test_deactivate_class_hides_from_dropdown(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    response = admin.put(f"{BASE}/{cls['id']}", json={"is_active": False, "academic_year_id": pool["year"]["id"]})
    assert response.status_code == 200
    assert cls["id"] not in [c["id"] for c in admin.get(f"{BASE}/dropdown").json()]
    assert cls["id"] in [c["id"] for c in admin.get(f"{BASE}/read_all").json()]


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A03")
def test_update_class_without_year_is_422(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    assert admin.put(f"{BASE}/{cls['id']}", json={"name": unique("mstc")}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A04")
def test_update_class_with_null_year_is_400(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    response = admin.put(f"{BASE}/{cls['id']}", json={"academic_year_id": None})
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A05")
def test_rename_to_existing_class_name(admin, cleanup, pool):
    a = make_class(admin, cleanup, pool["year"]["id"])
    b = make_class(admin, cleanup, pool["year"]["id"])
    response = admin.put(f"{BASE}/{b['id']}", json={"name": a["name"], "academic_year_id": pool["year"]["id"]})
    assert response.status_code == 400
    assert response.json()["detail"] == f"Class '{a['name']}' already exists for this academic year"


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A06")
def test_update_with_sections_replaces_section_ids(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    response = admin.put(
        f"{BASE}/{cls['id']}",
        json={"academic_year_id": pool["year"]["id"], "sections": [{"id": None, "name": "Z"}]},
    )
    assert response.status_code == 200, response.text
    data = admin.get(f"{BASE}/by_class_id/{cls['id']}").json()
    assert section_names(data) == ["Z"]
    assert data["sections"][0]["id"] not in [s["id"] for s in cls["sections"]]


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A07")
def test_update_with_sections_blocked_by_mapping(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    section = cls["sections"][0]
    mapping = make_mapping(admin, cleanup, cls["id"], section["id"], pool["subjects"][0]["id"], pool["year"]["id"])
    response = admin.put(
        f"{BASE}/{cls['id']}",
        json={"academic_year_id": pool["year"]["id"], "sections": [{"id": None, "name": "Z"}]},
    )
    assert response.status_code == 400
    data = admin.get(f"{BASE}/by_class_id/{cls['id']}").json()
    assert sorted(s["id"] for s in data["sections"]) == sorted(s["id"] for s in cls["sections"])
    assert admin.get(f"/masters/class-subject-mappings/{mapping['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A08")
def test_update_unknown_class_is_404(admin, pool):
    response = admin.put(f"{BASE}/{RANDOM_ID}", json={"name": "x", "academic_year_id": pool["year"]["id"]})
    assert response.status_code == 404
    assert response.json()["detail"] == "Class not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A09")
def test_delete_class_removes_sections(admin, pool):
    created = admin.post(f"{BASE}/", json=class_body(pool["year"]["id"]))
    cls = created.json()
    response = admin.delete(f"{BASE}/{cls['id']}")
    assert response.status_code == 204
    assert admin.get(f"{BASE}/by_class_id/{cls['id']}").status_code == 404
    for section in cls["sections"]:
        assert admin.get(f"{BASE}/sections/{section['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A10")
def test_delete_class_blocked_by_mapping(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=("A",))
    make_mapping(admin, cleanup, cls["id"], None, pool["subjects"][0]["id"], pool["year"]["id"])
    response = admin.delete(f"{BASE}/{cls['id']}")
    assert response.status_code == 400
    assert "being used by 1 record(s): 1 subject mapping(s)" in response.json()["detail"]
    assert admin.get(f"{BASE}/by_class_id/{cls['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A11")
def test_delete_class_blocked_by_section_timetable(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=("A",))
    section = cls["sections"][0]
    timetable = admin.post(
        "/students/timetable/frontend",
        json={
            "section_id": section["id"],
            "timetable_data": [
                {
                    "time": {"from": "09:00", "to": "09:45"},
                    "type": "subject",
                    "subjects": {"Monday": pool["subjects"][0]["id"]},
                }
            ],
        },
    )
    assert timetable.status_code == 200, timetable.text
    cleanup.delete_later(admin, f"/students/timetable/frontend/{section['id']}")
    blocked = admin.delete(f"{BASE}/{cls['id']}")
    assert blocked.status_code == 400
    assert "section-related record(s)" in blocked.json()["detail"]
    assert admin.delete(f"/students/timetable/frontend/{section['id']}").status_code == 200
    assert admin.delete(f"{BASE}/{cls['id']}").status_code == 204


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A12")
def test_delete_unknown_class_is_404(admin):
    assert admin.delete(f"{BASE}/{RANDOM_ID}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A13")
@pytest.mark.parametrize("role", DENIED)
def test_class_update_delete_denied(role_clients, admin, cleanup, pool, role):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    client = role_clients[role]
    put = client.put(f"{BASE}/{cls['id']}", json={"name": unique("mstc"), "academic_year_id": pool["year"]["id"]})
    assert put.status_code == 403
    assert client.delete(f"{BASE}/{cls['id']}").status_code == 403
    assert admin.get(f"{BASE}/by_class_id/{cls['id']}").json()["name"] == cls["name"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A14")
def test_class_update_delete_need_authentication(anon, pool):
    put = anon.put(f"{BASE}/{RANDOM_ID}", json={"name": "x", "academic_year_id": pool["year"]["id"]})
    assert put.status_code == 401
    assert anon.delete(f"{BASE}/{RANDOM_ID}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A15")
def test_class_update_delete_tenant_isolation(admin, tenant_b, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    put = tenant_b.put(
        f"{BASE}/{cls['id']}", json={"name": unique("mstc"), "academic_year_id": tenant_b.academic_year_id}
    )
    assert put.status_code == 404
    assert tenant_b.delete(f"{BASE}/{cls['id']}").status_code == 404
    assert admin.get(f"{BASE}/by_class_id/{cls['id']}").json()["name"] == cls["name"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-04-A16")
def test_delete_invalidates_class_lookups(admin, pool):
    cls = admin.post(f"{BASE}/", json=class_body(pool["year"]["id"])).json()
    assert cls["id"] in [c["id"] for c in admin.get(f"{BASE}/dropdown").json()]
    assert cls["id"] in [c["id"] for c in admin.get(f"{BASE}/class-list").json()]
    assert admin.delete(f"{BASE}/{cls['id']}").status_code == 204
    assert cls["id"] not in [c["id"] for c in admin.get(f"{BASE}/dropdown").json()]
    assert cls["id"] not in [c["id"] for c in admin.get(f"{BASE}/class-list").json()]


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A01")
def test_add_sections(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    response = admin.post(f"{BASE}/{cls['id']}/sections", json=[{"name": "C"}, {"name": "D"}])
    assert response.status_code == 201, response.text
    rows = response.json()
    assert sorted(r["name"] for r in rows) == ["C", "D"]
    assert all(r["class_id"] == cls["id"] and r["is_active"] is True for r in rows)


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A02")
def test_add_empty_section_list(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    response = admin.post(f"{BASE}/{cls['id']}/sections", json=[])
    assert response.status_code == 201
    assert response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A03")
def test_add_single_object_instead_of_list(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    assert admin.post(f"{BASE}/{cls['id']}/sections", json={"name": "E"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A04")
def test_add_duplicate_sections(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    existing = admin.post(f"{BASE}/{cls['id']}/sections", json=[{"name": "A"}])
    assert existing.status_code == 400
    assert existing.json()["detail"].startswith("Error adding sections")
    twice = admin.post(f"{BASE}/{cls['id']}/sections", json=[{"name": "Q"}, {"name": "Q"}])
    assert twice.status_code == 400
    assert twice.json()["detail"].startswith("Error adding sections")
    data = admin.get(f"{BASE}/by_class_id/{cls['id']}").json()
    assert section_names(data) == ["A", "B"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A05")
def test_add_sections_unknown_class(admin):
    response = admin.post(f"{BASE}/{RANDOM_ID}/sections", json=[{"name": "A"}])
    assert response.status_code == 404
    assert response.json()["detail"] == "Class not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A06")
def test_section_name_length_boundary(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=None)
    ok = admin.post(f"{BASE}/{cls['id']}/sections", json=[{"name": "s" * 50}])
    assert ok.status_code == 201
    too_long = admin.post(f"{BASE}/{cls['id']}/sections", json=[{"name": "t" * 51}])
    assert too_long.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A07")
def test_get_section(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    section = cls["sections"][0]
    response = admin.get(f"{BASE}/sections/{section['id']}")
    assert response.status_code == 200
    data = response.json()
    assert {"id", "name", "description", "is_active", "class_id", "created_at", "updated_at"} <= set(data)
    assert data["class_id"] == cls["id"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A08")
def test_get_unknown_section(admin):
    response = admin.get(f"{BASE}/sections/{RANDOM_ID}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Section not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A09")
def test_update_section(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    section = cls["sections"][0]
    response = admin.put(f"{BASE}/sections/{section['id']}", json={"id": None, "name": "A2", "is_active": False})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "A2" and data["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A10")
def test_update_section_without_id_in_body(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    assert admin.put(f"{BASE}/sections/{cls['sections'][0]['id']}", json={"name": "A2"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A11")
def test_update_section_null_values_ignored(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    sid = cls["sections"][0]["id"]
    assert admin.put(f"{BASE}/sections/{sid}", json={"id": None, "description": "keep"}).status_code == 200
    response = admin.put(f"{BASE}/sections/{sid}", json={"id": None, "description": None})
    assert response.status_code == 200
    assert response.json()["description"] == "keep"


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A12")
def test_rename_section_to_sibling_name(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    a, b = cls["sections"]
    response = admin.put(f"{BASE}/sections/{a['id']}", json={"id": None, "name": b["name"]})
    assert response.status_code == 400
    assert response.json()["detail"] == "A section with this name already exists in the class"


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A13")
def test_update_unknown_section(admin):
    response = admin.put(f"{BASE}/sections/{RANDOM_ID}", json={"id": None, "name": "A"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Section not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A14")
def test_delete_section(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    sid = cls["sections"][0]["id"]
    response = admin.delete(f"{BASE}/sections/{sid}")
    assert response.status_code == 200
    assert response.json() == {"message": "Section deleted successfully"}
    assert admin.get(f"{BASE}/sections/{sid}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A15")
def test_delete_section_blocked_by_mapping(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    sid = cls["sections"][0]["id"]
    make_mapping(admin, cleanup, cls["id"], sid, pool["subjects"][0]["id"], pool["year"]["id"])
    response = admin.delete(f"{BASE}/sections/{sid}")
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Cannot delete this section because it is referenced")
    assert admin.get(f"{BASE}/sections/{sid}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A16")
def test_delete_unknown_section(admin):
    assert admin.delete(f"{BASE}/sections/{RANDOM_ID}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A17")
def test_nested_section_paths_do_not_exist(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    sid = cls["sections"][0]["id"]
    assert admin.put(f"{BASE}/{cls['id']}/sections/{sid}", json={"id": None, "name": "Q"}).status_code in (404, 405)
    assert admin.delete(f"{BASE}/{cls['id']}/sections/{sid}").status_code in (404, 405)


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A18")
@pytest.mark.parametrize("role", DENIED)
def test_add_sections_denied(role_clients, admin, cleanup, pool, role):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    response = role_clients[role].post(f"{BASE}/{cls['id']}/sections", json=[{"name": "Q"}])
    assert response.status_code == 403
    assert section_names(admin.get(f"{BASE}/by_class_id/{cls['id']}").json()) == ["A", "B"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A19")
@pytest.mark.parametrize("role", ROLES)
def test_get_section_read_matrix(role_clients, admin, cleanup, pool, role):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    assert role_clients[role].get(f"{BASE}/sections/{cls['sections'][0]['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A20")
@pytest.mark.parametrize("role", DENIED)
def test_section_update_delete_denied(role_clients, admin, cleanup, pool, role):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    sid = cls["sections"][0]["id"]
    client = role_clients[role]
    assert client.put(f"{BASE}/sections/{sid}", json={"id": None, "name": "Q"}).status_code == 403
    assert client.delete(f"{BASE}/sections/{sid}").status_code == 403
    assert admin.get(f"{BASE}/sections/{sid}").json()["name"] == cls["sections"][0]["name"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A21")
def test_section_endpoints_need_authentication(anon):
    assert anon.post(f"{BASE}/{RANDOM_ID}/sections", json=[{"name": "A"}]).status_code == 401
    assert anon.get(f"{BASE}/sections/{RANDOM_ID}").status_code == 401
    assert anon.put(f"{BASE}/sections/{RANDOM_ID}", json={"id": None}).status_code == 401
    assert anon.delete(f"{BASE}/sections/{RANDOM_ID}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-05-A22")
def test_section_tenant_isolation(admin, tenant_b, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    sid = cls["sections"][0]["id"]
    assert tenant_b.get(f"{BASE}/sections/{sid}").status_code == 404
    assert tenant_b.put(f"{BASE}/sections/{sid}", json={"id": None, "name": "Q"}).status_code == 404
    assert tenant_b.delete(f"{BASE}/sections/{sid}").status_code == 404
    assert tenant_b.post(f"{BASE}/{cls['id']}/sections", json=[{"name": "Q"}]).status_code == 404
    assert admin.get(f"{BASE}/sections/{sid}").json()["name"] == cls["sections"][0]["name"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A01")
def test_class_dropdown_only_active(admin, cleanup, pool):
    active = make_class(admin, cleanup, pool["year"]["id"], sections=None)
    inactive = make_class(admin, cleanup, pool["year"]["id"], sections=None, is_active=False)
    default = admin.get(f"{BASE}/dropdown")
    assert default.status_code == 200
    rows = default.json()
    assert active["id"] in [r["id"] for r in rows]
    assert inactive["id"] not in [r["id"] for r in rows]
    assert all(set(r) == {"id", "name"} for r in rows)
    names = [r["name"] for r in rows]
    assert names == sorted(names)


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A02")
def test_class_dropdown_active_only_false(admin, cleanup, pool):
    inactive = make_class(admin, cleanup, pool["year"]["id"], sections=None, is_active=False)
    rows = admin.get(f"{BASE}/dropdown?active_only=false").json()
    assert inactive["id"] in [r["id"] for r in rows]


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A03")
def test_sections_dropdown_only_active_sections(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    b = next(s for s in cls["sections"] if s["name"] == "B")
    assert admin.put(f"{BASE}/sections/{b['id']}", json={"id": None, "is_active": False}).status_code == 200
    response = admin.get(f"{BASE}/by_class_id/{cls['id']}/sections")
    assert response.status_code == 200
    assert response.json() == [{"id": next(s["id"] for s in cls["sections"] if s["name"] == "A"), "name": "A"}]


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A04")
def test_sections_dropdown_unknown_class_is_empty(admin):
    response = admin.get(f"{BASE}/by_class_id/{RANDOM_ID}/sections")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A05")
def test_class_list_includes_inactive(admin, cleanup, pool):
    inactive = make_class(admin, cleanup, pool["year"]["id"], sections=None, is_active=False)
    response = admin.get(f"{BASE}/class-list")
    assert response.status_code == 200
    row = next(r for r in response.json() if r["id"] == inactive["id"])
    assert {"id", "name", "short_code", "is_active", "academic_year_id", "created_at", "updated_at"} <= set(row)
    assert row["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A06")
def test_section_list(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    response = admin.get(f"{BASE}/section-list")
    assert response.status_code == 200
    mine = [r for r in response.json() if r["class_id"] == cls["id"]]
    assert sorted(r["name"] for r in mine) == ["A", "B"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A07")
def test_class_section_list_labels(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    response = admin.get(f"{BASE}/class-section-list")
    assert response.status_code == 200
    labels = {r["section_id"]: r["class_section_name"] for r in response.json()}
    for section in cls["sections"]:
        assert labels[section["id"]] == f"{cls['name']} - {section['name']}"


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A08")
def test_sections_by_class_name(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    ok = admin.get(f"{BASE}/sections-by-class-name", params={"class_name": cls["name"]})
    assert ok.status_code == 200
    assert sorted(r["name"] for r in ok.json()) == ["A", "B"]
    missing = admin.get(f"{BASE}/sections-by-class-name", params={"class_name": unique("nope")})
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Class not found"
    assert admin.get(f"{BASE}/sections-by-class-name").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A09")
def test_students_by_class_section(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    params = {"class_name": cls["name"], "section_name": "A"}
    ok = admin.get(f"{BASE}/by-class-section", params=params)
    assert ok.status_code == 200
    assert isinstance(ok.json(), list)
    unknown_class = admin.get(f"{BASE}/by-class-section", params={"class_name": unique("nope"), "section_name": "A"})
    assert unknown_class.status_code == 404
    assert unknown_class.json()["detail"] == "Class not found"
    unknown_section = admin.get(f"{BASE}/by-class-section", params={"class_name": cls["name"], "section_name": "ZZ"})
    assert unknown_section.status_code == 404
    assert unknown_section.json()["detail"] == "Section not found for given class"


LOOKUP_PATHS = [
    "/dropdown",
    "/class-list",
    "/section-list",
    "/class-section-list",
    "/by_class_id/{cid}/sections",
    "/sections-by-class-name?class_name={cname}",
    "/by-class-section?class_name={cname}&section_name=A",
]


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A10")
@pytest.mark.parametrize("role", ROLES)
def test_lookup_read_matrix(role_clients, admin, cleanup, pool, role):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    for template in LOOKUP_PATHS:
        path = template.format(cid=cls["id"], cname=cls["name"])
        response = role_clients[role].get(f"{BASE}{path}")
        assert response.status_code == 200, (role, path, response.text)


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A11")
def test_lookups_need_authentication(anon):
    for template in LOOKUP_PATHS:
        path = template.format(cid=RANDOM_ID, cname="x")
        assert anon.get(f"{BASE}{path}").status_code == 401, path


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A12")
def test_lookups_tenant_isolation(admin, tenant_b, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"])
    section_ids = {s["id"] for s in cls["sections"]}
    assert cls["id"] not in [r["id"] for r in tenant_b.get(f"{BASE}/dropdown?active_only=false").json()]
    assert cls["id"] not in [r["id"] for r in tenant_b.get(f"{BASE}/class-list").json()]
    assert not section_ids & {r["id"] for r in tenant_b.get(f"{BASE}/section-list").json()}
    assert not section_ids & {r["section_id"] for r in tenant_b.get(f"{BASE}/class-section-list").json()}


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A13")
def test_create_invalidates_class_lookups(admin, cleanup, pool):
    admin.get(f"{BASE}/dropdown")
    admin.get(f"{BASE}/class-list")
    cls = make_class(admin, cleanup, pool["year"]["id"])
    assert cls["id"] in [r["id"] for r in admin.get(f"{BASE}/dropdown").json()]
    assert cls["id"] in [r["id"] for r in admin.get(f"{BASE}/class-list").json()]


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A14")
def test_section_rename_reflected_in_dropdown(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=("A",))
    sid = cls["sections"][0]["id"]
    before = admin.get(f"{BASE}/by_class_id/{cls['id']}/sections").json()
    assert [r["name"] for r in before] == ["A"]
    assert admin.put(f"{BASE}/sections/{sid}", json={"id": None, "name": "A9"}).status_code == 200
    after = admin.get(f"{BASE}/by_class_id/{cls['id']}/sections").json()
    assert [r["name"] for r in after] == ["A9"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-06-A15")
@pytest.mark.skip(reason="The test API runs with rate limiting disabled, so the 429 cannot be produced")
def test_dropdown_rate_limit():
    pass
