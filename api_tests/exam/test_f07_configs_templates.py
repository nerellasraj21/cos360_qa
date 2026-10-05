import pytest

from api_tests.exam.helpers import (
    ALL_ROLES,
    DEFAULT_COMPONENTS,
    OTHER_ROLES,
    config_map,
    create_exam,
    create_subject_scheme,
    get_configs,
    new_uuid,
)
from api_tests.support import items_of, unique


def add_section(admin, exam_id, world, section):
    return admin.post(f"/exams/{exam_id}/class-sections", json={"class_id": world.class_id, "section_id": world.sections[section]})


def template_body(world, name=None, subjects=("math", "sci"), board=None, level=None):
    items = []
    for idx, sub in enumerate(subjects):
        items.append(
            {
                "subject_id": world.subjects[sub],
                "sort_order": idx + 1,
                "components": [
                    {"component_name": cn, "entry_type": "marks", "max_marks": mx, "include_in_total": True, "sort_order": ci + 1}
                    for ci, (cn, mx) in enumerate(DEFAULT_COMPONENTS[sub])
                ],
            }
        )
    body = {"template_name": name or unique("exm_tpl_"), "description": "d", "items": items}
    if board:
        body["board"] = board
    if level:
        body["level"] = level
    return body


def make_template(admin, cleanup, world, **kwargs):
    response = admin.post("/exam-patterns/templates", json=template_body(world, **kwargs))
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/exam-patterns/templates/{data['id']}")
    return data


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A01")
def test_get_class_sections(admin, world, ex1):
    response = admin.get(f"/exams/{ex1['id']}/class-sections")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["class_id"] == world.class_id and rows[0]["section_id"] == world.sections["a"]
    for key in ("id", "exam_id", "stream_id", "created_at"):
        assert key in rows[0]
    assert "class_name" not in rows[0]
    assert admin.get(f"/exams/{new_uuid()}/class-sections").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A02")
def test_add_class_section(admin, world, ex1):
    response = add_section(admin, ex1["id"], world, "b")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["class_section"]["id"]
    assert body["class_section"]["section_id"] == world.sections["b"]
    assert body["auto_detect"]["has_suggestions"] is True
    assert len(admin.get(f"/exams/{ex1['id']}/class-sections").json()) == 2


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A03")
def test_add_class_section_duplicate(admin, world, ex1):
    assert add_section(admin, ex1["id"], world, "b").status_code == 201
    response = add_section(admin, ex1["id"], world, "b")
    assert response.status_code == 409
    assert response.json()["detail"] == "This class/section is already part of the exam."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A04")
def test_add_class_section_to_published_exam(admin, world, ex1):
    assert admin.post(f"/exams/{ex1['id']}/publish").status_code == 200
    response = add_section(admin, ex1["id"], world, "b")
    assert response.status_code == 409
    assert response.json()["detail"] == "Cannot add class-sections to exam with status 'published'."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A04")
def test_add_class_section_to_draft_exam(admin, world, ex1):
    assert admin.post(f"/exams/{ex1['id']}/deactivate").status_code == 200
    assert add_section(admin, ex1["id"], world, "b").status_code == 201


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A05")
def test_add_class_section_unknown_exam(admin, world):
    assert add_section(admin, new_uuid(), world, "b").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A06")
