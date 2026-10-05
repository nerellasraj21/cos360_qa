import pytest

from api_tests.exam.conftest import PASSWORD, World
from api_tests.support import QA_B_TENANT, Api
from api_tests.exam.helpers import (
    audit_actions,
    create_exam,
    enter_student_marks,
    get_configs,
    new_uuid,
    standard_marks,
    S1_MARKS,
    S2_MARKS,
    config_map,
    comp_by_name,
    mark_row,
    save_marks,
)

D6 = "DEF-EXM-6: Student role has no exam_results:read_own (permission catalog and Full plan omit exam_results), so GET /exams/{id}/my-result returns 403 permission_denied for every student"
KG2 = "KG-2: GET /exams/my-results is shadowed by GET /exams/{exam_id} and returns 422"


@pytest.fixture
def mx(admin, world, cleanup):
    exam_id = create_exam(admin, cleanup, world)
    configs = get_configs(admin, exam_id)
    enter_student_marks(admin, exam_id, world, configs, world.students[0], S1_MARKS)
    enter_student_marks(admin, exam_id, world, configs, world.students[1], S2_MARKS)
    return {"id": exam_id, "configs": configs}


@pytest.fixture
def mp(admin, mx):
    assert admin.post(f"/exams/{mx['id']}/compute").status_code == 200
    assert admin.post(f"/exams/{mx['id']}/publish").status_code == 200
    return mx


def subject_map(world, view):
    return {s["subject_name"].replace(world.tag, ""): s for s in view["subjects"]}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A01")
def test_my_marks_for_student(world, mx):
    me = world.student_api(0)
    response = me.get(f"/exams/{mx['id']}/my-marks")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["exam_id"] == mx["id"] and body["student_id"] == world.students[0]["id"]
    assert body["student_name"]
    subs = subject_map(world, body)
    assert set(subs) == {"math", "sci", "eng"}
    math = {c["component_name"]: c for c in subs["math"]["components"]}
    assert math["Written"]["marks_obtained"] == "62.00" and math["Written"]["max_marks"] == "80.00"
    assert math["Oral"]["marks_obtained"] == "18.00"
    assert [c["component_name"] for c in subs["math"]["components"]] == ["Written", "Oral"]
    assert body["subjects"][0]["subject_name"].endswith("math")


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A02")
def test_my_marks_only_own(world, mx):
    one = world.student_api(0).get(f"/exams/{mx['id']}/my-marks").json()
    two = world.student_api(1).get(f"/exams/{mx['id']}/my-marks").json()
    assert one["student_id"] == world.students[0]["id"] and two["student_id"] == world.students[1]["id"]
    sci_one = subject_map(world, one)["sci"]["components"][0]["marks_obtained"]
    sci_two = subject_map(world, two)["sci"]["components"][0]["marks_obtained"]
    assert (sci_one, sci_two) == ("90.00", "95.00")


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A03")
def test_my_marks_without_marks(world, mx):
    response = world.student_api(2).get(f"/exams/{mx['id']}/my-marks")
    assert response.status_code == 200
    assert response.json()["subjects"] == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A04")
@pytest.mark.parametrize("role", ["admin", "teacher", "staff", "parent"])
def test_my_marks_requires_student_identity(role_clients, mx, role):
    response = role_clients[role].get(f"/exams/{mx['id']}/my-marks")
    assert response.status_code == 400
    assert response.json()["detail"] == "Only students can access this endpoint"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A05")
def test_my_marks_unknown_exam(world):
    response = world.student_api(0).get(f"/exams/{new_uuid()}/my-marks")
    assert response.status_code == 200 and response.json()["subjects"] == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A06")
