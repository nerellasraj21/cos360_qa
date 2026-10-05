import uuid

import pytest

from api_tests.fee import helpers as h
from api_tests.support import items_of, unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api


def rid():
    return str(uuid.uuid4())


def term_body(year_id, dates=None, number=None, name=None, **extra):
    dates = h.Q4_DATES if dates is None else dates
    return {
        "term_name": name or unique("fee_term_"),
        "term_status": "active",
        "number_of_terms": len(dates) if number is None else number,
        "academic_year_id": year_id,
        "fee_term_dates": [{"fee_term_date": d} for d in dates],
        **extra,
    }


@pytest.fixture
def term(admin, cleanup, year_id):
    return h.make_term(admin, cleanup, year_id)


@pytest.mark.tc("TC-FEE-03-A01")
def test_term_create(admin, cleanup, year_id):
    body = term_body(year_id)
    r = h.ok(admin.post("/fee/terms/", json=body), 201)
    data = r.json()
    cleanup.delete_later(admin, f"/fee/terms/{data['id']}")
    assert data["number_of_terms"] == 4
    assert data["term_status"] == "active"
    assert [d["fee_term_date"] for d in data["fee_term_dates"]] == h.Q4_DATES
    assert all(d["id"] and d["term_id"] == data["id"] for d in data["fee_term_dates"])


@pytest.mark.tc("TC-FEE-03-A02")
def test_term_count_mismatch(admin, year_id):
    r = admin.post("/fee/terms/", json=term_body(year_id, h.Q4_DATES[:3], number=4))
    assert r.status_code == 422
    assert "must match number_of_terms" in r.text


@pytest.mark.tc("TC-FEE-03-A03")
def test_term_duplicate_dates(admin, year_id):
    r = admin.post("/fee/terms/", json=term_body(year_id, ["2026-06-10", "2026-06-10"]))
    assert r.status_code == 422
    assert "Duplicate fee term dates are not allowed" in r.text


@pytest.mark.tc("TC-FEE-03-A04")
def test_term_unknown_year(admin):
    r = admin.post("/fee/terms/", json=term_body(rid()))
    assert r.status_code == 404
    assert "Academic year with id" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-03-A05")
def test_term_zero_installments_allowed(admin, cleanup, year_id):
    r = admin.post("/fee/terms/", json=term_body(year_id, [], number=0))
    h.ok(r, 201)
    cleanup.delete_later(admin, f"/fee/terms/{r.json()['id']}")
    assert r.json()["number_of_terms"] == 0 and r.json()["fee_term_dates"] == []


@pytest.mark.tc("TC-FEE-03-A06")
def test_term_list(admin, term):
    r = h.ok(admin.get("/fee/terms/", params={"limit": 500, "offset": 0}))
    data = r.json()
    assert isinstance(data, list)
    mine = [t for t in data if t["id"] == term["id"]]
    assert mine and len(mine[0]["fee_term_dates"]) == 4
    assert len(h.ok(admin.get("/fee/terms/", params={"limit": 1})).json()) == 1


@pytest.mark.tc("TC-FEE-03-A07")
def test_term_dropdown_excludes_inactive(admin, cleanup, year_id, term):
    items = h.ok(admin.get("/fee/terms/dropdown")).json()
    assert all(set(i) == {"id", "term_name", "number_of_terms"} for i in items)
    assert term["id"] in {i["id"] for i in items}
    h.ok(admin.put(f"/fee/terms/{term['id']}", json={"term_status": "inactive"}))
    items = h.ok(admin.get("/fee/terms/dropdown")).json()
    assert term["id"] not in {i["id"] for i in items}


@pytest.mark.tc("TC-FEE-03-A08")
def test_term_get_and_dates(admin, cleanup, year_id):
    shuffled = ["2026-12-10", "2026-06-10", "2027-03-10", "2026-09-10"]
    t = h.make_term(admin, cleanup, year_id, shuffled)
    got = h.ok(admin.get(f"/fee/terms/{t['id']}")).json()
    assert got["id"] == t["id"] and len(got["fee_term_dates"]) == 4
    dates = h.ok(admin.get(f"/fee/terms/{t['id']}/dates")).json()
    assert [d["fee_term_date"] for d in dates] == sorted(shuffled)
    missing = rid()
    r = admin.get(f"/fee/terms/{missing}")
    assert r.status_code == 404
    assert f"Fee term with id {missing} not found" in h.detail_text(r)
    assert admin.get(f"/fee/terms/{missing}/dates").status_code == 404


@pytest.mark.tc("TC-FEE-03-A09")
def test_term_update_dates_in_place(admin, term):
    before = {d["fee_term_date"]: d["id"] for d in term["fee_term_dates"]}
    new_dates = ["2026-07-01", "2026-10-01", "2027-01-01", "2027-04-01"]
    body = {"fee_term_dates": [{"fee_term_date": d} for d in new_dates]}
    h.ok(admin.put(f"/fee/terms/{term['id']}", json=body))
    after = h.ok(admin.get(f"/fee/terms/{term['id']}/dates")).json()
    assert [d["fee_term_date"] for d in after] == new_dates
    assert [d["id"] for d in after] == [before[k] for k in sorted(before)]


@pytest.mark.tc("TC-FEE-03-A10")
def test_term_update_dates_count_mismatch(admin, term):
    body = {"fee_term_dates": [{"fee_term_date": "2026-07-01"}, {"fee_term_date": "2026-10-01"}]}
    r = admin.put(f"/fee/terms/{term['id']}", json=body)
    assert r.status_code == 400
    assert "Number of fee term dates (2) must match number_of_terms (4)" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-03-A11")
