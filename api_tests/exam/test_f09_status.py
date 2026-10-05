import pytest

from api_tests.exam.helpers import (
    ALL_ROLES,
    OTHER_ROLES,
    audit_actions,
    create_exam,
    exam_payload,
    get_configs,
    grid,
    new_uuid,
    remove_exam,
    save_marks,
    mark_row,
    standard_marks,
)
from api_tests.support import unique


def status_of(admin, exam_id):
    return admin.get(f"/exams/{exam_id}").json()["status"]


@pytest.fixture
def ex_computed(admin, world, cleanup):
    exam_id = create_exam(admin, cleanup, world)
    configs = get_configs(admin, exam_id)
    standard_marks(admin, exam_id, world, configs)
    assert admin.post(f"/exams/{exam_id}/compute").status_code == 200
    return {"id": exam_id, "configs": configs}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A01")
def test_update_exam_name_and_term(admin, world, ex1):
    before = admin.get(f"/exams/{ex1['id']}").json()
    new_name = unique("exm_v2_")
    response = admin.put(f"/exams/{ex1['id']}", json={"exam_name": new_name, "term": "Term 1"})
    assert response.status_code == 200, response.text
    after = admin.get(f"/exams/{ex1['id']}").json()
    assert after["exam_name"] == new_name and after["term"] == "Term 1"
    for key in ("board", "level", "exam_type", "nature", "exam_grade_scheme_id", "status", "academic_year_id"):
        assert after[key] == before[key]
    assert response.json()["exam_name"] == new_name


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A02")
def test_update_published_exam_allowed(admin, world, ex1):
    assert admin.post(f"/exams/{ex1['id']}/publish").status_code == 200
    response = admin.put(f"/exams/{ex1['id']}", json={"term": "T2"})
    assert response.status_code == 200
    assert admin.get(f"/exams/{ex1['id']}").json()["status"] == "published"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A03")
@pytest.mark.xfail(strict=True, reason="KG-10: PUT /exams/{id} with a duplicate exam name returns 500 instead of 409")
def test_update_duplicate_name(admin, world, cleanup):
    one = create_exam(admin, cleanup, world)
    two = create_exam(admin, cleanup, world)
    name = admin.get(f"/exams/{one}").json()["exam_name"]
    assert admin.put(f"/exams/{two}", json={"exam_name": name}).status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A04")