def test_child_marks_for_linked_child(world, mx):
    parent = world.parent_api(0)
    response = parent.get(f"/exams/{mx['id']}/child-marks/{world.students[0]['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["student_id"] == world.students[0]["id"]
    assert len(response.json()["subjects"]) == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A07")
def test_child_marks_for_unlinked_student(world, mx):
    parent = world.parent_api(0)
    response = parent.get(f"/exams/{mx['id']}/child-marks/{world.students[1]['id']}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot access marks for unrelated student"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A08")
def test_child_marks_requires_parent_identity(admin, world, mx):
    sid = world.students[0]["id"]
    for client in (world.student_api(0), admin):
        response = client.get(f"/exams/{mx['id']}/child-marks/{sid}")
        assert response.status_code == 400
        assert response.json()["detail"] == "Only parents can access this endpoint"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A09")
@pytest.mark.xfail(strict=True, reason=D6)
def test_my_result_after_publish(world, mp):
    response = world.student_api(0).get(f"/exams/{mp['id']}/my-result")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["student_id"] == world.students[0]["id"]
    assert (body["total_marks_obtained"], body["percentage"], body["grade_label"], body["gpa"], body["rank"]) == (
        "240.00", "80.00", "A", "3.50", 2,
    )
    assert len(body["subject_results"]) == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A10")
@pytest.mark.xfail(strict=True, reason=D6)
def test_my_result_before_publish(admin, world, mx):
    assert admin.post(f"/exams/{mx['id']}/compute").status_code == 200
    response = world.student_api(0).get(f"/exams/{mx['id']}/my-result")
    assert response.status_code == 403
    assert response.json()["detail"] == "Results are not yet published for this exam."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A11")
@pytest.mark.xfail(strict=True, reason=D6)
def test_my_result_published_without_row(world, mp):
    response = world.student_api(2).get(f"/exams/{mp['id']}/my-result")
    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A12")
@pytest.mark.parametrize("role", ["admin", "teacher", "staff", "parent"])
def test_my_result_denied_for_non_students(role_clients, mp, role):
    assert role_clients[role].get(f"/exams/{mp['id']}/my-result").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A13")
def test_child_result_published(world, mp):
    response = world.parent_api(0).get(f"/exams/{mp['id']}/child-result/{world.students[0]['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["student_id"] == world.students[0]["id"]
    assert response.json()["percentage"] == "80.00"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A14")
def test_child_result_before_publish(admin, world, mx):
    admin.post(f"/exams/{mx['id']}/compute")
    response = world.parent_api(0).get(f"/exams/{mx['id']}/child-result/{world.students[0]['id']}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Results are not yet published for this exam."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A15")
def test_child_result_unlinked(world, mp):
    response = world.parent_api(0).get(f"/exams/{mp['id']}/child-result/{world.students[1]['id']}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot access results for unrelated student"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A16")
def test_child_result_requires_parent_identity(admin, world, mp):
    sid = world.students[0]["id"]
    for client in (world.student_api(0), admin):
        response = client.get(f"/exams/{mp['id']}/child-result/{sid}")
        assert response.status_code == 400
        assert response.json()["detail"] == "Only parents can access this endpoint"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A17")
@pytest.mark.xfail(strict=True, reason=D6)
def test_my_results_list_for_student(world, mp):
    response = world.student_api(0).get("/exams/my-results")
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A18")
@pytest.mark.xfail(strict=True, reason=D6)
def test_my_results_list_only_published(admin, world, mp, cleanup):
    other = create_exam(admin, cleanup, world)
    enter_student_marks(admin, other, world, get_configs(admin, other), world.students[0], S1_MARKS)
    admin.post(f"/exams/{other}/compute")
    response = world.student_api(0).get("/exams/my-results")
    assert response.status_code == 200
    ids = {r["exam_id"] for r in response.json()}
    assert mp["id"] in ids and other not in ids


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A19")
def test_my_results_list_denied_for_admin_and_parent(admin, world):
    assert admin.get("/exams/my-results").status_code == 403
    assert world.parent_api(0).get("/exams/my-results").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A20")
@pytest.mark.xfail(strict=True, reason=D6)
def test_unlock_hides_result_again(admin, world, mp):
    me = world.student_api(0)
    assert me.get(f"/exams/{mp['id']}/my-result").status_code == 200
    assert admin.post(f"/exams/{mp['id']}/unlock", json={"reason": "fix"}).status_code == 200
    assert me.get(f"/exams/{mp['id']}/my-result").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A21")
def test_my_views_unauthenticated(anon, world, mx):
    e = mx["id"]
    sid = world.students[0]["id"]
    assert anon.get(f"/exams/{e}/my-marks").status_code == 401
    assert anon.get(f"/exams/{e}/child-marks/{sid}").status_code == 401
    assert anon.get(f"/exams/{e}/my-result").status_code == 401
    assert anon.get(f"/exams/{e}/child-result/{sid}").status_code == 401
    assert anon.get("/exams/my-results").status_code in (401, 422)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A22")
def test_student_of_other_tenant(tenant_b, admin, mp, logins):
    wb = World(tenant_b, tenant_b.academic_year_id)
    try:
        wb.build(student_count=1)
        s = wb.students[0]
        anon = Api(tenant_header=QA_B_TENANT)
        try:
            login_response = anon.post(
                "/auth/login",
                json={"username": s["admission_number"], "password": "student@123", "academic_year_id": tenant_b.academic_year_id},
            )
            assert login_response.status_code == 200, login_response.text
            data = login_response.json()
            token = data.get("change_password_token")
            if token:
                done = anon.post(
                    "/auth/staff/set-password",
                    json={"change_password_token": token, "new_password": PASSWORD, "confirm_password": PASSWORD},
                )
                assert done.status_code == 200, done.text
                data = done.json()
        finally:
            anon.close()
        me = Api(token=data["access_token"])
        try:
            marks = me.get(f"/exams/{mp['id']}/my-marks")
            assert marks.status_code == 200 and marks.json()["subjects"] == []
            assert me.get(f"/exams/{mp['id']}/my-result").status_code in (403, 404)
        finally:
            me.close()
    finally:
        wb.teardown()


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A23")
def test_my_views_cschema_mismatch(world, mp):
    from api_tests.support import Api

    mine = world.student_api(0)
    foreign = Api(token=mine.token, tenant_header="qa_school_b")
    try:
        assert foreign.get(f"/exams/{mp['id']}/my-marks").status_code == 403
        assert foreign.get(f"/exams/{mp['id']}/my-result").status_code == 403
    finally:
        foreign.close()


@pytest.mark.api
@pytest.mark.tc("TC-EXM-17-A24")
@pytest.mark.xfail(strict=True, reason=D6)
def test_republished_exam_shows_recomputed_values(admin, world, mp):
    me = world.student_api(0)
    admin.post(f"/exams/{mp['id']}/unlock", json={"reason": "fix"})
    cmap = config_map(world, mp["configs"])
    save_marks(admin, mp["id"], cmap["eng"], [mark_row(world.students[0]["id"], comp_by_name(cmap["eng"], "Written"), 100)])
    assert admin.post(f"/exams/{mp['id']}/compute", params={"force": "true"}).status_code == 200
    assert admin.post(f"/exams/{mp['id']}/publish").status_code == 200
    body = me.get(f"/exams/{mp['id']}/my-result").json()
    assert body["total_marks_obtained"] == "270.00" and body["percentage"] == "90.00"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-16-A15")
def test_student_cannot_read_other_students_result(admin, world, mx):
    assert admin.post(f"/exams/{mx['id']}/compute").status_code == 200
    me = world.student_api(0)
    assert me.get(f"/exams/{mx['id']}/results/{world.students[1]['id']}").status_code == 403
