import copy

import pytest

from api_tests.exam.conftest import World
from api_tests.exam.helpers import (
    ALL_ROLES,
    OTHER_ROLES,
    create_exam,
    create_remark_set,
    exam_payload,
    get_configs,
    new_uuid,
    remove_exam,
)
from api_tests.support import items_of, unique


def post_exam(admin, cleanup, payload):
    response = admin.post("/exams", json=payload)
    if response.status_code == 201:
        cleanup.add(remove_exam, admin, response.json()["exam_id"])
    return response


def names(admin, **params):
    return [e["exam_name"] for e in admin.get("/exams", params=params).json()]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A01")
def test_create_ex1(admin, world, cleanup):
    payload = exam_payload(world, dates=True)
    payload["exam_dates"] = payload["exam_dates"][:2]
    response = post_exam(admin, cleanup, payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "active"
    assert body["class_sections_created"] == 1
    assert body["subject_configs_created"] == 3
    assert body["exam_dates_created"] == 2
    assert body["exam_name"] == payload["exam"]["exam_name"]
    got = admin.get(f"/exams/{body['exam_id']}")
    assert got.status_code == 200
    assert got.json()["status"] == "active"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A02")
def test_duplicate_name_same_year(admin, world, cleanup):
    payload = exam_payload(world)
    assert post_exam(admin, cleanup, payload).status_code == 201
    response = admin.post("/exams", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == f"An exam named '{payload['exam']['exam_name']}' already exists for this academic year."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A03")
def test_same_name_in_other_year(admin, world, cleanup):
    year = admin.post(
        "/masters/academic_years/",
        json={"title": unique("exm_yr_"), "start_date": "6210-04-01", "end_date": "6211-03-31", "is_active": False},
    )
    assert year.status_code == 201, year.text
    cleanup.delete_later(admin, f"/masters/academic_years/{year.json()['id']}")
    payload = exam_payload(world)
    assert post_exam(admin, cleanup, payload).status_code == 201
    other = copy.deepcopy(payload)
    other["exam"]["academic_year_id"] = year.json()["id"]
    assert post_exam(admin, cleanup, other).status_code == 201


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A04")
def test_unmapped_subject_rejected_and_nothing_stored(admin, world, cleanup):
    payload = exam_payload(world, subjects=("math", "extra"), comps={"math": [("W", 50)], "extra": [("W", 50)]})
    response = admin.post("/exams", json=payload)
    assert response.status_code == 422
    assert "is not mapped" in response.json()["detail"]
    assert payload["exam"]["exam_name"] not in names(admin)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A05")
def test_exclude_marks_subject_rejected(admin, world, cleanup):
    payload = exam_payload(world, subjects=("excl",), comps={"excl": [("W", 50)]})
    response = admin.post("/exams", json=payload)
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A06")
def test_config_class_not_in_class_sections(admin, world, cleanup):
    payload = exam_payload(world)
    payload["subject_configs"][0]["class_id"] = new_uuid()
    assert admin.post("/exams", json=payload).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A07")
@pytest.mark.parametrize(
    "component",
    [
        {"component_name": "W", "entry_type": "marks"},
        {"component_name": "R", "entry_type": "remarks"},
    ],
)
def test_component_required_fields(admin, world, component):
    payload = exam_payload(world, subjects=("math",))
    payload["subject_configs"][0]["components"] = [component]
    assert admin.post("/exams", json=payload).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A08")
def test_negative_max_marks(admin, world):
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", -1)]})
    assert admin.post("/exams", json=payload).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A09")
def test_zero_max_marks_accepted(admin, world, cleanup):
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", 0)]})
    assert post_exam(admin, cleanup, payload).status_code == 201


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A10")
@pytest.mark.parametrize("empty", ["class_sections", "subject_configs", "components"])
def test_empty_collections_rejected(admin, world, empty):
    payload = exam_payload(world, subjects=("math",))
    if empty == "components":
        payload["subject_configs"][0]["components"] = []
    else:
        payload[empty] = []
    assert admin.post("/exams", json=payload).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A11")
def test_exam_name_length(admin, world, cleanup):
    ok = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]})
    ok["exam"]["exam_name"] = (unique("exm_") + "n" * 150)[:150]
    assert post_exam(admin, cleanup, ok).status_code == 201
    bad = copy.deepcopy(ok)
    bad["exam"]["exam_name"] = ok["exam"]["exam_name"] + "x"
    assert admin.post("/exams", json=bad).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A12")