def test_term_shrink_with_referenced_date_fails(admin, cleanup, year_id, fee_world):
    cls = h.make_class(admin, cleanup, year_id)
    cat = h.make_category(admin, cleanup, year_id)
    t = h.make_term(admin, cleanup, year_id)
    ftype = h.make_type(admin, cleanup, year_id, cat["id"], t["id"])
    student = h.make_student(admin, cleanup, year_id, cls)
    h.map_student(admin, cleanup, year_id, student, ftype["id"])
    body = {"number_of_terms": 3, "fee_term_dates": [{"fee_term_date": d} for d in h.T3_DATES]}
    r = admin.put(f"/fee/terms/{t['id']}", json=body)
    assert r.status_code == 500
    assert h.ok(admin.get(f"/fee/terms/{t['id']}")).json()["number_of_terms"] == 4
    assert len(admin.get(f"/fee/terms/{t['id']}/dates").json()) == 4


@pytest.mark.tc("TC-FEE-03-A12")
def test_term_set_inactive(admin, term):
    r = h.ok(admin.put(f"/fee/terms/{term['id']}", json={"term_status": "inactive"}))
    assert r.json()["term_status"] == "inactive"
    ids = {i["id"] for i in admin.get("/fee/terms/dropdown").json()}
    assert term["id"] not in ids


@pytest.mark.tc("TC-FEE-03-A13")
def test_term_delete_unused(admin, year_id):
    t = h.ok(admin.post("/fee/terms/", json=term_body(year_id)), 201).json()
    r = h.ok(admin.delete(f"/fee/terms/{t['id']}"))
    assert r.json()["id"] == t["id"]
    assert admin.get(f"/fee/terms/{t['id']}").status_code == 404
    assert admin.get(f"/fee/terms/{t['id']}/dates").status_code == 404


@pytest.mark.tc("TC-FEE-03-A14")
def test_term_delete_used_by_type_blocked(admin, cleanup, year_id, term):
    cat = h.make_category(admin, cleanup, year_id)
    h.make_type(admin, cleanup, year_id, cat["id"], term["id"])
    r = admin.delete(f"/fee/terms/{term['id']}")
    assert r.status_code == 400
    assert f"Cannot delete fee term '{term['term_name']}' because it is being used by 1 fee type(s)" in h.detail_text(r)
    assert admin.get(f"/fee/terms/{term['id']}").status_code == 200


@pytest.mark.tc("TC-FEE-03-A15")
def test_term_delete_single_date(admin, term):
    date_id = term["fee_term_dates"][-1]["id"]
    r = h.ok(admin.delete(f"/fee/terms/dates/{date_id}"))
    assert r.json()["message"] == "Fee term date deleted successfully"
    remaining = {d["id"] for d in admin.get(f"/fee/terms/{term['id']}/dates").json()}
    assert date_id not in remaining
    missing = rid()
    r = admin.delete(f"/fee/terms/dates/{missing}")
    assert r.status_code == 404
    assert f"Fee term date with id {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-03-A16")
def test_term_health(admin):
    assert h.ok(admin.get("/fee/terms/health")).json()["module"] == "fee_terms"


@pytest.mark.tc("TC-FEE-03-A17")
@pytest.mark.parametrize("role", ROLES)
def test_term_write_matrix(role, role_clients, admin, cleanup, year_id, term):
    client = role_clients[role]
    allowed = role == "admin"
    r = client.post("/fee/terms/", json=term_body(year_id))
    if allowed:
        h.ok(r, 201)
        cleanup.delete_later(admin, f"/fee/terms/{r.json()['id']}")
    else:
        assert r.status_code == 403
    r = client.put(f"/fee/terms/{term['id']}", json={"term_status": "active"})
    assert r.status_code == (200 if allowed else 403)
    victim = h.make_term(admin, cleanup, year_id)
    r = client.delete(f"/fee/terms/dates/{victim['fee_term_dates'][0]['id']}")
    assert r.status_code == (200 if allowed else 403)
    r = client.delete(f"/fee/terms/{victim['id']}")
    assert r.status_code == (200 if allowed else 403)
    if not allowed:
        assert admin.get(f"/fee/terms/{victim['id']}").status_code == 200


@pytest.mark.tc("TC-FEE-03-A18")
@pytest.mark.parametrize("role", ROLES)
def test_term_read_matrix(role, role_clients, term):
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get("/fee/terms/").status_code == expected
    assert client.get(f"/fee/terms/{term['id']}").status_code == expected
    assert client.get(f"/fee/terms/{term['id']}/dates").status_code == expected
    assert client.get("/fee/terms/dropdown").status_code == expected


@pytest.mark.tc("TC-FEE-03-A19")
def test_term_no_token_header_mismatch_and_isolation(anon, mismatched_admin, tenant_b, term, year_id):
    assert anon.get("/fee/terms/").status_code == 401
    assert anon.get(f"/fee/terms/{term['id']}").status_code == 401
    assert anon.post("/fee/terms/", json=term_body(year_id)).status_code == 401
    assert anon.delete(f"/fee/terms/{term['id']}").status_code == 401
    assert mismatched_admin.get("/fee/terms/").status_code == 403
    assert tenant_b.get(f"/fee/terms/{term['id']}").status_code == 404
    ids = {t["id"] for t in items_of(tenant_b.get("/fee/terms/", params={"limit": 500}))}
    assert term["id"] not in ids
