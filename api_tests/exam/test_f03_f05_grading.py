import pytest

from api_tests.exam.helpers import (
    ALL_ROLES,
    GS1_BANDS,
    OTHER_ROLES,
    bands,
    create_exam,
    create_exam_scheme,
    create_remark_set,
    create_subject_scheme,
    exam_payload,
    get_configs,
    new_uuid,
    remove_exam,
)
from api_tests.support import items_of, unique

KINDS = {
    "exam": {"label": "Exam grade scheme", "notfound": "ExamGradeScheme"},
    "subject": {"label": "Subject grade scheme", "notfound": "SubjectGradeScheme"},
}
KIND_PARAMS = list(KINDS)


def make(admin, cleanup, kind, name=None, spec=GS1_BANDS):
    maker = create_exam_scheme if kind == "exam" else create_subject_scheme
    return maker(admin, cleanup, name=name, spec=spec)


def band(a, b, label="A", gpa=1, passed=True, order=0, remarks=None):
    return {"from_percent": a, "to_percent": b, "grade_label": label, "gpa": gpa, "is_pass": passed, "sort_order": order, "remarks": remarks}


def raw_post(admin, kind, body, cleanup=None):
    response = admin.post(f"/grade-schemes/{kind}", json=body)
    if cleanup is not None and response.status_code == 201:
        cleanup.delete_later(admin, f"/grade-schemes/{kind}/{response.json()['id']}")
    return response


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A01")
@pytest.mark.tc("TC-EXM-04-A01")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_create_scheme_with_six_bands(admin, cleanup, kind):
    data = make(admin, cleanup, kind)
    assert len(data["bands"]) == 6
    for b in data["bands"]:
        assert b["id"]
        assert isinstance(b["from_percent"], (int, float))
        assert isinstance(b["to_percent"], (int, float))
        assert isinstance(b["gpa"], (int, float))
    labels = {b["grade_label"]: b for b in data["bands"]}
    assert labels["A+"]["gpa"] == 4.0 and labels["A+"]["is_pass"] is True
    assert labels["F"]["is_pass"] is False and labels["F"]["from_percent"] == 0
    assert labels["A"]["to_percent"] == 89.99


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A02")
@pytest.mark.tc("TC-EXM-04-A02")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_duplicate_name_rejected(admin, cleanup, kind):
    data = make(admin, cleanup, kind)
    response = raw_post(admin, kind, {"name": data["name"], "bands": bands()})
    assert response.status_code == 400
    assert response.json()["detail"] == f"{KINDS[kind]['label']} '{data['name']}' already exists"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A03")
