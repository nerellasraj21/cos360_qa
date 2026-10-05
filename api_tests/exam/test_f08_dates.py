import pytest

from api_tests.exam.helpers import ALL_ROLES, OTHER_ROLES, create_exam, new_uuid

KG1 = "KG-1: exam date create endpoints read current_user['id'] (absent from real tokens) and return 500"


def date_body(world, exam_id, sub="math", section="a", when="2027-03-01", **extra):
    body = {
        "exam_id": exam_id,
        "class_id": world.class_id,
        "section_id": world.sections[section],
        "subject_id": world.subjects[sub],
        "exam_date": when,
        "start_time": "09:30",
        "end_time": "11:00",
        "venue": "Hall A",
    }
    body.update(extra)
    return body


def dates_of(admin, exam_id):
    response = admin.get(f"/exams/{exam_id}/dates")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def ex_dated(admin, world, cleanup):
    exam_id = create_exam(admin, cleanup, world, dates=True)
    return exam_id


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A01")
def test_create_date(admin, world, cleanup, logins):
    ex1 = {"id": create_exam(admin, cleanup, world)}
    response = admin.post(f"/exams/{ex1['id']}/dates", json=date_body(world, ex1["id"]))
    assert response.status_code == 201, response.text
    assert response.json()["created_by"] == logins["admin"]["user"]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A02")