@pytest.mark.parametrize("field,value", [("nature", "daily"), ("level", "kg")])
def test_invalid_enum_values(admin, world, field, value):
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]})
    payload["exam"][field] = value
    assert admin.post("/exams", json=payload).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A13")
def test_hall_ticket_attendance_bounds(admin, world, cleanup):
    ok = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]}, hall_ticket_min_attendance=100)
    assert post_exam(admin, cleanup, ok).status_code == 201
    bad = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]}, hall_ticket_min_attendance=101)
    assert admin.post("/exams", json=bad).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A14")
def test_unknown_academic_year_conflicts(admin, world):
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]})
    payload["exam"]["academic_year_id"] = new_uuid()
    assert admin.post("/exams", json=payload).status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A15")
def test_duplicate_date_rows_conflict(admin, world):
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]}, dates=True)
    payload["exam_dates"] = payload["exam_dates"] * 2
    response = admin.post("/exams", json=payload)
    assert response.status_code == 409
    assert payload["exam"]["exam_name"] not in names(admin)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A16")
def test_remarks_component_with_set(admin, world, cleanup):
    rs = create_remark_set(admin, cleanup)
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]})
    payload["subject_configs"][0]["components"].append(
        {"component_name": "Grade", "entry_type": "remarks", "remark_grade_set_id": rs["id"], "sort_order": 2}
    )
    response = post_exam(admin, cleanup, payload)
    assert response.status_code == 201, response.text
    configs = get_configs(admin, response.json()["exam_id"])
    comps = {c["component_name"]: c for c in configs[0]["components"]}
    assert comps["Grade"]["remark_grade_set_id"] == rs["id"]
    assert comps["Grade"]["entry_type"] == "remarks"
    assert comps["Grade"]["max_marks"] is None


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A17")
def test_null_section_class_section(admin, world, cleanup):
    mapped = admin.post(
        "/masters/class-subject-mappings/",
        json={"class_id": world.class_id, "section_id": None, "academic_year_id": world.year_id, "subject_id": world.subjects["extra"], "order": 1, "exclude_marks": False, "is_active": True},
    )
    if mapped.status_code not in (200, 201):
        pytest.skip(f"cannot create a section-less mapping: {mapped.status_code} {mapped.text}")
    cleanup.delete_later(admin, f"/masters/class-subject-mappings/{mapped.json()['id']}")
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]})
    payload["class_sections"] = [{"class_id": world.class_id, "section_id": None}]
    payload["subject_configs"][0]["section_id"] = None
    payload["subject_configs"][0]["subject_id"] = world.subjects["extra"]
    response = post_exam(admin, cleanup, payload)
    assert response.status_code == 201, response.text
    sections = admin.get(f"/exams/{response.json()['exam_id']}/class-sections").json()
    assert sections[0]["section_id"] is None


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A18")
def test_unknown_fields_ignored(admin, world, cleanup):
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]})
    payload["exam"]["status"] = "published"
    payload["exam"]["subject_grade_scheme_id"] = new_uuid()
    response = post_exam(admin, cleanup, payload)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "active"
    assert admin.get(f"/exams/{response.json()['exam_id']}").json()["status"] == "active"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A19")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_create_denied(role_clients, world, role):
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]})
    assert role_clients[role].post("/exams", json=payload).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A20")