@pytest.mark.tc("TC-EXM-04-A03")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_from_greater_than_to_rejected(admin, kind):
    body = {"name": unique("exm_bad_"), "bands": [band(60, 50)]}
    assert raw_post(admin, kind, body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A04")
@pytest.mark.parametrize(
    "bad",
    [
        band(0, 100.01),
        band(-1, 50),
        band(0, 50, label="x" * 11),
        band(0, 50, gpa=-0.5),
        band(0, 50, remarks="r" * 101),
    ],
)
def test_band_field_bounds(admin, bad):
    assert raw_post(admin, "exam", {"name": unique("exm_bad_"), "bands": [bad]}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A05")
def test_empty_bands_allowed(admin, cleanup):
    response = raw_post(admin, "exam", {"name": unique("exm_empty_"), "bands": []}, cleanup)
    assert response.status_code == 201
    assert response.json()["bands"] == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A06")
def test_band_boundaries_zero_and_hundred(admin, cleanup):
    response = raw_post(admin, "exam", {"name": unique("exm_edge_"), "bands": [band(0, 100, "P")]}, cleanup)
    assert response.status_code == 201
    b = response.json()["bands"][0]
    assert b["from_percent"] == 0 and b["to_percent"] == 100


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A07")
@pytest.mark.tc("TC-EXM-04-A05")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_list_and_get_scheme(admin, cleanup, kind):
    data = make(admin, cleanup, kind)
    listed = items_of(admin.get(f"/grade-schemes/{kind}"))
    mine = next(s for s in listed if s["id"] == data["id"])
    assert len(mine["bands"]) == 6
    one = admin.get(f"/grade-schemes/{kind}/{data['id']}")
    assert one.status_code == 200 and len(one.json()["bands"]) == 6


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A08")
@pytest.mark.tc("TC-EXM-04-A05")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_get_unknown_scheme(admin, kind):
    missing = new_uuid()
    response = admin.get(f"/grade-schemes/{kind}/{missing}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"{KINDS[kind]['notfound']} with id {missing} not found"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A09")
@pytest.mark.tc("TC-EXM-04-A06")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_update_replaces_bands_and_name(admin, cleanup, kind):
    data = make(admin, cleanup, kind)
    new_name = unique("exm_new_")
    body = {"name": new_name, "description": "x", "is_default": False, "bands": [band(0, 49.99, "F", 0, False, 0), band(50, 100, "P", 1, True, 1)]}
    response = admin.put(f"/grade-schemes/{kind}/{data['id']}", json=body)
    assert response.status_code == 200, response.text
    fresh = admin.get(f"/grade-schemes/{kind}/{data['id']}").json()
    assert fresh["name"] == new_name
    assert sorted(b["grade_label"] for b in fresh["bands"]) == ["F", "P"]
    old = {b["id"] for b in data["bands"]}
    assert not old & {b["id"] for b in fresh["bands"]}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A09")
@pytest.mark.parametrize("kind", KIND_PARAMS)
@pytest.mark.xfail(strict=True, reason="DEF-EXM-2: PUT /grade-schemes/{kind}/{id} response returns the stale band list instead of the replaced bands")
def test_update_response_shows_replaced_bands(admin, cleanup, kind):
    data = make(admin, cleanup, kind)
    body = {"name": data["name"], "bands": [band(0, 100, "ONLY", 1, True, 0)]}
    response = admin.put(f"/grade-schemes/{kind}/{data['id']}", json=body)
    assert [b["grade_label"] for b in response.json()["bands"]] == ["ONLY"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A10")
def test_update_keeping_same_name(admin, cleanup):
    data = make(admin, cleanup, "exam")
    response = admin.put(f"/grade-schemes/exam/{data['id']}", json={"name": data["name"], "description": "changed", "bands": bands()})
    assert response.status_code == 200
    assert admin.get(f"/grade-schemes/exam/{data['id']}").json()["description"] == "changed"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A11")
@pytest.mark.tc("TC-EXM-04-A07")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_rename_to_existing_name_rejected(admin, cleanup, kind):
    one = make(admin, cleanup, kind)
    two = make(admin, cleanup, kind)
    response = admin.put(f"/grade-schemes/{kind}/{two['id']}", json={"name": one["name"], "bands": bands()})
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A12")
@pytest.mark.tc("TC-EXM-04-A08")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_update_unknown_scheme(admin, kind):
    assert admin.put(f"/grade-schemes/{kind}/{new_uuid()}", json={"name": unique("exm_"), "bands": []}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A13")
@pytest.mark.tc("TC-EXM-04-A09")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_delete_unused_scheme(admin, kind):
    response = raw_post(admin, kind, {"name": unique("exm_del_"), "bands": bands()})
    sid = response.json()["id"]
    assert admin.delete(f"/grade-schemes/{kind}/{sid}").status_code == 204
    assert admin.get(f"/grade-schemes/{kind}/{sid}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A14")
def test_delete_exam_scheme_in_use(admin, world, cleanup):
    scheme = make(admin, cleanup, "exam")
    create_exam(admin, cleanup, world, scheme_id=scheme["id"])
    response = admin.delete(f"/grade-schemes/exam/{scheme['id']}")
    assert response.status_code == 409
    assert admin.get(f"/grade-schemes/exam/{scheme['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A15")
@pytest.mark.tc("TC-EXM-04-A11")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_delete_unknown_scheme(admin, kind):
    assert admin.delete(f"/grade-schemes/{kind}/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A16")
@pytest.mark.tc("TC-EXM-04-A12")
@pytest.mark.parametrize("kind", KIND_PARAMS)
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_scheme_write_denied(role_clients, admin, cleanup, kind, role):
    data = make(admin, cleanup, kind)
    client = role_clients[role]
    assert client.post(f"/grade-schemes/{kind}", json={"name": unique("exm_"), "bands": []}).status_code == 403
    assert client.put(f"/grade-schemes/{kind}/{data['id']}", json={"name": unique("exm_"), "bands": []}).status_code == 403
    assert client.delete(f"/grade-schemes/{kind}/{data['id']}").status_code == 403
    assert admin.get(f"/grade-schemes/{kind}/{data['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A17")
@pytest.mark.tc("TC-EXM-04-A13")
@pytest.mark.parametrize("kind", KIND_PARAMS)
@pytest.mark.parametrize("role", ALL_ROLES)
def test_scheme_read_all_roles(role_clients, admin, cleanup, kind, role):
    data = make(admin, cleanup, kind)
    assert role_clients[role].get(f"/grade-schemes/{kind}").status_code == 200
    assert role_clients[role].get(f"/grade-schemes/{kind}/{data['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A18")
@pytest.mark.tc("TC-EXM-04-A14")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_scheme_unauthenticated(anon, kind):
    sid = new_uuid()
    assert anon.get(f"/grade-schemes/{kind}").status_code == 401
    assert anon.get(f"/grade-schemes/{kind}/{sid}").status_code == 401
    assert anon.post(f"/grade-schemes/{kind}", json={"name": "x", "bands": []}).status_code == 401
    assert anon.put(f"/grade-schemes/{kind}/{sid}", json={"name": "x", "bands": []}).status_code == 401
    assert anon.delete(f"/grade-schemes/{kind}/{sid}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A19")
@pytest.mark.tc("TC-EXM-04-A15")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_scheme_tenant_isolation(admin, tenant_b, cleanup, kind):
    data = make(admin, cleanup, kind)
    assert data["id"] not in {s["id"] for s in items_of(tenant_b.get(f"/grade-schemes/{kind}"))}
    assert tenant_b.get(f"/grade-schemes/{kind}/{data['id']}").status_code == 404
    assert tenant_b.delete(f"/grade-schemes/{kind}/{data['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A20")
def test_same_scheme_name_in_both_tenants(admin, tenant_b, cleanup):
    name = unique("exm_both_")
    make(admin, cleanup, "exam", name=name)
    make(tenant_b, cleanup, "exam", name=name)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A21")
@pytest.mark.tc("TC-EXM-04-A15")
@pytest.mark.parametrize("kind", KIND_PARAMS)
def test_scheme_cschema_mismatch(foreign, kind):
    assert foreign.post(f"/grade-schemes/{kind}", json={"name": unique("exm_"), "bands": []}).status_code == 403
    assert foreign.get(f"/grade-schemes/{kind}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-03-A22")
def test_two_default_schemes_allowed(admin, cleanup):
    one = create_exam_scheme(admin, cleanup, default=True)
    two = create_exam_scheme(admin, cleanup, default=True)
    assert one["is_default"] is True and two["is_default"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXM-04-A04")
def test_subject_scheme_name_independent_of_exam_scheme(admin, cleanup):
    name = unique("exm_same_")
    make(admin, cleanup, "exam", name=name)
    make(admin, cleanup, "subject", name=name)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-04-A10")
@pytest.mark.xfail(strict=True, reason="KG-12: DELETE /grade-schemes/subject/{id} on a scheme assigned to an exam subject config returns 500 instead of 409")
def test_delete_subject_scheme_in_use(admin, world, cleanup):
    scheme = create_subject_scheme(admin, cleanup)
    payload = exam_payload(world)
    payload["subject_configs"][0]["subject_grade_scheme_id"] = scheme["id"]
    response = admin.post("/exams", json=payload)
    assert response.status_code == 201, response.text
    cleanup.add(remove_exam, admin, response.json()["exam_id"])
    result = admin.delete(f"/grade-schemes/subject/{scheme['id']}")
    assert result.status_code == 409
    assert admin.get(f"/grade-schemes/subject/{scheme['id']}").status_code == 200


def remark_body(name=None, options=None):
    if options is None:
        options = [{"grade_letter": "A", "label": "Excellent", "sort_order": 0}, {"grade_letter": "B", "label": "Good", "sort_order": 1}]
    return {"name": name or unique("exm_rs_"), "options": options}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A01")
def test_create_remark_set(admin, cleanup):
    data = create_remark_set(admin, cleanup)
    assert len(data["options"]) == 2
    for o in data["options"]:
        assert o["id"] and o["set_id"] == data["id"]
    assert {o["grade_letter"]: o["label"] for o in data["options"]} == {"A": "Excellent", "B": "Good"}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A02")
def test_remark_set_duplicate_name(admin, cleanup):
    data = create_remark_set(admin, cleanup)
    response = admin.post("/remark-grades", json=remark_body(data["name"]))
    assert response.status_code == 400
    assert response.json()["detail"] == f"Remark grade set '{data['name']}' already exists"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A03")
@pytest.mark.parametrize(
    "option",
    [
        {"grade_letter": "A", "label": "x" * 51},
        {"grade_letter": "ABCDEF", "label": "ok"},
    ],
)
def test_remark_option_bounds(admin, option):
    assert admin.post("/remark-grades", json=remark_body(options=[option])).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A03")
def test_remark_option_boundary_values_accepted(admin, cleanup):
    response = admin.post("/remark-grades", json=remark_body(options=[{"grade_letter": "ABCDE", "label": "x" * 50}]))
    assert response.status_code == 201
    cleanup.delete_later(admin, f"/remark-grades/{response.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A04")
def test_remark_set_empty_options(admin, cleanup):
    response = admin.post("/remark-grades", json=remark_body(options=[]))
    assert response.status_code == 201
    cleanup.delete_later(admin, f"/remark-grades/{response.json()['id']}")
    assert response.json()["options"] == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A05")
def test_remark_set_get_and_list(admin, cleanup):
    data = create_remark_set(admin, cleanup)
    assert data["id"] in {s["id"] for s in items_of(admin.get("/remark-grades"))}
    assert admin.get(f"/remark-grades/{data['id']}").status_code == 200
    assert admin.get(f"/remark-grades/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A06")
def test_remark_set_rename_only(admin, cleanup):
    data = create_remark_set(admin, cleanup)
    new_name = unique("exm_rs_")
    response = admin.put(f"/remark-grades/{data['id']}", json={"name": new_name})
    assert response.status_code == 200
    fresh = admin.get(f"/remark-grades/{data['id']}").json()
    assert fresh["name"] == new_name
    assert {o["id"] for o in fresh["options"]} == {o["id"] for o in data["options"]}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A07")
def test_remark_set_replace_options(admin, cleanup):
    data = create_remark_set(admin, cleanup)
    options = [{"grade_letter": "C", "label": "Fair", "sort_order": 0}]
    response = admin.put(f"/remark-grades/{data['id']}", json={"options": options})
    assert response.status_code == 200
    fresh = admin.get(f"/remark-grades/{data['id']}").json()
    assert [o["grade_letter"] for o in fresh["options"]] == ["C"]
    assert not {o["id"] for o in data["options"]} & {o["id"] for o in fresh["options"]}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A07")
@pytest.mark.xfail(strict=True, reason="DEF-EXM-3: PUT /remark-grades/{id} response returns the stale options instead of the replaced list")
def test_remark_set_update_response_shows_new_options(admin, cleanup):
    data = create_remark_set(admin, cleanup)
    options = [{"grade_letter": "C", "label": "Fair", "sort_order": 0}]
    response = admin.put(f"/remark-grades/{data['id']}", json={"options": options})
    assert [o["grade_letter"] for o in response.json()["options"]] == ["C"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A08")
def test_remark_set_rename_conflict(admin, cleanup):
    one = create_remark_set(admin, cleanup)
    two = create_remark_set(admin, cleanup)
    assert admin.put(f"/remark-grades/{two['id']}", json={"name": one["name"]}).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A09")
def test_remark_set_delete_unused(admin):
    response = admin.post("/remark-grades", json=remark_body())
    sid = response.json()["id"]
    assert admin.delete(f"/remark-grades/{sid}").status_code == 204
    assert admin.get(f"/remark-grades/{sid}").status_code == 404
    assert admin.put(f"/remark-grades/{new_uuid()}", json={"name": "x"}).status_code == 404
    assert admin.delete(f"/remark-grades/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A10")
@pytest.mark.xfail(strict=True, reason="KG-12: DELETE /remark-grades/{id} on a set used by an exam component returns 500 instead of 409")
def test_remark_set_delete_in_use(admin, world, cleanup):
    rs = create_remark_set(admin, cleanup)
    payload = exam_payload(world, subjects=("eng",))
    payload["subject_configs"][0]["components"].append(
        {"component_name": "Grade", "entry_type": "remarks", "remark_grade_set_id": rs["id"], "sort_order": 2}
    )
    response = admin.post("/exams", json=payload)
    assert response.status_code == 201, response.text
    cleanup.add(remove_exam, admin, response.json()["exam_id"])
    result = admin.delete(f"/remark-grades/{rs['id']}")
    assert result.status_code == 409
    assert admin.get(f"/remark-grades/{rs['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A11")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_remark_write_denied(role_clients, admin, cleanup, role):
    data = create_remark_set(admin, cleanup)
    client = role_clients[role]
    assert client.post("/remark-grades", json=remark_body()).status_code == 403
    assert client.put(f"/remark-grades/{data['id']}", json={"name": unique("exm_")}).status_code == 403
    assert client.delete(f"/remark-grades/{data['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A12")
@pytest.mark.parametrize("role", ALL_ROLES)
def test_remark_read_all_roles(role_clients, admin, cleanup, role):
    data = create_remark_set(admin, cleanup)
    assert role_clients[role].get("/remark-grades").status_code == 200
    assert role_clients[role].get(f"/remark-grades/{data['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A13")
def test_remark_unauthenticated(anon):
    sid = new_uuid()
    assert anon.get("/remark-grades").status_code == 401
    assert anon.get(f"/remark-grades/{sid}").status_code == 401
    assert anon.post("/remark-grades", json=remark_body()).status_code == 401
    assert anon.put(f"/remark-grades/{sid}", json={"name": "x"}).status_code == 401
    assert anon.delete(f"/remark-grades/{sid}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-05-A14")
def test_remark_isolation_and_cschema(admin, tenant_b, foreign, cleanup):
    data = create_remark_set(admin, cleanup)
    assert data["id"] not in {s["id"] for s in items_of(tenant_b.get("/remark-grades"))}
    assert tenant_b.get(f"/remark-grades/{data['id']}").status_code == 404
    assert foreign.post("/remark-grades", json=remark_body()).status_code == 403
