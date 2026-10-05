import uuid

import pytest

from api_tests.fee import helpers as h
from api_tests.support import items_of, unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
PREFIX = "/fee/class-mapping-term-amounts"


def rid():
    return str(uuid.uuid4())


@pytest.fixture
def cm(admin, cleanup, year_id, fee_world):
    cls = h.make_class(admin, cleanup, year_id)
    cat = h.make_category(admin, cleanup, year_id)
    q4 = h.make_term(admin, cleanup, year_id)
    ftype = h.make_type(admin, cleanup, year_id, cat["id"], q4["id"])
    mapping = h.make_class_mapping(admin, cleanup, year_id, cls["id"], ftype["id"], "12000.00")
    dates = sorted(q4["fee_term_dates"], key=lambda x: x["fee_term_date"])
    return {"mapping": mapping, "type": ftype, "term": q4, "dates": dates, "class": cls}


def body(cm, amounts=("3000", "3000", "3000", "3000"), dates=None):
    dates = dates or [d["id"] for d in cm["dates"]]
    return {
        "fee_class_mapping_id": cm["mapping"]["id"],
        "term_amounts": [{"term_date_id": d, "term_amount": a} for d, a in zip(dates, amounts)],
    }


def create(admin, cleanup, cm, **kw):
    r = h.ok(admin.post(f"{PREFIX}/", json=body(cm, **kw)), 201)
    ids = [t["id"] for t in r.json()]
    cleanup.add(admin.delete, f"{PREFIX}/", json={"term_amount_ids": ids})
    return r.json()


@pytest.mark.tc("TC-FEE-05-A01")
def test_term_amounts_create(admin, cleanup, cm):
    rows = create(admin, cleanup, cm)
    assert len(rows) == 4
    for row, d in zip(sorted(rows, key=lambda x: x["term_date"]), cm["dates"]):
        assert row["term_date_id"] == d["id"]
        assert row["term_id"] == cm["term"]["id"]
        assert row["term_name"] == cm["term"]["term_name"]
        assert row["term_date"] == d["fee_term_date"]
        assert row["term_amount"] == "3000.00"


@pytest.mark.tc("TC-FEE-05-A02")
def test_term_amounts_sum_mismatch(admin, cm):
    r = admin.post(f"{PREFIX}/", json=body(cm, ("3000", "3000", "3000", "2999")))
    assert r.status_code == 400
    assert "Sum of term amounts (11999" in h.detail_text(r)
    assert "must equal total fee (12000.00)" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-05-A03")
def test_term_amounts_count_mismatch(admin, cm):
    r = admin.post(f"{PREFIX}/", json=body(cm, ("4000", "4000", "4000"), [d["id"] for d in cm["dates"][:3]]))
    assert r.status_code == 400
    assert "Number of term amounts (3) must match number of term dates (4)" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-05-A04")
def test_term_amounts_date_from_other_term(admin, cleanup, year_id, cm):
    other = h.make_term(admin, cleanup, year_id)
    dates = [d["id"] for d in cm["dates"][:3]] + [other["fee_term_dates"][0]["id"]]
    r = admin.post(f"{PREFIX}/", json=body(cm, dates=dates))
    assert r.status_code == 400
    assert "not found or doesn't belong to term" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-05-A05")
def test_term_amounts_duplicate_date(admin, cm):
    first = cm["dates"][0]["id"]
    r = admin.post(f"{PREFIX}/", json=body(cm, dates=[first, first, cm["dates"][2]["id"], cm["dates"][3]["id"]]))
    assert r.status_code == 400
    assert f"Duplicate term_date_id {first} in request" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-05-A06")
def test_term_amounts_already_exist(admin, cleanup, cm):
    create(admin, cleanup, cm)
    r = admin.post(f"{PREFIX}/", json=body(cm))
    assert r.status_code == 400
    assert "Term amount already exists for this fee class mapping and term date combination" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-05-A07")
def test_term_amounts_zero_rejected(admin, cm):
    r = admin.post(f"{PREFIX}/", json=body(cm, ("0", "6000", "3000", "3000")))
    assert r.status_code == 422