def test_list_filters(admin, world, cleanup):
    one = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]}, nature="summative")
    two = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]}, nature="formative")
    assert post_exam(admin, cleanup, one).status_code == 201
    assert post_exam(admin, cleanup, two).status_code == 201
    n1, n2 = one["exam"]["exam_name"], two["exam"]["exam_name"]
    year = world.year_id
    assert {n1, n2} <= set(names(admin, academic_year_id=year))
    active = names(admin, academic_year_id=year, exam_status="active")
    assert {n1, n2} <= set(active)
    summ = names(admin, academic_year_id=year, nature="summative")
    assert n1 in summ and n2 not in summ
    combined = names(admin, academic_year_id=year, exam_status="active", nature="formative")
    assert n2 in combined and n1 not in combined
    assert admin.get("/exams", params={"academic_year_id": year, "exam_status": "draft", "nature": "cumulative"}).json() == [] or n1 not in names(
        admin, academic_year_id=year, exam_status="draft"
    )
    assert names(admin, academic_year_id=new_uuid()) == []
    full = admin.get("/exams", params={"academic_year_id": year}).json()
    ids = [e["exam_name"] for e in full]
    assert ids.index(n2) < ids.index(n1)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A21")
def test_list_shape(admin, world, cleanup):
    exam_id = create_exam(admin, cleanup, world)
    response = admin.get("/exams", params={"academic_year_id": world.year_id})
    assert isinstance(response.json(), list)
    item = next(e for e in response.json() if e["id"] == exam_id)
    assert item["subject_config_count"] == 3
    for key in (
        "exam_name", "board", "level", "exam_type", "nature", "status", "academic_year_id", "mark_entry_deadline",
        "hall_ticket_min_attendance", "attendance_from_date", "attendance_to_date", "publish_rank", "term", "created_at",
    ):
        assert key in item


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A22")
def test_get_exam_and_unknown(admin, world, cleanup):
    exam_id = create_exam(admin, cleanup, world)
    data = admin.get(f"/exams/{exam_id}").json()
    assert data["hall_ticket_published"] is False
    assert data["cloned_from_exam_id"] is None
    assert data["id"] == exam_id
    missing = new_uuid()
    response = admin.get(f"/exams/{missing}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Exam {missing} not found"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A23")
@pytest.mark.parametrize("role", ALL_ROLES)
def test_read_exams_all_roles(role_clients, admin, world, cleanup, role):
    exam_id = create_exam(admin, cleanup, world)
    assert role_clients[role].get("/exams").status_code == 200
    assert role_clients[role].get(f"/exams/{exam_id}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A24")
def test_exams_unauthenticated(anon, world):
    assert anon.get("/exams").status_code == 401
    assert anon.get(f"/exams/{new_uuid()}").status_code == 401
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]})
    assert anon.post("/exams", json=payload).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A25")
def test_exam_tenant_isolation(admin, tenant_b, world, cleanup):
    exam_id = create_exam(admin, cleanup, world)
    assert exam_id not in {e["id"] for e in tenant_b.get("/exams").json()}
    assert tenant_b.get(f"/exams/{exam_id}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A26")
def test_same_name_in_both_tenants(admin, tenant_b, world, cleanup):
    name = unique("exm_both_")
    create_exam(admin, cleanup, world, name=name)
    wb = World(tenant_b, tenant_b.academic_year_id)
    try:
        wb.build(student_count=0)
        payload = exam_payload(wb, name=name, subjects=("math",), comps={"math": [("W", 10)]})
        response = tenant_b.post("/exams", json=payload)
        assert response.status_code == 201, response.text
        cleanup.add(remove_exam, tenant_b, response.json()["exam_id"])
    finally:
        cleanup.run()
        wb.teardown()


@pytest.mark.api
@pytest.mark.tc("TC-EXM-06-A27")
def test_exam_cschema_mismatch(foreign, world):
    payload = exam_payload(world, subjects=("math",), comps={"math": [("W", 10)]})
    assert foreign.post("/exams", json=payload).status_code == 403
    assert foreign.get("/exams").status_code == 403
