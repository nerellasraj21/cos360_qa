import uuid

import pytest

from api_tests.fee import helpers as h
from api_tests.support import items_of, unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api


def rid():
    return str(uuid.uuid4())


def cm_body(year_id, class_id, type_id, total="12000.00", mandatory=False):
    return {
        "class_id": class_id,
        "fee_type_id": type_id,
        "total_fee": total,
        "academic_year_id": year_id,
        "all_by_default": mandatory,
    }


@pytest.fixture
def setup(admin, cleanup, year_id, fee_world):
    cls = h.make_class(admin, cleanup, year_id)
    cat = h.make_category(admin, cleanup, year_id)
    ftype = h.make_type(admin, cleanup, year_id, cat["id"], fee_world["q4"]["id"])
    return {"class": cls, "type": ftype, "q4": fee_world["q4"]}


def student_mappings(admin, student_id, type_id, year_id):
    r = h.ok(
        admin.get(
            "/fee/student-mappings/",
            params={"student_id": student_id, "fee_type_id": type_id, "academic_year_id": year_id},
        )
    )
    return items_of(r)


@pytest.mark.tc("TC-FEE-04-A01")
def test_class_mapping_create(admin, cleanup, year_id, setup):
    r = h.ok(admin.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], setup["type"]["id"])), 201)
    data = r.json()
    cleanup.delete_later(admin, f"/fee/class-mappings/{data['id']}")
    assert data["total_fee"] == "12000.00"
    assert data["all_by_default"] is False
    assert data["class_name"] == setup["class"]["name"]
    assert data["fee_type_name"] == setup["type"]["type_name"]
    assert data["academic_year_name"]
    assert data["class_fee_mapping_terms"] == []


@pytest.mark.tc("TC-FEE-04-A02")
def test_class_mapping_duplicate(admin, cleanup, year_id, setup):
    h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    r = admin.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], setup["type"]["id"]))
    assert r.status_code == 400
    assert "Fee class mapping already exists for this combination of class, fee type, and academic year" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-04-A03")
def test_class_mapping_zero_fee(admin, cleanup, year_id, setup):
    r = h.ok(admin.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], setup["type"]["id"], "0")), 201)
    cleanup.delete_later(admin, f"/fee/class-mappings/{r.json()['id']}")
    assert h.D(r.json()["total_fee"]) == 0
    assert h.ok(admin.get(f"/fee/class-mappings/{r.json()['id']}")).json()["total_fee"] == "0.00"


@pytest.mark.tc("TC-FEE-04-A04")
def test_class_mapping_negative_fee(admin, year_id, setup):
    r = admin.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], setup["type"]["id"], "-1"))
    assert r.status_code == 422


@pytest.mark.tc("TC-FEE-04-A05")
def test_class_mapping_unknown_references(admin, year_id, setup):
    r = admin.post("/fee/class-mappings/", json=cm_body(year_id, rid(), setup["type"]["id"]))
    assert r.status_code == 404 and "Class with id" in h.detail_text(r)
    r = admin.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], rid()))
    assert r.status_code == 404 and "Fee type with id" in h.detail_text(r)
    r = admin.post("/fee/class-mappings/", json=cm_body(rid(), setup["class"]["id"], setup["type"]["id"]))
    assert r.status_code == 404 and "Academic year with id" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-04-A06")
def test_class_mapping_mandatory_maps_students(admin, cleanup, year_id, setup):
    s1 = h.make_student(admin, cleanup, year_id, setup["class"])
    s2 = h.make_student(admin, cleanup, year_id, setup["class"])
    r = h.ok(
        admin.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], setup["type"]["id"], mandatory=True)),
        201,
    )
    cleanup.delete_later(admin, f"/fee/class-mappings/{r.json()['id']}")
    for s in (s1, s2):
        rows = student_mappings(admin, s["id"], setup["type"]["id"], year_id)
        assert len(rows) == 1
        cleanup.delete_later(admin, f"/fee/student-mappings/{rows[0]['id']}")
        assert rows[0]["total_fee"] == "12000.00"
        full = h.ok(admin.get(f"/fee/student-mappings/{rows[0]['id']}")).json()
        assert [t["term_amount"] for t in full["student_fee_mapping_terms"]] == ["3000.00"] * 4