@pytest.mark.tc("TC-FEE-05-A08")
def test_term_amounts_unknown_mapping(admin, cm):
    payload = body(cm)
    missing = rid()
    payload["fee_class_mapping_id"] = missing
    r = admin.post(f"{PREFIX}/", json=payload)
    assert r.status_code == 404
    assert f"Fee class mapping with id {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-05-A09")
def test_term_amounts_update(admin, cleanup, cm):
    rows = sorted(create(admin, cleanup, cm), key=lambda x: x["term_date"])
    payload = {
        "fee_class_mapping_id": cm["mapping"]["id"],
        "term_amounts": [
            {"id": row["id"], "term_date_id": row["term_date_id"], "term_amount": a}
            for row, a in zip(rows, ("4000", "4000", "2000", "2000"))
        ],
    }
    r = h.ok(admin.put(f"{PREFIX}/", json=payload))
    got = sorted(r.json(), key=lambda x: x["term_date"])
    assert [t["term_amount"] for t in got] == ["4000.00", "4000.00", "2000.00", "2000.00"]
    assert [t["id"] for t in got] == [row["id"] for row in rows]


@pytest.mark.tc("TC-FEE-05-A10")
def test_term_amounts_update_unknown_id(admin, cleanup, cm):
    rows = sorted(create(admin, cleanup, cm), key=lambda x: x["term_date"])
    missing = rid()
    payload = {
        "fee_class_mapping_id": cm["mapping"]["id"],
        "term_amounts": [{"id": missing, "term_date_id": rows[0]["term_date_id"], "term_amount": "12000"}]
        + [{"id": r_["id"], "term_date_id": r_["term_date_id"], "term_amount": "3000"} for r_ in rows[1:]],
    }
    r = admin.put(f"{PREFIX}/", json=payload)
    assert r.status_code == 404
    assert f"Term amount with id {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-05-A11")
def test_term_amounts_update_without_id_creates(admin, cleanup, cm):
    payload = {
        "fee_class_mapping_id": cm["mapping"]["id"],
        "term_amounts": [{"term_date_id": d["id"], "term_amount": "3000"} for d in cm["dates"]],
    }
    r = h.ok(admin.put(f"{PREFIX}/", json=payload))
    ids = [t["id"] for t in r.json()]
    cleanup.add(admin.delete, f"{PREFIX}/", json={"term_amount_ids": ids})
    assert len(ids) == 4
    listed = h.ok(admin.get(f"{PREFIX}/by-mapping/{cm['mapping']['id']}")).json()
    assert len(listed) == 4


@pytest.mark.tc("TC-FEE-05-A12")
def test_term_amounts_update_requires_term_date_id(admin, cleanup, cm):
    rows = create(admin, cleanup, cm)
    payload = {
        "fee_class_mapping_id": cm["mapping"]["id"],
        "term_amounts": [{"id": rows[0]["id"], "term_id": cm["term"]["id"], "term_amount": "3000"}],
    }
    assert admin.put(f"{PREFIX}/", json=payload).status_code == 422


@pytest.mark.tc("TC-FEE-05-A13")
def test_term_amounts_reads(admin, cleanup, cm):
    rows = create(admin, cleanup, cm)
    by_mapping = h.ok(admin.get(f"{PREFIX}/by-mapping/{cm['mapping']['id']}")).json()
    assert len(by_mapping) == 4
    date_of = {d["id"]: d["fee_term_date"] for d in cm["dates"]}
    got = [date_of[t["term_date_id"]] for t in by_mapping]
    assert got == sorted(got)
    listed = items_of(
        admin.get(f"{PREFIX}/", params={"class_mapping_id": cm["mapping"]["id"], "fee_term_id": cm["term"]["id"]})
    )
    assert {t["id"] for t in listed} == {t["id"] for t in rows}
    assert items_of(admin.get(f"{PREFIX}/", params={"class_mapping_id": cm["mapping"]["id"], "fee_term_id": rid()})) == []
    one = h.ok(admin.get(f"{PREFIX}/{rows[0]['id']}")).json()
    assert one["id"] == rows[0]["id"]
    missing = rid()
    r = admin.get(f"{PREFIX}/{missing}")
    assert r.status_code == 404
    assert f"Term amount with id {missing} not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-05-A14")
