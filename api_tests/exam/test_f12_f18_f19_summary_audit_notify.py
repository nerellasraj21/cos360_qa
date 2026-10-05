import pytest

from api_tests.exam.helpers import ALL_ROLES, OTHER_ROLES, audit_actions, create_exam, get_configs, new_uuid

TARGET_403 = "KG-3: Student and Parent hold exams:read and can read any exam's audit log"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-12-A01")
@pytest.mark.parametrize("role", ["teacher", "staff"])
def test_summary_data_for_staff_roles(role_clients, world, ex1, role):
    client = role_clients[role]
    sections = client.get(f"/exams/{ex1['id']}/class-sections")
    configs = client.get(f"/exams/{ex1['id']}/subject-configs")
    assert sections.status_code == 200 and configs.status_code == 200
    assert len(sections.json()) == 1
    assert len(configs.json()) == 3
    totals = []
    for cfg in configs.json():
        totals.append(sum(float(c["max_marks"]) for c in cfg["components"] if c["include_in_total"] and c["entry_type"] == "marks"))
    assert totals == [100.0, 100.0, 100.0]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-12-A02")
def test_summary_data_readable_by_student(role_clients, ex1):
    assert role_clients["student"].get(f"/exams/{ex1['id']}/class-sections").status_code == 200
    assert role_clients["student"].get(f"/exams/{ex1['id']}/subject-configs").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-12-A03")
def test_summary_data_tenant_isolation(tenant_b, ex1):
    assert tenant_b.get(f"/exams/{ex1['id']}/class-sections").status_code == 404
    assert tenant_b.get(f"/exams/{ex1['id']}/subject-configs").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A01")