@pytest.mark.parametrize("body", [{"hall_ticket_min_attendance": 101}, {"exam_name": "x" * 151}])
def test_update_validation(admin, ex1, body):
    assert admin.put(f"/exams/{ex1['id']}", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A05")
def test_update_unknown_exam(admin):
    assert admin.put(f"/exams/{new_uuid()}", json={"term": "x"}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A06")
def test_update_ignores_other_fields(admin, ex1):
    before = admin.get(f"/exams/{ex1['id']}").json()
    response = admin.put(
        f"/exams/{ex1['id']}", json={"board": "CBSE", "level": "secondary", "exam_grade_scheme_id": new_uuid(), "term": "T9"}
    )
    assert response.status_code == 200
    after = admin.get(f"/exams/{ex1['id']}").json()
    assert after["board"] == before["board"] and after["level"] == before["level"]
    assert after["exam_grade_scheme_id"] == before["exam_grade_scheme_id"]
    assert after["term"] == "T9"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A07")
def test_clone_exam(admin, world, ex1, cleanup):
    source = admin.get(f"/exams/{ex1['id']}").json()
    response = admin.post(f"/exams/{ex1['id']}/clone", json={})
    assert response.status_code == 201, response.text
    clone = response.json()
    cleanup.add(remove_exam, admin, clone["id"])
    assert clone["status"] == "draft"
    assert clone["exam_name"] == f"Copy of {source['exam_name']}"
    assert clone["cloned_from_exam_id"] == ex1["id"]
    assert admin.get(f"/exams/{clone['id']}/class-sections").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A08")
def test_clone_ignores_body_name(admin, ex1, cleanup):
    source = admin.get(f"/exams/{ex1['id']}").json()
    response = admin.post(f"/exams/{ex1['id']}/clone", json={"new_name": "Custom"})
    assert response.status_code == 201
    cleanup.add(remove_exam, admin, response.json()["id"])
    assert response.json()["exam_name"] == f"Copy of {source['exam_name']}"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A09")
def test_clone_twice_conflicts(admin, ex1, cleanup):
    first = admin.post(f"/exams/{ex1['id']}/clone", json={})
    assert first.status_code == 201
    cleanup.add(remove_exam, admin, first.json()["id"])
    assert admin.post(f"/exams/{ex1['id']}/clone", json={}).status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A10")
def test_clone_unknown(admin):
    assert admin.post(f"/exams/{new_uuid()}/clone", json={}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A11")
def test_activate_draft(admin, ex1):
    assert admin.post(f"/exams/{ex1['id']}/deactivate").status_code == 200
    response = admin.post(f"/exams/{ex1['id']}/activate")
    assert response.status_code == 200
    assert response.json() == {"exam_id": ex1["id"], "status": "active"}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A12")
def test_activate_active_conflicts(admin, ex1):
    assert admin.post(f"/exams/{ex1['id']}/activate").status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A13")
def test_deactivate_active(admin, ex1):
    response = admin.post(f"/exams/{ex1['id']}/deactivate")
    assert response.status_code == 200
    assert response.json() == {"exam_id": ex1["id"], "status": "draft"}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A14")
def test_deactivate_draft_conflicts(admin, ex1):
    admin.post(f"/exams/{ex1['id']}/deactivate")
    assert admin.post(f"/exams/{ex1['id']}/deactivate").status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A15")
def test_unlock_published_keeps_results_and_audits(admin, ex_computed):
    e = ex_computed["id"]
    assert admin.post(f"/exams/{e}/publish").status_code == 200
    response = admin.post(f"/exams/{e}/unlock", json={"reason": "Marks fix"})
    assert response.status_code == 200
    assert response.json() == {"exam_id": e, "status": "active", "reason": "Marks fix"}
    assert status_of(admin, e) == "active"
    assert len(admin.get(f"/exams/{e}/results").json()) == 3
    row = next(r for r in audit_actions(admin, e) if r["action"] == "exam_unlocked")
    assert row["reason"] == "Marks fix"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A16")
def test_unlock_draft_or_active_conflicts(admin, ex1):
    assert admin.post(f"/exams/{ex1['id']}/unlock", json={"reason": "x"}).status_code == 409
    admin.post(f"/exams/{ex1['id']}/deactivate")
    assert admin.post(f"/exams/{ex1['id']}/unlock", json={"reason": "x"}).status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A17")
def test_unlock_requires_reason(admin, ex1):
    admin.post(f"/exams/{ex1['id']}/publish")
    assert admin.post(f"/exams/{ex1['id']}/unlock").status_code == 422
    assert admin.post(f"/exams/{ex1['id']}/unlock", json={}).status_code == 422
    assert status_of(admin, ex1["id"]) == "published"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A18")
@pytest.mark.xfail(strict=True, reason="DEF-EXM-5: POST /exams/{id}/unlock with a reason over 300 characters returns 500 (column limit) instead of 422")
def test_unlock_reason_too_long(admin, ex1):
    admin.post(f"/exams/{ex1['id']}/publish")
    response = admin.post(f"/exams/{ex1['id']}/unlock", json={"reason": "r" * 301})
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A19")
def test_delete_cascades_marks_and_results(admin, world, ex_computed):
    e = ex_computed["id"]
    assert len(admin.get(f"/exams/{e}/results").json()) == 3
    assert admin.delete(f"/exams/{e}").status_code == 204
    assert admin.get(f"/exams/{e}").status_code == 404
    assert admin.get(f"/exams/{e}/results").json() == []
    cfg = ex_computed["configs"][0]
    rows = grid(admin, e, world, cfg).json()
    assert all(not r["marks"] for r in rows)
    deleted = next(r for r in audit_actions(admin, e) if r["action"] == "exam_deleted")
    assert deleted["old_value"] == "active"
    meta = deleted["metadata_"]
    assert meta["marks_deleted"] == 12
    assert meta["subject_results_deleted"] == 9
    assert meta["exam_results_deleted"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A19")
def test_delete_draft_exam_with_marks(admin, world, cleanup):
    e = create_exam(admin, cleanup, world)
    configs = get_configs(admin, e)
    standard_marks(admin, e, world, configs, count=1)
    admin.post(f"/exams/{e}/compute")
    assert admin.post(f"/exams/{e}/deactivate").status_code == 200
    assert admin.delete(f"/exams/{e}").status_code == 204
    assert admin.get(f"/exams/{e}").status_code == 404
    assert admin.get(f"/exams/{e}/results").json() == []
    deleted = next(r for r in audit_actions(admin, e) if r["action"] == "exam_deleted")
    assert deleted["old_value"] == "draft"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A20")
def test_delete_active_exam(admin, world, cleanup):
    e = create_exam(admin, cleanup, world)
    assert admin.delete(f"/exams/{e}").status_code == 204


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A21")
def test_delete_published_exam_conflicts(admin, ex1):
    admin.post(f"/exams/{ex1['id']}/publish")
    response = admin.delete(f"/exams/{ex1['id']}")
    assert response.status_code == 409
    assert "cannot be deleted because it is published" in response.json()["detail"]
    assert status_of(admin, ex1["id"]) == "published"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A22")
def test_delete_unknown_exam(admin):
    assert admin.delete(f"/exams/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A23")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_lifecycle_write_denied(role_clients, ex1, role):
    client = role_clients[role]
    e = ex1["id"]
    assert client.put(f"/exams/{e}", json={"term": "x"}).status_code == 403
    assert client.post(f"/exams/{e}/activate").status_code == 403
    assert client.post(f"/exams/{e}/deactivate").status_code == 403
    assert client.post(f"/exams/{e}/unlock", json={"reason": "x"}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A24")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_clone_and_delete_denied(role_clients, admin, ex1, role):
    client = role_clients[role]
    e = ex1["id"]
    assert client.post(f"/exams/{e}/clone", json={}).status_code == 403
    assert client.delete(f"/exams/{e}").status_code == 403
    assert status_of(admin, e) == "active"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A25")
def test_unauthenticated(anon, ex1):
    e = ex1["id"]
    assert anon.put(f"/exams/{e}", json={"term": "x"}).status_code == 401
    assert anon.delete(f"/exams/{e}").status_code == 401
    assert anon.post(f"/exams/{e}/clone", json={}).status_code == 401
    assert anon.post(f"/exams/{e}/activate").status_code == 401
    assert anon.post(f"/exams/{e}/deactivate").status_code == 401
    assert anon.post(f"/exams/{e}/unlock", json={"reason": "x"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A26")
def test_tenant_isolation(admin, tenant_b, ex1):
    e = ex1["id"]
    assert tenant_b.delete(f"/exams/{e}").status_code == 404
    assert tenant_b.post(f"/exams/{e}/activate").status_code == 404
    assert tenant_b.post(f"/exams/{e}/clone", json={}).status_code == 404
    assert tenant_b.put(f"/exams/{e}", json={"term": "x"}).status_code == 404
    assert status_of(admin, e) == "active"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A27")
def test_cschema_mismatch(foreign, ex1):
    assert foreign.delete(f"/exams/{ex1['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A28")
def test_audit_survives_delete(admin, world, cleanup):
    e = create_exam(admin, cleanup, world)
    assert admin.delete(f"/exams/{e}").status_code == 204
    actions = [r["action"] for r in audit_actions(admin, e)]
    assert "exam_deleted" in actions


STATUS_SETUP = {
    "draft": lambda admin, e: admin.post(f"/exams/{e}/deactivate"),
    "active": lambda admin, e: None,
    "published": lambda admin, e: admin.post(f"/exams/{e}/publish"),
}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A29")
@pytest.mark.parametrize("state", ["draft", "active", "published"])
def test_status_matrix(admin, world, cleanup, state):
    e = create_exam(admin, cleanup, world)
    configs = get_configs(admin, e)
    STATUS_SETUP[state](admin, e)
    assert status_of(admin, e) == state
    assert admin.put(f"/exams/{e}", json={"term": "M"}).status_code == 200
    section = admin.post(f"/exams/{e}/class-sections", json={"class_id": world.class_id, "section_id": world.sections["b"]})
    assert section.status_code == (409 if state == "published" else 201)
    cfg = configs[0]
    comp = cfg["components"][0]
    saved = save_marks(admin, e, cfg, [mark_row(world.students[0]["id"], comp, 10)])
    assert saved.status_code == 200
    assert admin.post(f"/exams/{e}/hall-tickets/compute").status_code == 200
    assert admin.post(f"/exams/{e}/compute", params={"force": "true"}).status_code == 200
    student = world.student_api(0)
    assert student.get(f"/exams/{e}/my-marks").status_code == 200
    if state != "published":
        assert student.get(f"/exams/{e}/my-result").status_code == 403
    publish = admin.post(f"/exams/{e}/publish")
    expected = {"draft": 409, "active": 200, "published": 409}[state]
    assert publish.status_code == expected
    if state == "published":
        assert admin.delete(f"/exams/{e}").status_code == 409
    else:
        assert status_of(admin, e) == ("published" if state == "active" else "draft")


@pytest.mark.api
@pytest.mark.tc("TC-EXM-09-A29")
@pytest.mark.xfail(strict=True, reason="DEF-EXM-6: Student role has no exam_results:read_own, so my-result returns 403 even for a published exam")
def test_published_state_student_sees_result(admin, world, cleanup):
    e = create_exam(admin, cleanup, world)
    configs = get_configs(admin, e)
    STATUS_SETUP["published"](admin, e)
    cfg = configs[0]
    comp = cfg["components"][0]
    save_marks(admin, e, cfg, [mark_row(world.students[0]["id"], comp, 10)])
    assert admin.post(f"/exams/{e}/compute", params={"force": "true"}).status_code == 200
    assert world.student_api(0).get(f"/exams/{e}/my-result").status_code == 200