def test_term_amounts_delete(admin, cleanup, cm):
    rows = create(admin, cleanup, cm)
    r = h.ok(admin.delete(f"{PREFIX}/", json={"term_amount_ids": [rows[0]["id"], rows[1]["id"]]}))
    assert r.json()["message"] == "Successfully deleted 2 term amount(s)"
    assert len(admin.get(f"{PREFIX}/by-mapping/{cm['mapping']['id']}").json()) == 2


@pytest.mark.tc("TC-FEE-05-A15")
def test_term_amounts_health(admin):
    h.ok(admin.get(f"{PREFIX}/health"))


@pytest.mark.tc("TC-FEE-05-A16")
@pytest.mark.parametrize("role", ROLES)
def test_term_amounts_write_matrix(role, role_clients, admin, cleanup, cm):
    client = role_clients[role]
    allowed = role == "admin"
    r = client.post(f"{PREFIX}/", json=body(cm))
    if allowed:
        h.ok(r, 201)
        rows = r.json()
        cleanup.add(admin.delete, f"{PREFIX}/", json={"term_amount_ids": [t["id"] for t in rows]})
    else:
        assert r.status_code == 403
        rows = create(admin, cleanup, cm)
    payload = {
        "fee_class_mapping_id": cm["mapping"]["id"],
        "term_amounts": [{"id": t["id"], "term_date_id": t["term_date_id"], "term_amount": "3000"} for t in rows],
    }
    r = client.put(f"{PREFIX}/", json=payload)
    assert r.status_code == (200 if allowed else 403)
    r = client.delete(f"{PREFIX}/", json={"term_amount_ids": [rows[0]["id"]]})
    assert r.status_code == (200 if allowed else 403)


@pytest.mark.tc("TC-FEE-05-A17")
@pytest.mark.parametrize("role", ROLES)
def test_term_amounts_read_matrix(role, role_clients, admin, cleanup, cm):
    rows = create(admin, cleanup, cm)
    client = role_clients[role]
    expected = 200 if role in ("admin", "staff") else 403
    assert client.get(f"{PREFIX}/", params={"class_mapping_id": cm["mapping"]["id"]}).status_code == expected
    assert client.get(f"{PREFIX}/{rows[0]['id']}").status_code == expected
    assert client.get(f"{PREFIX}/by-mapping/{cm['mapping']['id']}").status_code == expected


@pytest.mark.tc("TC-FEE-05-A18")
def test_term_amounts_no_token_header_isolation(anon, mismatched_admin, tenant_b, admin, cleanup, cm):
    rows = create(admin, cleanup, cm)
    assert anon.get(f"{PREFIX}/by-mapping/{cm['mapping']['id']}").status_code == 401
    assert anon.post(f"{PREFIX}/", json=body(cm)).status_code == 401
    assert mismatched_admin.get(f"{PREFIX}/by-mapping/{cm['mapping']['id']}").status_code == 403
    assert items_of(tenant_b.get(f"{PREFIX}/by-mapping/{cm['mapping']['id']}")) == []
    assert tenant_b.get(f"{PREFIX}/{rows[0]['id']}").status_code == 404


@pytest.mark.tc("TC-FEE-05-A19")
def test_student_term_amounts_follow_class_template(admin, cleanup, year_id, cm):
    create(admin, cleanup, cm, amounts=("5000", "3000", "2000", "2000"))
    student = h.make_student(admin, cleanup, year_id, cm["class"])
    mapping = h.map_student(admin, cleanup, year_id, student, cm["type"]["id"], "12000.00")
    assert [t["term_amount"] for t in mapping["student_fee_mapping_terms"]] == ["5000.00", "3000.00", "2000.00", "2000.00"]


@pytest.mark.tc("TC-FEE-05-A13")
@pytest.mark.xfail(strict=True, reason="FEE-B06: GET by-mapping, list and single term-amount reads return term_date null (only create/update fill it)")
def test_term_amounts_reads_carry_term_date(admin, cleanup, cm):
    rows = create(admin, cleanup, cm)
    by_mapping = h.ok(admin.get(f"{PREFIX}/by-mapping/{cm['mapping']['id']}")).json()
    assert all(t["term_date"] for t in by_mapping)
    assert h.ok(admin.get(f"{PREFIX}/{rows[0]['id']}")).json()["term_date"]