def test_get_subject_configs(admin, world, ex1):
    rows = admin.get(f"/exams/{ex1['id']}/subject-configs").json()
    assert len(rows) == 3
    assert [r["sort_order"] for r in rows] == [1, 2, 3]
    inverse = {v: k for k, v in world.subjects.items()}
    assert [inverse[r["subject_id"]] for r in rows] == ["math", "sci", "eng"]
    math = rows[0]
    assert sorted(c["max_marks"] for c in math["components"]) == ["20.00", "80.00"]
    for r in rows:
        assert r["components"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A07")
def test_get_one_config_and_unknown(admin, world, ex1):
    cfg = ex1["configs"][0]
    response = admin.get(f"/exams/{ex1['id']}/subject-configs/{cfg['id']}")
    assert response.status_code == 200
    assert len(response.json()["components"]) == len(cfg["components"])
    missing = new_uuid()
    miss = admin.get(f"/exams/{ex1['id']}/subject-configs/{missing}")
    assert miss.status_code == 404
    assert miss.json()["detail"] == f"ExamSubjectConfig {missing} not found"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A08")
@pytest.mark.xfail(strict=True, reason="DEF-EXM-4: PUT /exams/{id}/subject-configs/{cid} returns 500 MissingGreenlet whenever a column value changes (the change is committed)")
def test_update_config_fields_response(admin, world, ex1, cleanup):
    cfg = ex1["configs"][0]
    scheme = create_subject_scheme(admin, cleanup)
    response = admin.put(
        f"/exams/{ex1['id']}/subject-configs/{cfg['id']}", json={"credit_hours": 4, "subject_grade_scheme_id": scheme["id"]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["credit_hours"] == 4


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A08")
def test_update_config_fields_persisted(admin, world, ex1, cleanup):
    cfg = ex1["configs"][0]
    scheme = create_subject_scheme(admin, cleanup)
    admin.put(f"/exams/{ex1['id']}/subject-configs/{cfg['id']}", json={"credit_hours": 4, "subject_grade_scheme_id": scheme["id"]})
    fresh = admin.get(f"/exams/{ex1['id']}/subject-configs/{cfg['id']}").json()
    assert fresh["credit_hours"] == 4
    assert fresh["subject_grade_scheme_id"] == scheme["id"]
    assert {c["id"] for c in fresh["components"]} == {c["id"] for c in cfg["components"]}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A09")
def test_update_config_clear_scheme_persisted(admin, world, ex1, cleanup):
    cfg = ex1["configs"][0]
    scheme = create_subject_scheme(admin, cleanup)
    admin.put(f"/exams/{ex1['id']}/subject-configs/{cfg['id']}", json={"subject_grade_scheme_id": scheme["id"]})
    admin.put(f"/exams/{ex1['id']}/subject-configs/{cfg['id']}", json={"subject_grade_scheme_id": None})
    assert admin.get(f"/exams/{ex1['id']}/subject-configs/{cfg['id']}").json()["subject_grade_scheme_id"] is None


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A09")
@pytest.mark.xfail(strict=True, reason="DEF-EXM-4: PUT subject-configs returns 500 MissingGreenlet when clearing an assigned scheme (the change is committed)")
def test_update_config_clear_scheme_response(admin, world, ex1, cleanup):
    cfg = ex1["configs"][0]
    scheme = create_subject_scheme(admin, cleanup)
    admin.put(f"/exams/{ex1['id']}/subject-configs/{cfg['id']}", json={"subject_grade_scheme_id": scheme["id"]})
    response = admin.put(f"/exams/{ex1['id']}/subject-configs/{cfg['id']}", json={"subject_grade_scheme_id": None})
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A10")
def test_update_config_is_active_ignored(admin, world, ex1):
    cfg = ex1["configs"][0]
    response = admin.put(f"/exams/{ex1['id']}/subject-configs/{cfg['id']}", json={"is_active": False})
    assert response.status_code == 200
    assert len(admin.get(f"/exams/{ex1['id']}/subject-configs").json()) == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A11")
def test_update_config_unknown(admin, ex1):
    assert admin.put(f"/exams/{ex1['id']}/subject-configs/{new_uuid()}", json={"credit_hours": 1}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A12")
def test_create_template_manual(admin, world, cleanup):
    data = make_template(admin, cleanup, world)
    assert len(data["items"]) == 2
    math = next(i for i in data["items"] if i["subject_id"] == world.subjects["math"])
    assert len(math["components"]) == 2
    listed = next(t for t in items_of(admin.get("/exam-patterns/templates")) if t["id"] == data["id"])
    assert listed["item_count"] == 2


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A13")
def test_template_duplicate_name(admin, world, cleanup):
    data = make_template(admin, cleanup, world)
    response = admin.post("/exam-patterns/templates", json=template_body(world, name=data["template_name"]))
    assert response.status_code == 409
    assert response.json()["detail"] == f"Template named '{data['template_name']}' already exists."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A14")
def test_template_from_exam(admin, world, ex1, cleanup):
    name = unique("exm_tpl_")
    response = admin.post(
        "/exam-patterns/templates/from-exam",
        json={"template_name": name, "exam_id": ex1["id"], "class_id": world.class_id, "section_id": world.sections["a"]},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/exam-patterns/templates/{data['id']}")
    assert data["source_exam_id"] == ex1["id"]
    assert len(data["items"]) == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A15")
def test_template_from_exam_without_configs(admin, world, ex1):
    response = admin.post(
        "/exam-patterns/templates/from-exam",
        json={"template_name": unique("exm_tpl_"), "exam_id": ex1["id"], "class_id": world.class_id, "section_id": world.sections["b"]},
    )
    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A16")
def test_list_templates_filters(admin, world, cleanup):
    one = make_template(admin, cleanup, world, board="CBSE", level="exm_lvl_a")
    two = make_template(admin, cleanup, world, board="ICSE", level="exm_lvl_a")
    rows = items_of(admin.get("/exam-patterns/templates", params={"board": "CBSE", "level": "exm_lvl_a"}))
    ids = {r["id"] for r in rows}
    assert one["id"] in ids and two["id"] not in ids
    rows = items_of(admin.get("/exam-patterns/templates", params={"level": "exm_lvl_a"}))
    assert {one["id"], two["id"]} <= {r["id"] for r in rows}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A17")
def test_get_template_unknown_and_deactivated(admin, world, cleanup):
    data = make_template(admin, cleanup, world)
    assert admin.get(f"/exam-patterns/templates/{data['id']}").status_code == 200
    assert admin.get(f"/exam-patterns/templates/{new_uuid()}").status_code == 404
    admin.delete(f"/exam-patterns/templates/{data['id']}")
    assert admin.get(f"/exam-patterns/templates/{data['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A18")
def test_update_template(admin, world, cleanup):
    data = make_template(admin, cleanup, world)
    new_name = unique("exm_tpl_")
    response = admin.put(f"/exam-patterns/templates/{data['id']}", json={"template_name": new_name, "description": "changed"})
    assert response.status_code == 200
    fresh = admin.get(f"/exam-patterns/templates/{data['id']}").json()
    assert fresh["template_name"] == new_name and fresh["description"] == "changed"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A19")
def test_update_template_deactivate(admin, world, cleanup):
    data = make_template(admin, cleanup, world)
    response = admin.put(f"/exam-patterns/templates/{data['id']}", json={"is_active": False})
    assert response.status_code == 200
    assert data["id"] not in {t["id"] for t in items_of(admin.get("/exam-patterns/templates"))}
    assert admin.get(f"/exam-patterns/templates/{data['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A20")
def test_delete_template_soft(admin, world, cleanup):
    data = make_template(admin, cleanup, world)
    response = admin.delete(f"/exam-patterns/templates/{data['id']}")
    assert response.status_code == 200
    assert response.json() == {"detail": "Template deactivated"}
    assert admin.get(f"/exam-patterns/templates/{data['id']}").status_code == 404
    assert data["id"] not in {t["id"] for t in items_of(admin.get("/exam-patterns/templates"))}
    assert admin.delete(f"/exam-patterns/templates/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A21")
@pytest.mark.xfail(strict=True, reason="KG-12: creating a template with the name of a deleted (inactive) template returns 500 (database unique constraint)")
def test_template_name_reuse_after_delete(admin, world, cleanup):
    data = make_template(admin, cleanup, world)
    admin.delete(f"/exam-patterns/templates/{data['id']}")
    response = admin.post("/exam-patterns/templates", json=template_body(world, name=data["template_name"]))
    assert response.status_code in (201, 409)


def copy_body(world, src, dst, skip=False):
    return {
        "source_class_id": world.class_id,
        "source_section_id": world.sections[src],
        "target_class_id": world.class_id,
        "target_section_id": world.sections[dst],
        "skip_missing_subjects": skip,
    }


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A22")
def test_copy_pattern_to_empty_target(admin, world, ex1):
    assert add_section(admin, ex1["id"], world, "c").status_code == 201
    response = admin.post(f"/exam-patterns/{ex1['id']}/copy", json=copy_body(world, "a", "c"))
    assert response.status_code == 200, response.text
    assert response.json() == {"configs_created": 3, "skipped_subjects": []}
    configs = get_configs(admin, ex1["id"])
    target = config_map(world, configs, "c")
    assert set(target) == {"math", "sci", "eng"}
    assert sorted(c["max_marks"] for c in target["math"]["components"]) == ["20.00", "80.00"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A23")
def test_copy_to_target_with_configs(admin, world, ex1):
    add_section(admin, ex1["id"], world, "c")
    assert admin.post(f"/exam-patterns/{ex1['id']}/copy", json=copy_body(world, "a", "c")).status_code == 200
    response = admin.post(f"/exam-patterns/{ex1['id']}/copy", json=copy_body(world, "a", "c"))
    assert response.status_code == 409
    assert response.json()["detail"] == "Target class/section already has subject configs for this exam."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A24")
def test_copy_to_section_not_in_exam(admin, world, ex1):
    response = admin.post(f"/exam-patterns/{ex1['id']}/copy", json=copy_body(world, "a", "c"))
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A25")
def test_copy_with_missing_subject_rejected(admin, world, ex1):
    add_section(admin, ex1["id"], world, "b")
    response = admin.post(f"/exam-patterns/{ex1['id']}/copy", json=copy_body(world, "a", "b"))
    assert response.status_code == 422
    assert world.subjects["eng"] in response.text
    assert config_map(world, get_configs(admin, ex1["id"]), "b") == {}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A26")
def test_copy_with_missing_subject_skipped(admin, world, ex1):
    add_section(admin, ex1["id"], world, "b")
    response = admin.post(f"/exam-patterns/{ex1['id']}/copy", json=copy_body(world, "a", "b", skip=True))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["configs_created"] == 2
    assert [str(s) for s in body["skipped_subjects"]] == [world.subjects["eng"]]
    assert set(config_map(world, get_configs(admin, ex1["id"]), "b")) == {"math", "sci"}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A27")
def test_copy_from_source_without_configs(admin, world, ex1):
    add_section(admin, ex1["id"], world, "b")
    add_section(admin, ex1["id"], world, "c")
    response = admin.post(f"/exam-patterns/{ex1['id']}/copy", json=copy_body(world, "b", "c"))
    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A28")
def test_apply_template(admin, world, ex1, cleanup):
    tpl = make_template(admin, cleanup, world, subjects=("math", "sci", "eng"))
    add_section(admin, ex1["id"], world, "c")
    body = {"template_id": tpl["id"], "target_class_id": world.class_id, "target_section_id": world.sections["c"]}
    response = admin.post(f"/exam-patterns/{ex1['id']}/apply-template", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["configs_created"] == 3
    target = config_map(world, get_configs(admin, ex1["id"]), "c")
    assert sorted(c["max_marks"] for c in target["math"]["components"]) == ["20.00", "80.00"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A28")
def test_apply_template_with_unmapped_subject(admin, world, ex1, cleanup):
    tpl = make_template(admin, cleanup, world, subjects=("math", "sci", "eng"))
    add_section(admin, ex1["id"], world, "b")
    body = {"template_id": tpl["id"], "target_class_id": world.class_id, "target_section_id": world.sections["b"]}
    rejected = admin.post(f"/exam-patterns/{ex1['id']}/apply-template", json=body)
    assert rejected.status_code == 422
    assert f"Template subject {world.subjects['eng']} is not mapped to target class/section." in rejected.text
    skipped = admin.post(f"/exam-patterns/{ex1['id']}/apply-template", json={**body, "skip_missing_subjects": True})
    assert skipped.status_code == 200, skipped.text
    assert skipped.json()["configs_created"] == 2
    assert [str(s) for s in skipped.json()["skipped_subjects"]] == [world.subjects["eng"]]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A29")
def test_apply_deactivated_template(admin, world, ex1, cleanup):
    tpl = make_template(admin, cleanup, world)
    admin.delete(f"/exam-patterns/templates/{tpl['id']}")
    add_section(admin, ex1["id"], world, "c")
    body = {"template_id": tpl["id"], "target_class_id": world.class_id, "target_section_id": world.sections["c"]}
    assert admin.post(f"/exam-patterns/{ex1['id']}/apply-template", json=body).status_code == 404


def compare_params(world, src, dst):
    return {
        "source_class_id": world.class_id,
        "source_section_id": world.sections[src],
        "target_class_id": world.class_id,
        "target_section_id": world.sections[dst],
    }


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A30")
def test_compare_subjects(admin, world, ex1):
    response = admin.get(f"/exam-patterns/{ex1['id']}/compare", params=compare_params(world, "a", "b"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"common_subjects", "source_only_subjects", "target_only_subjects", "can_copy_all", "copyable_count"}
    assert body["copyable_count"] == 2
    assert {s["subject_id"] for s in body["common_subjects"]} == {world.subjects["math"], world.subjects["sci"]}
    assert [s["subject_id"] for s in body["source_only_subjects"]] == [world.subjects["eng"]]
    assert body["can_copy_all"] is False
    same = admin.get(f"/exam-patterns/{ex1['id']}/compare", params=compare_params(world, "a", "c")).json()
    assert same["can_copy_all"] is True and same["copyable_count"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A31")
def test_auto_detect(admin, world, ex1):
    response = admin.get(
        f"/exam-patterns/{ex1['id']}/auto-detect", params={"target_class_id": world.class_id, "target_section_id": world.sections["c"]}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_suggestions"] is True
    counts = [s["overlap_subject_count"] for s in body["suggestions"]]
    assert counts == sorted(counts, reverse=True)
    top = body["suggestions"][0]
    assert top["source_section_id"] == world.sections["a"]
    assert top["source_class_name"] == world.tag
    assert top["overlap_subject_count"] == 3


WRITE_CASES = [
    ("add_section", lambda w, e, t: ("post", f"/exams/{e}/class-sections", {"class_id": w.class_id, "section_id": w.sections["b"]})),
    ("template", lambda w, e, t: ("post", "/exam-patterns/templates", template_body(w))),
    (
        "from_exam",
        lambda w, e, t: (
            "post",
            "/exam-patterns/templates/from-exam",
            {"template_name": unique("exm_x_"), "exam_id": e, "class_id": w.class_id, "section_id": w.sections["a"]},
        ),
    ),
    ("copy", lambda w, e, t: ("post", f"/exam-patterns/{e}/copy", copy_body(w, "a", "c"))),
    (
        "apply",
        lambda w, e, t: (
            "post",
            f"/exam-patterns/{e}/apply-template",
            {"template_id": t, "target_class_id": w.class_id, "target_section_id": w.sections["c"]},
        ),
    ),
]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A32")
@pytest.mark.parametrize("role", OTHER_ROLES)
@pytest.mark.parametrize("case", [c[0] for c in WRITE_CASES])
def test_write_endpoints_denied(role_clients, world, ex1, admin, cleanup, role, case):
    tpl = make_template(admin, cleanup, world)
    method, path, body = dict(WRITE_CASES)[case](world, ex1["id"], tpl["id"])
    assert getattr(role_clients[role], method)(path, json=body).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A33")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_update_and_delete_denied(role_clients, world, ex1, admin, cleanup, role):
    tpl = make_template(admin, cleanup, world)
    client = role_clients[role]
    cfg = ex1["configs"][0]
    assert client.put(f"/exams/{ex1['id']}/subject-configs/{cfg['id']}", json={"credit_hours": 9}).status_code == 403
    assert client.put(f"/exam-patterns/templates/{tpl['id']}", json={"template_name": "x"}).status_code == 403
    assert client.delete(f"/exam-patterns/templates/{tpl['id']}").status_code == 403
    assert admin.get(f"/exam-patterns/templates/{tpl['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A34")
@pytest.mark.parametrize("role", ALL_ROLES)
def test_read_endpoints_all_roles(role_clients, world, ex1, admin, cleanup, role):
    tpl = make_template(admin, cleanup, world)
    client = role_clients[role]
    cfg = ex1["configs"][0]
    e = ex1["id"]
    assert client.get(f"/exams/{e}/class-sections").status_code == 200
    assert client.get(f"/exams/{e}/subject-configs").status_code == 200
    assert client.get(f"/exams/{e}/subject-configs/{cfg['id']}").status_code == 200
    assert client.get(f"/exam-patterns/templates/{tpl['id']}").status_code == 200
    assert client.get(f"/exam-patterns/{e}/compare", params=compare_params(world, "a", "b")).status_code == 200
    params = {"target_class_id": world.class_id, "target_section_id": world.sections["c"]}
    assert client.get(f"/exam-patterns/{e}/auto-detect", params=params).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A35")
@pytest.mark.parametrize("role", ALL_ROLES)
def test_list_templates_all_roles(role_clients, role):
    assert role_clients[role].get("/exam-patterns/templates").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A36")
def test_unauthenticated(anon, world, ex1):
    e = ex1["id"]
    cfg = ex1["configs"][0]["id"]
    tid = new_uuid()
    assert anon.get(f"/exams/{e}/class-sections").status_code == 401
    assert anon.post(f"/exams/{e}/class-sections", json={"class_id": world.class_id, "section_id": world.sections["b"]}).status_code == 401
    assert anon.get(f"/exams/{e}/subject-configs").status_code == 401
    assert anon.get(f"/exams/{e}/subject-configs/{cfg}").status_code == 401
    assert anon.put(f"/exams/{e}/subject-configs/{cfg}", json={"credit_hours": 1}).status_code == 401
    assert anon.post("/exam-patterns/templates", json=template_body(world)).status_code == 401
    assert anon.get("/exam-patterns/templates").status_code == 401
    assert anon.get(f"/exam-patterns/templates/{tid}").status_code == 401
    assert anon.put(f"/exam-patterns/templates/{tid}", json={"template_name": "x"}).status_code == 401
    assert anon.delete(f"/exam-patterns/templates/{tid}").status_code == 401
    assert anon.post(f"/exam-patterns/{e}/copy", json=copy_body(world, "a", "c")).status_code == 401
    assert anon.get(f"/exam-patterns/{e}/compare", params=compare_params(world, "a", "b")).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-07-A37")
def test_tenant_isolation(admin, tenant_b, foreign, world, ex1, cleanup):
    tpl = make_template(admin, cleanup, world)
    assert tenant_b.get(f"/exam-patterns/templates/{tpl['id']}").status_code == 404
    assert tpl["id"] not in {t["id"] for t in items_of(tenant_b.get("/exam-patterns/templates"))}
    assert tenant_b.get(f"/exams/{ex1['id']}/class-sections").status_code == 404
    assert foreign.post(f"/exam-patterns/{ex1['id']}/copy", json=copy_body(world, "a", "c")).status_code == 403