@pytest.mark.tc("TC-FEE-04-A07")
def test_class_mapping_toggle_mandatory(admin, cleanup, year_id, setup):
    s1 = h.make_student(admin, cleanup, year_id, setup["class"])
    m = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    assert student_mappings(admin, s1["id"], setup["type"]["id"], year_id) == []
    r = h.ok(admin.patch(f"/fee/class-mappings/{m['id']}/toggle-mandatory"))
    assert r.json()["all_by_default"] is True
    rows = student_mappings(admin, s1["id"], setup["type"]["id"], year_id)
    assert len(rows) == 1
    cleanup.delete_later(admin, f"/fee/student-mappings/{rows[0]['id']}")
    r = h.ok(admin.patch(f"/fee/class-mappings/{m['id']}/toggle-mandatory"))
    assert r.json()["all_by_default"] is False
    assert len(student_mappings(admin, s1["id"], setup["type"]["id"], year_id)) == 1


@pytest.mark.tc("TC-FEE-04-A08")
def test_class_mapping_put_mandatory_idempotent(admin, cleanup, year_id, setup):
    s1 = h.make_student(admin, cleanup, year_id, setup["class"])
    m = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    h.ok(admin.put(f"/fee/class-mappings/{m['id']}", json={"all_by_default": True}))
    rows = student_mappings(admin, s1["id"], setup["type"]["id"], year_id)
    assert len(rows) == 1
    cleanup.delete_later(admin, f"/fee/student-mappings/{rows[0]['id']}")
    h.ok(admin.put(f"/fee/class-mappings/{m['id']}", json={"all_by_default": True}))
    assert len(student_mappings(admin, s1["id"], setup["type"]["id"], year_id)) == 1


@pytest.mark.tc("TC-FEE-04-A09")
def test_class_mapping_total_change_does_not_propagate(admin, cleanup, year_id, setup):
    s1 = h.make_student(admin, cleanup, year_id, setup["class"])
    m = h.ok(
        admin.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], setup["type"]["id"], mandatory=True)),
        201,
    ).json()
    cleanup.delete_later(admin, f"/fee/class-mappings/{m['id']}")
    rows = student_mappings(admin, s1["id"], setup["type"]["id"], year_id)
    cleanup.delete_later(admin, f"/fee/student-mappings/{rows[0]['id']}")
    r = h.ok(admin.put(f"/fee/class-mappings/{m['id']}", json={"total_fee": "13000.00"}))
    assert r.json()["total_fee"] == "13000.00"
    assert student_mappings(admin, s1["id"], setup["type"]["id"], year_id)[0]["total_fee"] == "12000.00"


@pytest.mark.tc("TC-FEE-04-A10")
def test_class_mapping_put_fee_type(admin, cleanup, year_id, setup, fee_world):
    m = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    other = h.make_type(admin, cleanup, year_id, fee_world["category"]["id"], fee_world["q4"]["id"])
    r = h.ok(admin.put(f"/fee/class-mappings/{m['id']}", json={"fee_type_id": other["id"]}))
    assert r.json()["fee_type_id"] == other["id"]


@pytest.mark.tc("TC-FEE-04-A11")
def test_class_mapping_put_class_uuid(admin, cleanup, year_id, setup):
    m = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    other = h.make_class(admin, cleanup, year_id)
    r = h.ok(admin.put(f"/fee/class-mappings/{m['id']}", json={"class_id": other["id"]}))
    assert r.json()["class_id"] == other["id"]


@pytest.mark.tc("TC-FEE-04-A12")
def test_class_mapping_bulk_with_duplicate(admin, cleanup, year_id, setup):
    classes = [setup["class"]] + [h.make_class(admin, cleanup, year_id) for _ in range(2)]
    h.make_class_mapping(admin, cleanup, year_id, classes[0]["id"], setup["type"]["id"])
    body = {
        "class_ids": [c["id"] for c in classes],
        "fee_type_id": setup["type"]["id"],
        "total_fee": "5000.00",
        "academic_year_id": year_id,
        "all_by_default": False,
    }
    r = h.ok(admin.post("/fee/class-mappings/bulk", json=body), 201)
    data = r.json()
    for m in data["created_mappings"]:
        cleanup.delete_later(admin, f"/fee/class-mappings/{m['id']}")
    assert data["success_count"] == 2 and data["total_count"] == 3
    assert len(data["errors"]) == 1
    assert data["errors"][0]["error_code"] == "DUPLICATE_MAPPING"
    assert data["errors"][0]["class_id"] == classes[0]["id"]
    assert data["message"] == "Successfully created 2 out of 3 fee class mappings. 1 failed."


