import uuid

import pytest

from api_tests.fee import helpers as h
from api_tests.support import items_of

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
P = "/fee/student-mappings"


def rid():
    return str(uuid.uuid4())


def sm_body(year_id, student, type_id, total="12000.00", **over):
    body = {
        "student_id": student["id"],
        "student_admission_num": student["admission_number"],
        "class_id": student["class_id"],
        "section_id": student["section_id"],
        "fee_type_id": type_id,
        "total_fee": total,
        "academic_year_id": year_id,
    }
    body.update(over)
    return body


def bulk_body(year_id, students, type_id, total="5000.00", **over):
    s0 = students[0]
    body = {
        "student_ids": [s["id"] if isinstance(s, dict) else s for s in students],
        "class_id": s0["class_id"],
        "section_id": s0["section_id"],
        "fee_type_id": type_id,
        "total_fee": total,
        "academic_year_id": year_id,
    }
    body.update(over)
    return body


@pytest.fixture
def own_type(admin, cleanup, year_id, fee_world):
    return h.make_type(admin, cleanup, year_id, fee_world["category"]["id"], fee_world["q4"]["id"])


def clean_bulk(admin, cleanup, data):
    for m in data.get("created_mappings", []):
        cleanup.delete_later(admin, f"{P}/{m['id']}")


