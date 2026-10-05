import pytest

from api_tests.exam.helpers import (
    ALL_ROLES,
    OTHER_ROLES,
    XLSX_TYPE,
    build_xlsx,
    config_map,
    grid,
    mark_row,
    new_uuid,
    save_marks,
)

KG1 = "KG-1: POST /exams/{id}/mark-permissions reads current_user['id'] (absent from real tokens) and returns 500"


def grant(admin, exam_id, user_id, note="n"):
    response = admin.post(f"/exams/{exam_id}/mark-permissions", json={"exam_id": exam_id, "user_id": user_id, "scope_note": note})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A01")
def test_grant_permission(admin, ex1, logins):
    data = grant(admin, ex1["id"], logins["teacher"]["user"]["id"])
    assert data["granted_by"] == logins["admin"]["user"]["id"]
    assert data["is_active"] is True and data["exam_id"] == ex1["id"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A02")
def test_grant_requires_exam_id(admin, ex1, logins):
    body = {"user_id": logins["teacher"]["user"]["id"], "scope_note": "n"}
    assert admin.post(f"/exams/{ex1['id']}/mark-permissions", json=body).status_code == 422
    assert admin.post(f"/exams/{ex1['id']}/mark-permissions", json={"exam_id": ex1["id"]}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A03")
def test_grant_twice_conflicts(admin, ex1, logins):
    uid = logins["teacher"]["user"]["id"]
    grant(admin, ex1["id"], uid)
    again = admin.post(f"/exams/{ex1['id']}/mark-permissions", json={"exam_id": ex1["id"], "user_id": uid})
    assert again.status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A04")
def test_revoke_then_regrant_reuses_row(admin, ex1, logins):
    uid = logins["teacher"]["user"]["id"]
    first = grant(admin, ex1["id"], uid)
    assert admin.put(f"/exams/{ex1['id']}/mark-permissions/{first['id']}", json={"is_active": False}).status_code == 200
    again = grant(admin, ex1["id"], uid)
    assert again["id"] == first["id"] and again["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A05")
def test_list_permissions_empty_for_new_exam(admin, ex1):
    response = admin.get(f"/exams/{ex1['id']}/mark-permissions")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A05")
def test_list_includes_active_and_revoked(admin, ex1, logins):
    uid = logins["teacher"]["user"]["id"]
    first = grant(admin, ex1["id"], uid)
    admin.delete(f"/exams/{ex1['id']}/mark-permissions/{first['id']}")
    rows = admin.get(f"/exams/{ex1['id']}/mark-permissions").json()
    assert [r["id"] for r in rows] == [first["id"]]
    assert rows[0]["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A06")
def test_update_permission_note_and_flag(admin, ex1, logins):
    first = grant(admin, ex1["id"], logins["teacher"]["user"]["id"])
    response = admin.put(f"/exams/{ex1['id']}/mark-permissions/{first['id']}", json={"is_active": False, "scope_note": "x"})
    assert response.status_code == 200
    assert response.json()["scope_note"] == "x" and response.json()["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A07")
def test_update_requires_is_active(admin, ex1):
    assert admin.put(f"/exams/{ex1['id']}/mark-permissions/{new_uuid()}", json={"scope_note": "x"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A08")
def test_update_unknown_permission(admin, ex1):
    missing = new_uuid()
    response = admin.put(f"/exams/{ex1['id']}/mark-permissions/{missing}", json={"is_active": False})
    assert response.status_code == 404
    assert response.json()["detail"] == f"ExamMarkEntryPermission with id {missing} not found"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A09")
def test_delete_is_soft(admin, ex1, logins):
    first = grant(admin, ex1["id"], logins["teacher"]["user"]["id"])
    assert admin.delete(f"/exams/{ex1['id']}/mark-permissions/{first['id']}").status_code == 204
    rows = admin.get(f"/exams/{ex1['id']}/mark-permissions").json()
    assert rows[0]["id"] == first["id"] and rows[0]["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A10")
def test_delete_unknown_permission(admin, ex1):
    assert admin.delete(f"/exams/{ex1['id']}/mark-permissions/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A11")
def test_delegation_blocks_other_users(admin, world, ex1, teacher, logins):
    grant(admin, ex1["id"], logins["teacher"]["user"]["id"])
    cfg = ex1["configs"][0]
    blocked = grid(admin, ex1["id"], world, cfg)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "You do not have mark entry permission for this exam"
    save = save_marks(admin, ex1["id"], cfg, [mark_row(world.students[0]["id"], cfg["components"][0], 5)])
    assert save.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A12")
def test_granted_user_can_enter_marks(admin, world, ex1, teacher, logins):
    grant(admin, ex1["id"], logins["teacher"]["user"]["id"])
    cfg = ex1["configs"][0]
    assert grid(teacher, ex1["id"], world, cfg).status_code == 200
    save = save_marks(teacher, ex1["id"], cfg, [mark_row(world.students[0]["id"], cfg["components"][0], 5)])
    assert save.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A13")
def test_revoking_only_grant_restores_open_access(admin, world, ex1, logins):
    first = grant(admin, ex1["id"], logins["teacher"]["user"]["id"])
    cfg = ex1["configs"][0]
    assert grid(admin, ex1["id"], world, cfg).status_code == 403
    admin.delete(f"/exams/{ex1['id']}/mark-permissions/{first['id']}")
    assert grid(admin, ex1["id"], world, cfg).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A14")
def test_template_and_upload_not_delegated(admin, world, ex1, logins):
    grant(admin, ex1["id"], logins["teacher"]["user"]["id"])
    cfg = ex1["configs"][0]
    params = {"class_id": world.class_id, "section_id": world.sections["a"], "subject_config_id": cfg["id"]}
    template = admin.get(f"/exams/{ex1['id']}/marks/template", params=params)
    assert template.status_code == 200
    assert template.headers["content-type"].startswith(XLSX_TYPE)
    upload = admin.post(
        f"/exams/{ex1['id']}/marks/upload",
        params=params,
        files={"file": ("m.xlsx", build_xlsx(["student_id"], []), XLSX_TYPE)},
    )
    assert upload.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A15")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_grant_and_update_denied(role_clients, ex1, logins, role):
    client = role_clients[role]
    body = {"exam_id": ex1["id"], "user_id": logins["teacher"]["user"]["id"]}
    assert client.post(f"/exams/{ex1['id']}/mark-permissions", json=body).status_code == 403
    assert client.put(f"/exams/{ex1['id']}/mark-permissions/{new_uuid()}", json={"is_active": False}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A16")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_revoke_denied(role_clients, ex1, role):
    assert role_clients[role].delete(f"/exams/{ex1['id']}/mark-permissions/{new_uuid()}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A17")
@pytest.mark.parametrize("role", ALL_ROLES)
def test_list_all_roles(role_clients, ex1, role):
    assert role_clients[role].get(f"/exams/{ex1['id']}/mark-permissions").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A18")
def test_unauthenticated(anon, ex1, logins):
    e = ex1["id"]
    body = {"exam_id": e, "user_id": logins["teacher"]["user"]["id"]}
    assert anon.get(f"/exams/{e}/mark-permissions").status_code == 401
    assert anon.post(f"/exams/{e}/mark-permissions", json=body).status_code == 401
    assert anon.put(f"/exams/{e}/mark-permissions/{new_uuid()}", json={"is_active": False}).status_code == 401
    assert anon.delete(f"/exams/{e}/mark-permissions/{new_uuid()}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A19")
def test_tenant_isolation(tenant_b, ex1):
    e = ex1["id"]
    assert tenant_b.get(f"/exams/{e}/mark-permissions").json() == []
    assert tenant_b.put(f"/exams/{e}/mark-permissions/{new_uuid()}", json={"is_active": False}).status_code == 404
    assert tenant_b.delete(f"/exams/{e}/mark-permissions/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-10-A20")
def test_cschema_mismatch(foreign, ex1, logins):
    body = {"exam_id": ex1["id"], "user_id": logins["teacher"]["user"]["id"]}
    assert foreign.post(f"/exams/{ex1['id']}/mark-permissions", json=body).status_code == 403