@pytest.mark.tc("TC-FEE-04-A13")
def test_class_mapping_bulk_unknown_class(admin, cleanup, year_id, setup):
    ghost = rid()
    body = {
        "class_ids": [setup["class"]["id"], ghost],
        "fee_type_id": setup["type"]["id"],
        "total_fee": "5000.00",
        "academic_year_id": year_id,
        "all_by_default": False,
    }
    r = h.ok(admin.post("/fee/class-mappings/bulk", json=body), 201)
    data = r.json()
    for m in data["created_mappings"]:
        cleanup.delete_later(admin, f"/fee/class-mappings/{m['id']}")
    assert data["success_count"] == 1
    assert [(e["class_id"], e["error_code"]) for e in data["errors"]] == [(ghost, "CLASS_NOT_FOUND")]


@pytest.mark.tc("TC-FEE-04-A14")
def test_class_mapping_bulk_unknown_fee_type(admin, year_id, setup):
    body = {
        "class_ids": [setup["class"]["id"]],
        "fee_type_id": rid(),
        "total_fee": "5000.00",
        "academic_year_id": year_id,
        "all_by_default": False,
    }
    r = admin.post("/fee/class-mappings/bulk", json=body)
    assert r.status_code == 404
    assert "Fee type with id" in h.detail_text(r)
    got = items_of(admin.get("/fee/class-mappings/", params={"class_id": setup["class"]["id"]}))
    assert got == []


@pytest.mark.tc("TC-FEE-04-A15")
def test_class_mapping_list_filters(admin, cleanup, year_id, setup, fee_world):
    other_type = h.make_type(admin, cleanup, year_id, fee_world["category"]["id"], fee_world["q4"]["id"])
    m1 = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    m2 = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], other_type["id"], mandatory=True)
    rows = items_of(admin.get("/fee/class-mappings/", params={"class_id": setup["class"]["id"]}))
    assert {r["id"] for r in rows} == {m1["id"], m2["id"]}
    assert all("class_fee_mapping_terms" in r for r in rows)
    mandatory = items_of(admin.get("/fee/class-mappings/", params={"class_id": setup["class"]["id"], "all_by_default": "true"}))
    assert [r["id"] for r in mandatory] == [m2["id"]]
    page = items_of(admin.get("/fee/class-mappings/", params={"class_id": setup["class"]["id"], "limit": 1, "offset": 0}))
    assert len(page) == 1
    page2 = items_of(admin.get("/fee/class-mappings/", params={"class_id": setup["class"]["id"], "limit": 1, "offset": 1}))
    assert len(page2) == 1 and page2[0]["id"] != page[0]["id"]


@pytest.mark.tc("TC-FEE-04-A16")
def test_class_mapping_filter_by_fee_type(admin, cleanup, year_id, setup):
    m = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    rows = items_of(h.ok(admin.get("/fee/class-mappings/", params={"fee_type_id": setup["type"]["id"]})))
    assert [r["id"] for r in rows] == [m["id"]]


@pytest.mark.tc("TC-FEE-04-A17")
def test_class_mapping_get(admin, cleanup, year_id, setup):
    m = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    assert h.ok(admin.get(f"/fee/class-mappings/{m['id']}")).json()["id"] == m["id"]


@pytest.mark.tc("TC-FEE-04-A17")
@pytest.mark.xfail(strict=True, reason="FEE-B04: GET /fee/class-mappings/{unknown id} returns 500 because the service swallows its own 404")
def test_class_mapping_get_unknown(admin):
    missing = rid()
    r = admin.get(f"/fee/class-mappings/{missing}")
    assert r.status_code == 404
    assert f"Fee class mapping with id {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-04-A18")
def test_class_mapping_delete_keeps_student_mappings(admin, cleanup, year_id, setup):
    s1 = h.make_student(admin, cleanup, year_id, setup["class"])
    m = h.ok(
        admin.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], setup["type"]["id"], mandatory=True)),
        201,
    ).json()
    rows = student_mappings(admin, s1["id"], setup["type"]["id"], year_id)
    cleanup.delete_later(admin, f"/fee/student-mappings/{rows[0]['id']}")
    h.ok(admin.delete(f"/fee/class-mappings/{m['id']}"))
    assert items_of(admin.get("/fee/class-mappings/", params={"class_id": setup["class"]["id"]})) == []
    assert len(student_mappings(admin, s1["id"], setup["type"]["id"], year_id)) == 1