def test_create_date_requires_exam_id_in_body(admin, world, ex1):
    body = date_body(world, ex1["id"])
    del body["exam_id"]
    assert admin.post(f"/exams/{ex1['id']}/dates", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A03")
def test_duplicate_date_conflicts(admin, world, ex_dated):
    body = date_body(world, ex_dated, sub="math", when="2027-02-01")
    assert admin.post(f"/exams/{ex_dated}/dates", json=body).status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A04")
def test_bulk_create(admin, world, cleanup):
    ex1 = {"id": create_exam(admin, cleanup, world)}
    dates = [date_body(world, ex1["id"], sub=s, when=f"2027-03-0{i + 1}") for i, s in enumerate(("math", "sci", "eng"))]
    response = admin.post(f"/exams/{ex1['id']}/dates/bulk", json={"dates": dates})
    assert response.status_code == 201, response.text
    assert len(response.json()) == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A05")
def test_bulk_with_duplicate_is_atomic(admin, world, ex_dated):
    dates = [date_body(world, ex_dated, sub="math", when="2027-03-09"), date_body(world, ex_dated, sub="sci", when="2027-02-02")]
    before = len(dates_of(admin, ex_dated))
    response = admin.post(f"/exams/{ex_dated}/dates/bulk", json={"dates": dates})
    assert response.status_code == 409
    assert len(dates_of(admin, ex_dated)) == before


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A06")
def test_multi_section_create(admin, world, cleanup):
    ex1 = {"id": create_exam(admin, cleanup, world)}
    body = {
        "exam_id": ex1["id"],
        "subject_id": world.subjects["math"],
        "exam_date": "2027-03-05",
        "start_time": "09:00",
        "end_time": "10:00",
        "venue": "Hall",
        "class_sections": [
            {"class_id": world.class_id, "section_id": world.sections["a"]},
            {"class_id": world.class_id, "section_id": world.sections["b"]},
        ],
    }
    response = admin.post(f"/exams/{ex1['id']}/dates/multi-section", json=body)
    assert response.status_code == 201, response.text
    rows = response.json()
    assert len(rows) == 2
    assert {r["exam_date"] for r in rows} == {"2027-03-05"}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A07")
def test_empty_collections_rejected(admin, world, ex1):
    assert admin.post(f"/exams/{ex1['id']}/dates/bulk", json={"dates": []}).status_code == 422
    body = {"exam_id": ex1["id"], "subject_id": world.subjects["math"], "exam_date": "2027-03-05", "class_sections": []}
    assert admin.post(f"/exams/{ex1['id']}/dates/multi-section", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A08")
def test_length_and_format_validation(admin, world, ex1):
    assert admin.post(f"/exams/{ex1['id']}/dates", json=date_body(world, ex1["id"], venue="v" * 101)).status_code == 422
    assert admin.post(f"/exams/{ex1['id']}/dates", json=date_body(world, ex1["id"], notes="n" * 301)).status_code == 422
    assert admin.post(f"/exams/{ex1['id']}/dates", json=date_body(world, ex1["id"], when="2026-13-01")).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A09")
def test_list_dates(admin, world, ex_dated):
    rows = admin.get(f"/exams/{ex_dated}/dates", params={"class_id": new_uuid()}).json()
    assert len(rows) == 3
    assert [r["exam_date"] for r in rows] == ["2027-02-01", "2027-02-02", "2027-02-03"]
    for key in ("id", "exam_id", "class_id", "section_id", "subject_id", "start_time", "end_time", "venue", "created_by"):
        assert key in rows[0]
    assert rows[0]["venue"] == "Hall A"
    assert rows[0]["start_time"].startswith("09:30")


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A10")
def test_update_date(admin, world, ex_dated):
    row = dates_of(admin, ex_dated)[0]
    response = admin.put(f"/exams/{ex_dated}/dates/{row['id']}", json={"exam_date": "2027-03-02", "venue": "Hall B"})
    assert response.status_code == 200, response.text
    assert response.json()["exam_date"] == "2027-03-02"
    fresh = next(r for r in dates_of(admin, ex_dated) if r["id"] == row["id"])
    assert fresh["exam_date"] == "2027-03-02" and fresh["venue"] == "Hall B"
    assert fresh["subject_id"] == row["subject_id"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A11")
def test_update_date_empty_body(admin, world, ex_dated):
    row = dates_of(admin, ex_dated)[0]
    response = admin.put(f"/exams/{ex_dated}/dates/{row['id']}", json={})
    assert response.status_code == 200
    fresh = next(r for r in dates_of(admin, ex_dated) if r["id"] == row["id"])
    assert fresh["exam_date"] == row["exam_date"] and fresh["venue"] == row["venue"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A12")
def test_update_unknown_date(admin, ex_dated):
    missing = new_uuid()
    response = admin.put(f"/exams/{ex_dated}/dates/{missing}", json={"venue": "x"})
    assert response.status_code == 404
    assert response.json()["detail"] == f"ExamDate with id {missing} not found"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A13")
def test_delete_date(admin, ex_dated):
    row = dates_of(admin, ex_dated)[0]
    assert admin.delete(f"/exams/{ex_dated}/dates/{row['id']}").status_code == 204
    assert row["id"] not in {r["id"] for r in dates_of(admin, ex_dated)}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A14")
def test_delete_unknown_date(admin, ex_dated):
    assert admin.delete(f"/exams/{ex_dated}/dates/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A15")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_create_and_update_denied(role_clients, world, ex_dated, admin, role):
    client = role_clients[role]
    row = dates_of(admin, ex_dated)[0]
    assert client.post(f"/exams/{ex_dated}/dates", json=date_body(world, ex_dated)).status_code == 403
    assert client.post(f"/exams/{ex_dated}/dates/bulk", json={"dates": [date_body(world, ex_dated)]}).status_code == 403
    assert client.put(f"/exams/{ex_dated}/dates/{row['id']}", json={"venue": "x"}).status_code == 403
    assert next(r for r in dates_of(admin, ex_dated) if r["id"] == row["id"])["venue"] == "Hall A"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A16")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_delete_denied(role_clients, ex_dated, admin, role):
    row = dates_of(admin, ex_dated)[0]
    assert role_clients[role].delete(f"/exams/{ex_dated}/dates/{row['id']}").status_code == 403
    assert row["id"] in {r["id"] for r in dates_of(admin, ex_dated)}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A17")
@pytest.mark.parametrize("role", ALL_ROLES)
def test_list_all_roles(role_clients, ex_dated, role):
    assert role_clients[role].get(f"/exams/{ex_dated}/dates").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A18")
def test_unauthenticated(anon, world, ex_dated, admin):
    row = dates_of(admin, ex_dated)[0]
    assert anon.get(f"/exams/{ex_dated}/dates").status_code == 401
    assert anon.post(f"/exams/{ex_dated}/dates", json=date_body(world, ex_dated)).status_code == 401
    assert anon.post(f"/exams/{ex_dated}/dates/bulk", json={"dates": [date_body(world, ex_dated)]}).status_code == 401
    assert anon.put(f"/exams/{ex_dated}/dates/{row['id']}", json={"venue": "x"}).status_code == 401
    assert anon.delete(f"/exams/{ex_dated}/dates/{row['id']}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A19")
def test_tenant_isolation(tenant_b, ex_dated, admin):
    row = dates_of(admin, ex_dated)[0]
    assert tenant_b.get(f"/exams/{ex_dated}/dates").json() == []
    assert tenant_b.put(f"/exams/{ex_dated}/dates/{row['id']}", json={"venue": "x"}).status_code == 404
    assert tenant_b.delete(f"/exams/{ex_dated}/dates/{row['id']}").status_code == 404
    assert next(r for r in dates_of(admin, ex_dated) if r["id"] == row["id"])["venue"] == "Hall A"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A20")
def test_cschema_mismatch(foreign, world, ex_dated):
    assert foreign.post(f"/exams/{ex_dated}/dates", json=date_body(world, ex_dated)).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-08-A21")
def test_clone_does_not_copy_dates(admin, ex_dated, cleanup):
    from api_tests.exam.helpers import remove_exam

    clone = admin.post(f"/exams/{ex_dated}/clone", json={})
    assert clone.status_code == 201, clone.text
    cleanup.add(remove_exam, admin, clone.json()["id"])
    assert dates_of(admin, clone.json()["id"]) == []
    assert len(dates_of(admin, ex_dated)) == 3
