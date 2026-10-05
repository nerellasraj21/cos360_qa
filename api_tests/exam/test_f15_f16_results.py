import pytest

from api_tests.exam.helpers import (
    GS1_BANDS,
    OTHER_ROLES,
    audit_actions,
    bands,
    config_map,
    create_exam,
    create_subject_scheme,
    enter_student_marks,
    exam_payload,
    get_configs,
    mark_row,
    new_uuid,
    remove_exam,
    save_marks,
    standard_marks,
    comp_by_name,
)
from api_tests.support import unique

TARGET_403 = "KG-3: Student and Parent hold exams:read and can list every student's results, published or not"


@pytest.fixture
def rx(admin, world, cleanup):
    exam_id = create_exam(admin, cleanup, world)
    configs = get_configs(admin, exam_id)
    standard_marks(admin, exam_id, world, configs)
    return {"id": exam_id, "configs": configs}


@pytest.fixture
def rc(admin, rx):
    response = admin.post(f"/exams/{rx['id']}/compute")
    assert response.status_code == 200, response.text
    return rx


def results(admin, exam_id, **params):
    response = admin.get(f"/exams/{exam_id}/results", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def sub_by_name(world, row):
    inverse = {v: k for k, v in world.subjects.items()}
    out = {}
    for s in row["subject_results"]:
        out[s["subject_name"].replace(world.tag, "")] = s
    return out


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A01")
def test_compute_three_students(admin, rx):
    response = admin.post(f"/exams/{rx['id']}/compute")
    assert response.status_code == 200
    assert response.json() == {"exam_id": rx["id"], "students_computed": 3, "status": "computed"}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A02")
def test_results_exact_values(admin, world, rc):
    rows = results(admin, rc["id"])
    assert [r["student_id"] for r in rows] == [world.students[1]["id"], world.students[0]["id"], world.students[2]["id"]]
    s2, s1, s3 = rows
    assert (s2["total_marks_obtained"], s2["total_max_marks"], s2["percentage"], s2["grade_label"], s2["gpa"], s2["rank"], s2["is_passed"]) == (
        "270.00", "300.00", "90.00", "A+", "4.00", 1, True,
    )
    assert (s1["total_marks_obtained"], s1["total_max_marks"], s1["percentage"], s1["grade_label"], s1["gpa"], s1["rank"], s1["is_passed"]) == (
        "240.00", "300.00", "80.00", "A", "3.50", 2, True,
    )
    assert (s3["total_marks_obtained"], s3["percentage"], s3["grade_label"], s3["gpa"], s3["rank"], s3["is_passed"]) == (
        "130.00", "43.33", "D", "1.00", 3, False,
    )
    subs = sub_by_name(world, s1)
    assert (subs["math"]["marks_obtained"], subs["math"]["max_marks"], subs["math"]["percentage"], subs["math"]["grade_label"]) == ("80.00", "100.00", "80.00", "A")
    assert (subs["sci"]["percentage"], subs["sci"]["grade_label"]) == ("90.00", "A+")
    assert (subs["eng"]["percentage"], subs["eng"]["grade_label"], subs["eng"]["gpa"]) == ("70.00", "B", "3.00")
    s3subs = sub_by_name(world, s3)
    assert (s3subs["math"]["percentage"], s3subs["math"]["grade_label"], s3subs["math"]["is_passed"]) == ("55.00", "D", True)
    assert (s3subs["eng"]["grade_label"], s3subs["eng"]["is_passed"]) == ("F", False)
    for r in rows:
        assert r["student_name"] and r["admission_number"] and r["computed_at"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A03")
def test_absent_subject_row(admin, world, cleanup):
    exam_id = create_exam(admin, cleanup, world)
    configs = get_configs(admin, exam_id)
    cmap = config_map(world, configs)
    s = world.students[0]
    enter_student_marks(admin, exam_id, world, configs, s, {"math": (62, 18), "eng": (70,)})
    save_marks(admin, exam_id, cmap["sci"], [mark_row(s["id"], comp_by_name(cmap["sci"], "Written"), None, absent=True)])
    assert admin.post(f"/exams/{exam_id}/compute").status_code == 200
    row = results(admin, exam_id)[0]
    subs = sub_by_name(world, row)
    sci = subs["sci"]
    assert sci["is_absent"] is True and sci["grade_label"] == "ABS"
    assert sci["max_marks"] is None and sci["percentage"] is None
    assert float(sci["marks_obtained"]) == 0 and sci["is_passed"] is False
    assert float(sci["gpa"]) == 0
    assert (row["total_marks_obtained"], row["total_max_marks"], row["percentage"], row["grade_label"], row["is_passed"]) == (
        "150.00", "200.00", "75.00", "B", False,
    )


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A04")
def test_recompute_without_force_conflicts(admin, rc):
    response = admin.post(f"/exams/{rc['id']}/compute")
    assert response.status_code == 409
    assert response.json()["detail"] == "Results already computed. Pass force=true to recompute."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A05")
def test_force_recompute_reflects_changes(admin, world, rc):
    cmap = config_map(world, rc["configs"])
    s3 = world.students[2]
    save_marks(admin, rc["id"], cmap["eng"], [mark_row(s3["id"], comp_by_name(cmap["eng"], "Written"), 100)])
    response = admin.post(f"/exams/{rc['id']}/compute", params={"force": "true"})
    assert response.status_code == 200 and response.json()["students_computed"] == 3
    rows = results(admin, rc["id"])
    assert len(rows) == 3
    by_id = {r["student_id"]: r for r in rows}
    assert by_id[s3["id"]]["total_marks_obtained"] == "200.00"
    assert by_id[s3["id"]]["percentage"] == "66.67"
    assert by_id[s3["id"]]["is_passed"] is True
    assert by_id[world.students[0]["id"]]["rank"] == 2 and by_id[s3["id"]]["rank"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A06")
def test_compute_without_marks(admin, world, cleanup):
    exam_id = create_exam(admin, cleanup, world)
    response = admin.post(f"/exams/{exam_id}/compute")
    assert response.status_code == 200 and response.json()["students_computed"] == 0
    assert results(admin, exam_id) == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A07")
def test_compute_without_subject_configs(admin, rx, cleanup):
    clone = admin.post(f"/exams/{rx['id']}/clone", json={})
    assert clone.status_code == 201
    cleanup.add(remove_exam, admin, clone.json()["id"])
    response = admin.post(f"/exams/{clone.json()['id']}/compute")
    assert response.status_code == 422
    assert response.json()["detail"] == "No subject configs found for this exam."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A08")
def test_compute_unknown_exam(admin):
    assert admin.post(f"/exams/{new_uuid()}/compute").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A09")
def test_compute_on_published_and_draft(admin, rx):
    assert admin.post(f"/exams/{rx['id']}/deactivate").status_code == 200
    assert admin.post(f"/exams/{rx['id']}/compute").status_code == 200
    assert admin.get(f"/exams/{rx['id']}").json()["status"] == "draft"
    admin.post(f"/exams/{rx['id']}/activate")
    admin.post(f"/exams/{rx['id']}/publish")
    assert admin.post(f"/exams/{rx['id']}/compute", params={"force": "true"}).status_code == 200
    assert admin.get(f"/exams/{rx['id']}").json()["status"] == "published"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A10")
def test_compute_writes_audit(admin, rc):
    row = next(r for r in audit_actions(admin, rc["id"]) if r["action"] == "results_computed")
    assert row["metadata_"]["students_computed"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A11")
def test_compute_invalid_force(admin, rx):
    assert admin.post(f"/exams/{rx['id']}/compute", params={"force": "maybe"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A12")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_compute_denied(role_clients, admin, rx, role):
    assert role_clients[role].post(f"/exams/{rx['id']}/compute").status_code == 403
    assert results(admin, rx["id"]) == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A13")
def test_compute_unauthenticated(anon, rx):
    assert anon.post(f"/exams/{rx['id']}/compute").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A14")
def test_compute_tenant_isolation(tenant_b, admin, rx):
    assert tenant_b.post(f"/exams/{rx['id']}/compute").status_code == 404
    assert results(admin, rx["id"]) == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A15")
def test_compute_cschema_mismatch(foreign, rx):
    assert foreign.post(f"/exams/{rx['id']}/compute").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A16")
def test_compute_without_grade_scheme(admin, world, cleanup):
    payload = exam_payload(world)
    payload["exam"]["exam_grade_scheme_id"] = None
    response = admin.post("/exams", json=payload)
    assert response.status_code == 201, response.text
    exam_id = response.json()["exam_id"]
    cleanup.add(remove_exam, admin, exam_id)
    configs = get_configs(admin, exam_id)
    standard_marks(admin, exam_id, world, configs, count=1)
    assert admin.post(f"/exams/{exam_id}/compute").status_code == 200
    row = results(admin, exam_id)[0]
    assert row["grade_label"] is None and row["is_passed"] is False
    assert all(s["grade_label"] == "ABS" and s["is_passed"] is False for s in row["subject_results"])


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A17")
def test_subject_scheme_pass_threshold(admin, world, cleanup):
    scheme = create_subject_scheme(
        admin, cleanup, spec=[(0, 32.99, "F", 0.0, False), (33, 100, "P", 1.0, True)]
    )
    payload = exam_payload(world)
    for cfg in payload["subject_configs"]:
        if cfg["subject_id"] == world.subjects["sci"]:
            cfg["subject_grade_scheme_id"] = scheme["id"]
    response = admin.post("/exams", json=payload)
    assert response.status_code == 201, response.text
    exam_id = response.json()["exam_id"]
    cleanup.add(remove_exam, admin, exam_id)
    configs = get_configs(admin, exam_id)
    enter_student_marks(admin, exam_id, world, configs, world.students[0], {"math": (62, 18), "sci": (33,), "eng": (70,)})
    assert admin.post(f"/exams/{exam_id}/compute").status_code == 200
    row = results(admin, exam_id)[0]
    sci = sub_by_name(world, row)["sci"]
    assert sci["grade_label"] == "P" and sci["is_passed"] is True
    assert row["is_passed"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A18")
def test_tied_students_get_distinct_ranks(admin, world, cleanup):
    exam_id = create_exam(admin, cleanup, world)
    configs = get_configs(admin, exam_id)
    from api_tests.exam.helpers import S1_MARKS, S2_MARKS, S3_MARKS

    enter_student_marks(admin, exam_id, world, configs, world.students[0], S2_MARKS)
    enter_student_marks(admin, exam_id, world, configs, world.students[1], S1_MARKS)
    enter_student_marks(admin, exam_id, world, configs, world.students[2], S1_MARKS)
    assert admin.post(f"/exams/{exam_id}/compute").status_code == 200
    rows = results(admin, exam_id)
    ranks = {r["student_id"]: r["rank"] for r in rows}
    assert ranks[world.students[0]["id"]] == 1
    assert sorted([ranks[world.students[1]["id"]], ranks[world.students[2]["id"]]]) == [2, 3]
    assert len(set(ranks.values())) == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-15-A19")
@pytest.mark.xfail(strict=True, reason="KG-5: compute applies every section's subject configs to every student, creating ABS rows and failing students of multi-section exams")
def test_multi_section_exam_computes_only_own_subjects(admin, world, cleanup):
    exam_id = create_exam(admin, cleanup, world, sections=("a", "c"))
    configs = get_configs(admin, exam_id)
    standard_marks(admin, exam_id, world, configs, count=1)
    assert admin.post(f"/exams/{exam_id}/compute").status_code == 200
    row = results(admin, exam_id)[0]
    assert len(row["subject_results"]) == 3
    assert row["is_passed"] is True
    assert row["percentage"] == "80.00"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A01")
def test_publish_active_exam(admin, rc):
    response = admin.post(f"/exams/{rc['id']}/publish")
    assert response.status_code == 200
    assert response.json() == {"exam_id": rc["id"], "status": "published", "published_at": None}
    assert admin.get(f"/exams/{rc['id']}").json()["status"] == "published"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A02")
@pytest.mark.skip(reason="locked and finalized exams cannot be produced through the API and the database must not be touched directly")
def test_publish_locked_and_finalized():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A03")
def test_publish_draft_conflicts(admin, rx):
    admin.post(f"/exams/{rx['id']}/deactivate")
    response = admin.post(f"/exams/{rx['id']}/publish")
    assert response.status_code == 409
    assert response.json()["detail"] == "Exam status 'draft' cannot be published. Must be locked or active."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A04")
def test_publish_twice_conflicts(admin, rx):
    assert admin.post(f"/exams/{rx['id']}/publish").status_code == 200
    assert admin.post(f"/exams/{rx['id']}/publish").status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A05")
def test_publish_before_compute(admin, rx):
    assert admin.post(f"/exams/{rx['id']}/publish").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A06")
def test_publish_unknown_exam(admin):
    assert admin.post(f"/exams/{new_uuid()}/publish").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A07")
def test_publish_writes_audit(admin, rc):
    admin.post(f"/exams/{rc['id']}/publish")
    actions = [r["action"] for r in audit_actions(admin, rc["id"])]
    assert actions[0] == "results_published" and "results_computed" in actions


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A08")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_publish_denied(role_clients, admin, rx, role):
    assert role_clients[role].post(f"/exams/{rx['id']}/publish").status_code == 403
    assert admin.get(f"/exams/{rx['id']}").json()["status"] == "active"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A09")
def test_list_results_shape_and_order(admin, world, rc):
    rows = results(admin, rc["id"])
    assert [r["rank"] for r in rows] == [1, 2, 3]
    for key in ("id", "exam_id", "student_id", "student_name", "admission_number", "total_marks_obtained", "total_max_marks", "percentage", "grade_label", "gpa", "rank", "is_passed", "computed_at", "subject_results"):
        assert key in rows[0]
    for key in ("subject_config_id", "subject_name", "marks_obtained", "max_marks", "percentage", "grade_label", "gpa", "remark_grade", "is_absent", "is_passed"):
        assert key in rows[0]["subject_results"][0]
    assert isinstance(rows[0]["percentage"], str)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A10")
def test_filter_by_student(admin, world, rc):
    rows = results(admin, rc["id"], student_id=world.students[0]["id"])
    assert [r["student_id"] for r in rows] == [world.students[0]["id"]]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A11")
def test_filter_by_class_and_section(admin, world, rc):
    rows = results(admin, rc["id"], class_id=world.class_id, section_id=world.sections["a"])
    assert len(rows) == 3
    assert results(admin, rc["id"], class_id=world.class_id, section_id=world.sections["b"]) == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A12")
def test_filter_by_class_only(admin, world, rc):
    assert len(results(admin, rc["id"], class_id=world.class_id)) == 3
    assert results(admin, rc["id"], class_id=new_uuid()) == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A13")
def test_results_uncomputed_and_unknown_exam(admin, rx):
    assert results(admin, rx["id"]) == []
    assert results(admin, new_uuid()) == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A14")
def test_results_visible_before_publish_to_staff(admin, rc):
    assert admin.get(f"/exams/{rc['id']}").json()["status"] == "active"
    assert len(results(admin, rc["id"])) == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A15")
@pytest.mark.parametrize("role", ["student", "parent"])
def test_student_parent_cannot_list_all_results(role_clients, rc, role):
    assert role_clients[role].get(f"/exams/{rc['id']}/results").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A16")
def test_single_result(admin, world, rc):
    s1 = world.students[0]
    response = admin.get(f"/exams/{rc['id']}/results/{s1['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["rank"] == 2 and body["percentage"] == "80.00"
    inverse = [s["subject_name"].replace(world.tag, "") for s in body["subject_results"]]
    assert inverse == ["math", "sci", "eng"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A17")
def test_single_result_missing(admin, world, rx):
    s = world.students[0]
    response = admin.get(f"/exams/{rx['id']}/results/{s['id']}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"No result found for student {s['id']} in exam {rx['id']}"
    assert admin.get(f"/exams/{rx['id']}/results/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A18")
@pytest.mark.parametrize("role", ["admin", "teacher", "staff"])
def test_staff_roles_read_results(role_clients, world, rc, role):
    assert role_clients[role].get(f"/exams/{rc['id']}/results").status_code == 200
    assert role_clients[role].get(f"/exams/{rc['id']}/results/{world.students[0]['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A19")
def test_results_unauthenticated(anon, world, rx):
    assert anon.get(f"/exams/{rx['id']}/results").status_code == 401
    assert anon.get(f"/exams/{rx['id']}/results/{world.students[0]['id']}").status_code == 401
    assert anon.post(f"/exams/{rx['id']}/publish").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A20")
def test_results_tenant_isolation(tenant_b, world, rc):
    assert tenant_b.get(f"/exams/{rc['id']}/results").json() == []
    assert tenant_b.get(f"/exams/{rc['id']}/results/{world.students[0]['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A21")
def test_results_cschema_mismatch(foreign, rc):
    assert foreign.get(f"/exams/{rc['id']}/results").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A22")
def test_publish_rank_flag_ignored(admin, rc):
    assert admin.put(f"/exams/{rc['id']}", json={"publish_rank": False}).status_code == 200
    admin.post(f"/exams/{rc['id']}/publish")
    rows = results(admin, rc["id"])
    assert [r["rank"] for r in rows] == [1, 2, 3]