@pytest.mark.tc("TC-FEE-04-A19")
def test_class_mapping_health(admin):
    assert h.ok(admin.get("/fee/class-mappings/health")).json()["module"] == "fee_class_mappings"


@pytest.mark.tc("TC-FEE-04-A20")
@pytest.mark.parametrize("role", ROLES)
def test_class_mapping_write_matrix(role, role_clients, admin, cleanup, year_id, setup, fee_world):
    client = role_clients[role]
    allowed = role == "admin"
    r = client.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], setup["type"]["id"]))
    if allowed:
        h.ok(r, 201)
        cleanup.delete_later(admin, f"/fee/class-mappings/{r.json()['id']}")
        m = r.json()
    else:
        assert r.status_code == 403
        m = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    r = client.put(f"/fee/class-mappings/{m['id']}", json={"total_fee": "12500.00"})
    assert r.status_code == (200 if allowed else 403)
    r = client.patch(f"/fee/class-mappings/{m['id']}/toggle-mandatory")
    assert r.status_code == (200 if allowed else 403)
    if allowed:
        admin.patch(f"/fee/class-mappings/{m['id']}/toggle-mandatory")
    other = h.make_class(admin, cleanup, year_id)
    body = {
        "class_ids": [other["id"]],
        "fee_type_id": setup["type"]["id"],
        "total_fee": "100.00",
        "academic_year_id": year_id,
        "all_by_default": False,
    }
    r = client.post("/fee/class-mappings/bulk", json=body)
    if allowed:
        h.ok(r, 201)
        for c in r.json()["created_mappings"]:
            cleanup.delete_later(admin, f"/fee/class-mappings/{c['id']}")
    else:
        assert r.status_code == 403
    victim = h.make_class_mapping(admin, cleanup, year_id, other["id"], setup["type"]["id"]) if not allowed else m
    r = client.delete(f"/fee/class-mappings/{victim['id']}")
    assert r.status_code == (200 if allowed else 403)


@pytest.mark.tc("TC-FEE-04-A21")
@pytest.mark.parametrize("role", ROLES)
def test_class_mapping_read_matrix(role, role_clients, admin, cleanup, year_id, setup):
    m = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get("/fee/class-mappings/").status_code == expected
    assert client.get(f"/fee/class-mappings/{m['id']}").status_code == expected


@pytest.mark.tc("TC-FEE-04-A22")
def test_class_mapping_no_token_header_and_isolation(anon, mismatched_admin, tenant_b, admin, cleanup, year_id, setup):
    m = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    assert anon.get("/fee/class-mappings/").status_code == 401
    assert anon.get(f"/fee/class-mappings/{m['id']}").status_code == 401
    assert anon.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], setup["type"]["id"])).status_code == 401
    assert mismatched_admin.get("/fee/class-mappings/").status_code == 403
    assert items_of(tenant_b.get("/fee/class-mappings/", params={"class_id": setup["class"]["id"]})) == []
    assert tenant_b.get(f"/fee/class-mappings/{m['id']}").status_code in (404, 500)


@pytest.mark.tc("TC-FEE-04-A22")
@pytest.mark.xfail(strict=True, reason="FEE-B04: cross-tenant GET /fee/class-mappings/{id} returns 500 instead of 404")
def test_class_mapping_cross_tenant_get_is_404(tenant_b, admin, cleanup, year_id, setup):
    m = h.make_class_mapping(admin, cleanup, year_id, setup["class"]["id"], setup["type"]["id"])
    assert tenant_b.get(f"/fee/class-mappings/{m['id']}").status_code == 404


@pytest.mark.tc("TC-FEE-04-A23")
def test_admission_after_mandatory_mapping_gets_fee(admin, cleanup, year_id, setup):
    m = h.ok(
        admin.post("/fee/class-mappings/", json=cm_body(year_id, setup["class"]["id"], setup["type"]["id"], mandatory=True)),
        201,
    ).json()
    cleanup.delete_later(admin, f"/fee/class-mappings/{m['id']}")
    student = h.make_student(admin, cleanup, year_id, setup["class"])
    rows = student_mappings(admin, student["id"], setup["type"]["id"], year_id)
    assert len(rows) == 1
    cleanup.delete_later(admin, f"/fee/student-mappings/{rows[0]['id']}")
    full = h.ok(admin.get(f"/fee/student-mappings/{rows[0]['id']}")).json()
    assert full["total_fee"] == "12000.00"
    assert [t["term_amount"] for t in full["student_fee_mapping_terms"]] == ["3000.00"] * 4