@pytest.mark.tc("TC-FEE-06-A01")
def test_student_mapping_create_q4(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    r = h.ok(admin.post(f"{P}/", json=sm_body(year_id, s, fee_world["tuition"]["id"])), 201)
    data = r.json()
    cleanup.delete_later(admin, f"{P}/{data['id']}")
    assert data["total_fee"] == "12000.00"
    terms = data["student_fee_mapping_terms"]
    assert [t["term_amount"] for t in terms] == ["3000.00"] * 4
    assert sorted(t["term_date_id"] for t in terms) == sorted(d["id"] for d in fee_world["q4_dates"])
    assert {t["term_name"] for t in terms} == {fee_world["q4"]["term_name"]}
    assert data["student_details"]["student_id"] == s["id"]
    assert data["fee_type_name"] == fee_world["tuition"]["type_name"]


@pytest.mark.tc("TC-FEE-06-A01")
@pytest.mark.xfail(strict=True, reason="FEE-B07: student fee mapping term amounts always carry term_date null (POST and GET), although the schema field exists for the UI")
def test_student_mapping_terms_carry_term_date(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    r = h.ok(admin.post(f"{P}/", json=sm_body(year_id, s, fee_world["tuition"]["id"])), 201)
    cleanup.delete_later(admin, f"{P}/{r.json()['id']}")
    assert sorted(t["term_date"] for t in r.json()["student_fee_mapping_terms"]) == h.Q4_DATES


@pytest.mark.tc("TC-FEE-06-A02")
def test_student_mapping_create_t3_uneven(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    r = h.ok(admin.post(f"{P}/", json=sm_body(year_id, s, fee_world["lab"]["id"], "1000.00")), 201)
    cleanup.delete_later(admin, f"{P}/{r.json()['id']}")
    assert [t["term_amount"] for t in r.json()["student_fee_mapping_terms"]] == ["333.33"] * 3


@pytest.mark.tc("TC-FEE-06-A03")
def test_student_mapping_duplicate(admin, w1, year_id):
    r = admin.post(f"{P}/", json=sm_body(year_id, w1["student"], w1["tuition"]["id"]))
    assert r.status_code == 400
    assert "Fee student mapping already exists for this combination of student, fee type, and academic year" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-06-A04")
def test_student_mapping_unknown_admission_number(admin, year_id, fee_world, new_student):
    s = new_student()
    r = admin.post(f"{P}/", json=sm_body(year_id, s, fee_world["tuition"]["id"], student_admission_num="NOPE-" + rid()[:8]))
    assert r.status_code == 404
    assert "Admission with number" in h.detail_text(r) and "not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-06-A05")
@pytest.mark.parametrize(
    "field,message", [("student_id", "Student"), ("class_id", "Class"), ("section_id", "Section"), ("fee_type_id", "Fee type"), ("academic_year_id", "Academic year")]
)
def test_student_mapping_unknown_references(field, message, admin, year_id, fee_world, new_student):
    s = new_student()
    body = sm_body(year_id, s, fee_world["tuition"]["id"], **{field: rid()})
    r = admin.post(f"{P}/", json=body)
    assert r.status_code == 404, r.text
    assert message in h.detail_text(r)


@pytest.mark.tc("TC-FEE-06-A06")
def test_student_mapping_negative_fee(admin, year_id, fee_world, new_student):
    s = new_student()
    assert admin.post(f"{P}/", json=sm_body(year_id, s, fee_world["tuition"]["id"], "-1")).status_code == 422


@pytest.mark.tc("TC-FEE-06-A07")
def test_student_mapping_zero_fee(admin, cleanup, year_id, fee_world, new_student):
    s = new_student()
    r = h.ok(admin.post(f"{P}/", json=sm_body(year_id, s, fee_world["tuition"]["id"], "0")), 201)
    cleanup.delete_later(admin, f"{P}/{r.json()['id']}")
    assert all(h.D(t["term_amount"]) == 0 for t in r.json()["student_fee_mapping_terms"])
    assert len(r.json()["student_fee_mapping_terms"]) == 4
    got = h.ok(admin.get(f"{P}/{r.json()['id']}")).json()
    assert [t["term_amount"] for t in got["student_fee_mapping_terms"]] == ["0.00"] * 4


@pytest.mark.tc("TC-FEE-06-A08")
def test_student_mapping_bulk_with_duplicate(admin, cleanup, year_id, own_type, new_student):
    students = [new_student() for _ in range(3)]
    h.map_student(admin, cleanup, year_id, students[0], own_type["id"], "5000.00")
    r = h.ok(admin.post(f"{P}/bulk", json=bulk_body(year_id, students, own_type["id"])), 201)
    data = r.json()
    clean_bulk(admin, cleanup, data)
    assert data["success_count"] == 2 and data["total_count"] == 3
    assert [(e["student_id"], e["error_code"]) for e in data["errors"]] == [(students[0]["id"], "DUPLICATE_MAPPING")]
    assert data["message"] == "Successfully created 2 out of 3 fee student mappings. 1 failed."


@pytest.mark.tc("TC-FEE-06-A09")
def test_student_mapping_bulk_unknown_student(admin, cleanup, year_id, own_type, new_student):
    s = new_student()
    ghost = rid()
    r = h.ok(admin.post(f"{P}/bulk", json=bulk_body(year_id, [s, ghost], own_type["id"])), 201)
    data = r.json()
    clean_bulk(admin, cleanup, data)
    assert data["success_count"] == 1
    assert [(e["student_id"], e["error_code"]) for e in data["errors"]] == [(ghost, "STUDENT_NOT_FOUND")]


@pytest.mark.tc("TC-FEE-06-A10")
def test_student_mapping_bulk_all_fail(admin, cleanup, year_id, own_type, new_student):
    s = new_student()
    h.map_student(admin, cleanup, year_id, s, own_type["id"], "5000.00")
    r = h.ok(admin.post(f"{P}/bulk", json=bulk_body(year_id, [s], own_type["id"])), 201)
    data = r.json()
    assert data["success_count"] == 0
    assert data["message"] == "Failed to create any fee student mappings. All 1 attempts failed."


@pytest.mark.tc("TC-FEE-06-A11")
@pytest.mark.parametrize("field", ["class_id", "section_id", "fee_type_id", "academic_year_id"])
def test_student_mapping_bulk_unknown_reference(field, admin, cleanup, year_id, own_type, new_student):
    s = new_student()
    r = admin.post(f"{P}/bulk", json=bulk_body(year_id, [s], own_type["id"], **{field: rid()}))
    assert r.status_code == 404, r.text
    assert items_of(admin.get(f"{P}/", params={"student_id": s["id"]})) == []


@pytest.mark.tc("TC-FEE-06-A11")
def test_student_mapping_bulk_validators(admin, year_id, own_type, new_student):
    s = new_student()
    assert admin.post(f"{P}/bulk", json=bulk_body(year_id, [s, s], own_type["id"])).status_code == 422
    body = bulk_body(year_id, [s], own_type["id"])
    body["student_ids"] = []
    assert admin.post(f"{P}/bulk", json=body).status_code == 422


@pytest.mark.tc("TC-FEE-06-A12")
def test_student_mapping_list_light_rows(admin, w1, year_id):
    rows = items_of(h.ok(admin.get(f"{P}/", params={"student_id": w1["student"]["id"], "academic_year_id": year_id})))
    assert len(rows) == 1
    assert rows[0]["student_details"] is None
    assert rows[0]["student_fee_mapping_terms"] == []
    assert rows[0]["fee_type_id"] == w1["tuition"]["id"]
    assert rows[0]["fee_type_name"] is None and rows[0]["academic_year_name"] is None
    assert rows[0]["total_fee"] == "12000.00"


@pytest.mark.tc("TC-FEE-06-A13")
def test_student_mapping_get_full(admin, w1):
    data = h.ok(admin.get(f"{P}/{w1['mapping']['id']}")).json()
    details = data["student_details"]
    assert details["student_id"] == w1["student"]["id"]
    assert details["student_class"]["id"] == w1["student"]["class_id"]
    assert details["student_section"]["id"] == w1["student"]["section_id"]
    assert len(data["student_fee_mapping_terms"]) == 4


@pytest.mark.tc("TC-FEE-06-A14")
def test_student_mapping_put_total_rebuilds_terms(admin, w1):
    r = h.ok(admin.put(f"{P}/{w1['mapping']['id']}", json={"total_fee": "6000.00"}))
    assert r.json()["total_fee"] == "6000.00"
    got = h.ok(admin.get(f"{P}/{w1['mapping']['id']}")).json()
    assert got["total_fee"] == "6000.00"
    assert [t["term_amount"] for t in got["student_fee_mapping_terms"]] == ["1500.00"] * 4


@pytest.mark.tc("TC-FEE-06-A15")
def test_student_mapping_put_duplicate_type(admin, cleanup, year_id, w1, own_type):
    h.map_student(admin, cleanup, year_id, w1["student"], own_type["id"], "1000.00")
    r = admin.put(f"{P}/{w1['mapping']['id']}", json={"fee_type_id": own_type["id"]})
    assert r.status_code == 400
    assert "already exists" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-06-A16")
def test_student_mapping_delete_removes_from_summary(admin, year_id, fee_world, new_student):
    s = new_student()
    m = h.ok(admin.post(f"{P}/", json=sm_body(year_id, s, fee_world["tuition"]["id"])), 201).json()
    assert len(h.ok(h.summary(admin, s, year_id)).json()["items"]) == 1
    h.ok(admin.delete(f"{P}/{m['id']}"))
    assert h.ok(h.summary(admin, s, year_id)).json()["items"] == []
    assert items_of(admin.get(f"{P}/", params={"student_id": s["id"]})) == []


@pytest.mark.tc("TC-FEE-06-A16")
@pytest.mark.xfail(strict=True, reason="FEE-B05: GET /fee/student-mappings/{deleted or unknown id} returns 500 instead of 404")
def test_student_mapping_get_unknown(admin):
    assert admin.get(f"{P}/{rid()}").status_code == 404


@pytest.mark.tc("TC-FEE-06-A17")
def test_student_mapping_delete_with_concession_fails(admin, w1, year_id):
    h.ok(
        admin.post(
            "/fee/concessions/bulk",
            json={
                "student_id": w1["student"]["id"],
                "academic_year_id": year_id,
                "concessions": [
                    {"fee_type_id": w1["tuition"]["id"], "concession_amount": "500.00", "reason": "Merit award", "approved_by": "owner"}
                ],
            },
        )
    )
    r = admin.delete(f"{P}/{w1['mapping']['id']}")
    assert r.status_code == 500
    assert len(items_of(admin.get(f"{P}/", params={"student_id": w1["student"]["id"]}))) == 1


@pytest.mark.tc("TC-FEE-06-A18")
def test_student_mapping_delete_after_payment(admin, year_id, fee_world, new_student):
    s = new_student()
    m = h.ok(admin.post(f"{P}/", json=sm_body(year_id, s, fee_world["tuition"]["id"])), 201).json()
    paid = h.ok(h.pay(admin, s, year_id, "3000.00", [(fee_world["tuition"]["id"], "3000.00")])).json()
    h.ok(admin.delete(f"{P}/{m['id']}"))
    txn = h.ok(admin.get(f"/fee/transactions/{paid['transaction_id']}")).json()
    assert txn["status"] == "completed"
    assert h.ok(h.summary(admin, s, year_id)).json()["items"] == []


@pytest.mark.tc("TC-FEE-06-A19")
def test_student_mapping_health(admin):
    h.ok(admin.get(f"{P}/health"))


@pytest.mark.tc("TC-FEE-06-A20")
@pytest.mark.parametrize("role", ROLES)
def test_student_mapping_write_matrix(role, role_clients, admin, cleanup, year_id, own_type, new_student):
    client = role_clients[role]
    allowed = role in ("admin", "staff")
    s = new_student()
    r = client.post(f"{P}/", json=sm_body(year_id, s, own_type["id"]))
    if allowed:
        h.ok(r, 201)
        cleanup.delete_later(admin, f"{P}/{r.json()['id']}")
        mid = r.json()["id"]
    else:
        assert r.status_code == 403
        mid = h.map_student(admin, cleanup, year_id, s, own_type["id"])["id"]
    r = client.put(f"{P}/{mid}", json={"total_fee": "11000.00"})
    assert r.status_code == (200 if allowed else 403)
    others = [new_student(), new_student()]
    r = client.post(f"{P}/bulk", json=bulk_body(year_id, others, own_type["id"]))
    if allowed:
        h.ok(r, 201)
        clean_bulk(admin, cleanup, r.json())
    else:
        assert r.status_code == 403


@pytest.mark.tc("TC-FEE-06-A21")
@pytest.mark.parametrize("role", ROLES)
def test_student_mapping_delete_matrix(role, role_clients, admin, cleanup, year_id, own_type, new_student):
    s = new_student()
    m = h.map_student(admin, cleanup, year_id, s, own_type["id"])
    r = role_clients[role].delete(f"{P}/{m['id']}")
    assert r.status_code == (200 if role == "admin" else 403)


@pytest.mark.tc("TC-FEE-06-A22")
@pytest.mark.parametrize("role", ROLES)
def test_student_mapping_read_matrix(role, role_clients, w1):
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get(f"{P}/", params={"student_id": w1["student"]["id"]}).status_code == expected
    assert client.get(f"{P}/{w1['mapping']['id']}").status_code == expected


@pytest.mark.tc("TC-FEE-06-A23")
def test_student_mapping_no_token_header_isolation(anon, mismatched_admin, tenant_b, w1, year_id, fee_world):
    assert anon.get(f"{P}/").status_code == 401
    assert anon.get(f"{P}/{w1['mapping']['id']}").status_code == 401
    assert anon.post(f"{P}/", json=sm_body(year_id, w1["student"], fee_world["lab"]["id"])).status_code == 401
    assert anon.delete(f"{P}/{w1['mapping']['id']}").status_code == 401
    assert mismatched_admin.get(f"{P}/").status_code == 403
    assert items_of(tenant_b.get(f"{P}/", params={"student_id": w1["student"]["id"]})) == []
    assert tenant_b.get(f"{P}/{w1['mapping']['id']}").status_code in (404, 500)