def test_audit_after_compute_and_publish(admin, world, ex1, logins):
    from api_tests.exam.helpers import standard_marks

    standard_marks(admin, ex1["id"], world, ex1["configs"])
    admin.post(f"/exams/{ex1['id']}/compute")
    admin.post(f"/exams/{ex1['id']}/publish")
    rows = audit_actions(admin, ex1["id"])
    assert [r["action"] for r in rows[:2]] == ["results_published", "results_computed"]
    for r in rows[:2]:
        assert r["performed_by"] == logins["admin"]["user"]["id"] and r["performed_at"]
    assert rows[0]["performed_at"] >= rows[1]["performed_at"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A02")
def test_audit_after_unlock(admin, ex1):
    admin.post(f"/exams/{ex1['id']}/publish")
    admin.post(f"/exams/{ex1['id']}/unlock", json={"reason": "Marks fix"})
    row = next(r for r in audit_actions(admin, ex1["id"]) if r["action"] == "exam_unlocked")
    assert row["reason"] == "Marks fix"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A03")
def test_audit_after_hall_ticket_actions(admin, world, ex1):
    assert admin.post(f"/exams/{ex1['id']}/hall-tickets/compute").status_code == 200
    s = world.students[0]
    assert admin.put(f"/exams/{ex1['id']}/hall-tickets/{s['id']}/override", json={"attendance_override": True}).status_code == 200
    assert admin.post(f"/exams/{ex1['id']}/hall-tickets/publish").status_code == 200
    rows = {r["action"]: r for r in audit_actions(admin, ex1["id"])}
    assert rows["hall_tickets_computed"]["metadata_"]["total_students"] == 3
    assert rows["eligibility_overridden"]["student_id"] == s["id"]
    assert "final_eligible" in rows["eligibility_overridden"]["metadata_"]
    assert "hall_tickets_published" in rows


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A04")
def test_audit_after_notify(admin, ex1):
    body = {"notification_type": "custom", "message": "Exam starts Monday", "target_audience": "students"}
    assert admin.post(f"/exams/{ex1['id']}/notify", json=body).status_code == 200
    row = next(r for r in audit_actions(admin, ex1["id"]) if r["action"] == "notification_queued")
    meta = row["metadata_"]
    assert meta["target_audience"] == "students" and meta["notification_type"] == "custom" and meta["recipients"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A05")
def test_audit_after_delete(admin, world, cleanup):
    e = create_exam(admin, cleanup, world)
    assert admin.delete(f"/exams/{e}").status_code == 204
    row = next(r for r in audit_actions(admin, e) if r["action"] == "exam_deleted")
    assert row["old_value"] == "active"
    assert "marks_deleted" in row["metadata_"] and "exam_name" in row["metadata_"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A06")
def test_no_audit_for_routine_actions(admin, world, ex1, cleanup):
    from api_tests.exam.helpers import mark_row, remove_exam, save_marks

    cfg = ex1["configs"][0]
    save_marks(admin, ex1["id"], cfg, [mark_row(world.students[0]["id"], cfg["components"][0], 5)])
    admin.put(f"/exams/{ex1['id']}", json={"term": "T"})
    clone = admin.post(f"/exams/{ex1['id']}/clone", json={})
    cleanup.add(remove_exam, admin, clone.json()["id"])
    admin.post(f"/exams/{ex1['id']}/deactivate")
    admin.post(f"/exams/{ex1['id']}/activate")
    assert audit_actions(admin, ex1["id"]) == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A07")
def test_audit_pagination(admin, ex1):
    for _ in range(25):
        assert admin.post(f"/exams/{ex1['id']}/hall-tickets/publish").status_code == 200
    first = admin.get(f"/exams/{ex1['id']}/audit", params={"page": 1, "page_size": 20}).json()
    second = admin.get(f"/exams/{ex1['id']}/audit", params={"page": 2, "page_size": 20}).json()
    assert len(first) == 20 and len(second) == 5
    assert not {r["id"] for r in first} & {r["id"] for r in second}
    assert first[0]["performed_at"] >= second[-1]["performed_at"]
    default = admin.get(f"/exams/{ex1['id']}/audit").json()
    assert len(default) == 20
    assert len(admin.get(f"/exams/{ex1['id']}/audit", params={"page_size": 100}).json()) == 25


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A08")
def test_audit_page_size_100(admin, ex1):
    assert admin.get(f"/exams/{ex1['id']}/audit", params={"page_size": 100}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A09")
@pytest.mark.parametrize("params", [{"page_size": 101}, {"page": 0}, {"page_size": 0}])
def test_audit_invalid_paging(admin, ex1, params):
    assert admin.get(f"/exams/{ex1['id']}/audit", params=params).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A10")
def test_audit_unknown_exam(admin):
    response = admin.get(f"/exams/{new_uuid()}/audit")
    assert response.status_code == 200 and response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A11")
@pytest.mark.parametrize("role", ["admin", "teacher", "staff"])
def test_audit_readable_by_staff_roles(role_clients, ex1, role):
    assert role_clients[role].get(f"/exams/{ex1['id']}/audit").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A11")
@pytest.mark.parametrize("role", ["student", "parent"])
def test_audit_hidden_from_student_and_parent(role_clients, ex1, role):
    assert role_clients[role].get(f"/exams/{ex1['id']}/audit").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A12")
def test_audit_unauthenticated(anon, ex1):
    assert anon.get(f"/exams/{ex1['id']}/audit").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A13")
def test_audit_tenant_isolation(admin, tenant_b, ex1):
    admin.post(f"/exams/{ex1['id']}/hall-tickets/publish")
    assert audit_actions(admin, ex1["id"])
    assert tenant_b.get(f"/exams/{ex1['id']}/audit").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A14")
def test_audit_cschema_mismatch(foreign, ex1):
    assert foreign.get(f"/exams/{ex1['id']}/audit").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-18-A15")
@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_audit_is_append_only(admin, ex1, method):
    response = getattr(admin, method)(f"/exams/{ex1['id']}/audit")
    assert response.status_code == 405


def notify_body(**extra):
    body = {"notification_type": "custom", "message": "Exam starts Monday", "target_audience": "students"}
    body.update(extra)
    return body


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A01")
def test_notify_counts_students(admin, ex1):
    response = admin.post(f"/exams/{ex1['id']}/notify", json=notify_body())
    assert response.status_code == 200, response.text
    assert response.json() == {"exam_id": ex1["id"], "notifications_queued": 3, "notification_type": "custom"}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A02")
def test_notify_counts_distinct_parents(admin, ex1):
    response = admin.post(f"/exams/{ex1['id']}/notify", json=notify_body(target_audience="parents"))
    assert response.status_code == 200
    assert response.json()["notifications_queued"] == 6


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A03")
@pytest.mark.parametrize("audience", ["all", "both", "xyz"])
def test_notify_other_audiences_count_students_and_parents(admin, ex1, audience):
    response = admin.post(f"/exams/{ex1['id']}/notify", json=notify_body(target_audience=audience))
    assert response.status_code == 200
    assert response.json()["notifications_queued"] == 9


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A04")
def test_notify_requires_message(admin, ex1):
    assert admin.post(f"/exams/{ex1['id']}/notify", json={"notification_type": "custom"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A05")
def test_notify_unknown_exam(admin):
    response = admin.post(f"/exams/{new_uuid()}/notify", json=notify_body())
    assert response.status_code == 200 and response.json()["notifications_queued"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A06")
def test_notify_writes_audit(admin, ex1):
    admin.post(f"/exams/{ex1['id']}/notify", json=notify_body(target_audience="parents"))
    row = next(r for r in audit_actions(admin, ex1["id"]) if r["action"] == "notification_queued")
    assert row["metadata_"] == {"notification_type": "custom", "target_audience": "parents", "recipients": 6}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A07")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_notify_denied(role_clients, ex1, role):
    assert role_clients[role].post(f"/exams/{ex1['id']}/notify", json=notify_body()).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A08")
def test_sms_endpoints_denied_for_admin_without_send_sms(admin, world, ex1):
    e = ex1["id"]
    ids = [world.students[0]["id"]]
    assert admin.post(f"/exams/{e}/dates/send-schedule", json=ids).status_code == 403
    assert admin.post(f"/exams/{e}/send-results-notification", params={"student_ids": ids}).status_code == 403
    assert admin.post(f"/exams/{e}/send-hall-ticket-notification", params={"student_ids": ids}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A09")
@pytest.mark.skip(reason="needs exams:send_sms granted to a role (role grants must not change) and would reach the SMS queue and Celery")
def test_send_schedule_as_admin_with_sms():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A10")
@pytest.mark.skip(reason="needs exams:send_sms granted to a role (role grants must not change) and would reach the SMS queue and Celery")
def test_send_schedule_empty_list():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A11")
@pytest.mark.skip(reason="needs exams:send_sms granted to a role (role grants must not change); the unknown-exam 404 is only reachable after the permission check")
def test_send_schedule_unknown_exam():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A12")
@pytest.mark.skip(reason="needs exams:send_sms granted to a role and a parent phone; would queue a real SMS")
def test_send_schedule_unknown_student():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A13")
@pytest.mark.skip(reason="needs exams:send_sms granted to a role and would queue a real SMS")
def test_send_schedule_message_text():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A14")
@pytest.mark.skip(reason="needs exams:send_sms granted to a role and would queue a real SMS")
def test_send_results_notification_rows():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A15")
@pytest.mark.skip(reason="needs exams:send_sms granted to a role and would queue a real SMS")
def test_send_results_notification_no_result():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A16")
def test_send_results_requires_student_ids(admin, ex1):
    assert admin.post(f"/exams/{ex1['id']}/send-results-notification").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A17")
@pytest.mark.skip(reason="the unknown-exam 404 is only reachable after the exams:send_sms check, which no seeded role passes")
def test_send_results_unknown_exam():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A18")
@pytest.mark.skip(reason="needs exams:send_sms granted to a role and would queue a real SMS")
def test_send_hall_ticket_notification_rows():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A19")
def test_send_hall_ticket_requires_student_ids(admin, ex1):
    assert admin.post(f"/exams/{ex1['id']}/send-hall-ticket-notification").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A20")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_sms_endpoints_denied_for_other_roles(role_clients, world, ex1, role):
    client = role_clients[role]
    e = ex1["id"]
    ids = [world.students[0]["id"]]
    assert client.post(f"/exams/{e}/dates/send-schedule", json=ids).status_code == 403
    assert client.post(f"/exams/{e}/send-results-notification", params={"student_ids": ids}).status_code == 403
    assert client.post(f"/exams/{e}/send-hall-ticket-notification", params={"student_ids": ids}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A21")
def test_notification_endpoints_unauthenticated(anon, world, ex1):
    e = ex1["id"]
    ids = [world.students[0]["id"]]
    assert anon.post(f"/exams/{e}/notify", json=notify_body()).status_code == 401
    assert anon.post(f"/exams/{e}/dates/send-schedule", json=ids).status_code == 401
    assert anon.post(f"/exams/{e}/send-results-notification", params={"student_ids": ids}).status_code == 401
    assert anon.post(f"/exams/{e}/send-hall-ticket-notification", params={"student_ids": ids}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A22")
@pytest.mark.skip(reason="needs exams:send_sms granted to a tenant B admin (role grants must not change)")
def test_sms_tenant_isolation():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXM-19-A23")
def test_notify_cschema_mismatch(foreign, ex1):
    assert foreign.post(f"/exams/{ex1['id']}/notify", json=notify_body()).status_code == 403
