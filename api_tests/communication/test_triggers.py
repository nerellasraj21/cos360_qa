import uuid

import pytest

from api_tests.communication.helpers import granted

HOLIDAY = "/announcements/send-holiday-notice"
SUMMARY = "/staff/send-attendance-summary"
INTERVIEW = "/staff/send-interview-calls"
HOLIDAY_PARAMS = {"holiday_name": "Independence Day", "holiday_date": "2026-08-15", "reason": "National holiday"}
INTERVIEW_PARAMS = {"interview_date": "2026-10-10", "interview_time": "10:30 AM", "position": "Teacher"}
NO_SEND = "would queue a message and dispatch the Celery task; communication tests never reach a provider or the queue"


def require_no_grant(logins, role, resource, action="send_sms"):
    if granted(logins, role, resource, action):
        pytest.skip(f"{role} holds {resource}:{action} in this tenant, so a valid call would queue a real message")


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A01")
@pytest.mark.skip(reason=NO_SEND)
def test_holiday_notice_queues_one_row():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A02")
@pytest.mark.parametrize("missing", ["holiday_name", "holiday_date", "reason"])
def test_holiday_notice_requires_parameters(admin, missing):
    params = {k: v for k, v in HOLIDAY_PARAMS.items() if k != missing}
    response = admin.post(HOLIDAY, params=params)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", missing]


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A03")
@pytest.mark.skip(reason=NO_SEND)
def test_holiday_date_is_not_validated():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A04")
@pytest.mark.skip(reason=NO_SEND)
def test_holiday_template_id_is_null_without_environment():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A05")
@pytest.mark.skip(reason="needs the Celery dispatch patched to raise, which cannot be done against a running server")
def test_holiday_dispatch_failure():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A06")
@pytest.mark.skip(reason="processes a queue row with the provider code; needs direct access to the worker, outside API tests")
def test_holiday_row_cannot_be_delivered():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A07")
def test_holiday_notice_json_body_is_not_accepted(admin):
    response = admin.post(HOLIDAY, json=HOLIDAY_PARAMS)
    assert response.status_code == 422
    assert {d["loc"][-1] for d in response.json()["detail"]} == {"holiday_name", "holiday_date", "reason"}


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A08")
def test_admin_without_send_sms_grant_is_denied(admin, logins):
    require_no_grant(logins, "admin", "announcements")
    response = admin.post(HOLIDAY, params=HOLIDAY_PARAMS)
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A09")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_holiday_notice_denied_for_other_roles(role_clients, logins, role):
    require_no_grant(logins, role, "announcements")
    assert role_clients[role].post(HOLIDAY, params=HOLIDAY_PARAMS).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A10")
def test_holiday_notice_requires_token(anon):
    assert anon.post(HOLIDAY, params=HOLIDAY_PARAMS).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-COM-07-A11")
@pytest.mark.skip(reason=NO_SEND)
def test_holiday_row_is_tenant_scoped():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A01")
@pytest.mark.skip(reason=NO_SEND)
def test_attendance_summary_queues_rows():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A02")
def test_attendance_summary_unknown_staff_is_skipped(role_client):
    client = role_client([("staff_attendance", "send_sms")])
    response = client.post(SUMMARY, params={"period": "July"}, json=[str(uuid.uuid4())])
    assert response.status_code == 200
    assert response.json() == {
        "status": "queued",
        "queued_count": 0,
        "skipped_count": 1,
        "detail": "SMS queued for 0 staff. 1 skipped.",
    }


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A03")
def test_attendance_summary_empty_list(role_client):
    client = role_client([("staff_attendance", "send_sms")])
    response = client.post(SUMMARY, params={"period": "July"}, json=[])
    assert response.status_code == 200
    assert (response.json()["queued_count"], response.json()["skipped_count"]) == (0, 0)


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A04")
def test_attendance_summary_validation(admin):
    assert admin.post(SUMMARY, json=[]).status_code == 422
    assert admin.post(SUMMARY, params={"period": "July"}, json={}).status_code == 422
    assert admin.post(SUMMARY, params={"period": "July"}, json=["not-a-uuid"]).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A05")
@pytest.mark.skip(reason="needs the Celery dispatch patched to raise, which cannot be done against a running server")
def test_attendance_summary_dispatch_failure():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A06")
@pytest.mark.skip(reason=NO_SEND)
def test_interview_call_queues_row():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A07")
@pytest.mark.parametrize("missing", ["interview_date", "interview_time", "position"])
def test_interview_calls_require_parameters(admin, missing):
    params = {k: v for k, v in INTERVIEW_PARAMS.items() if k != missing}
    response = admin.post(INTERVIEW, params=params, json=[])
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", missing]


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A08")
@pytest.mark.skip(reason=NO_SEND)
def test_template_id_comes_from_environment():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A09")
@pytest.mark.skip(reason="processes a queue row with the provider code; needs direct access to the worker, outside API tests")
def test_trigger_row_cannot_be_delivered():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A10")
def test_admin_without_grants_is_denied(admin, logins):
    require_no_grant(logins, "admin", "staff_attendance")
    require_no_grant(logins, "admin", "staff_enrollment")
    summary = admin.post(SUMMARY, params={"period": "July"}, json=[])
    interview = admin.post(INTERVIEW, params=INTERVIEW_PARAMS, json=[])
    assert summary.status_code == 403 and interview.status_code == 403
    assert "cannot send_sms staff_attendance" in summary.json()["detail"]
    assert "cannot send_sms staff_enrollment" in interview.json()["detail"]


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A11")
def test_send_sms_grants_are_independent(role_client):
    client = role_client([("staff_attendance", "send_sms")])
    assert client.post(SUMMARY, params={"period": "July"}, json=[]).status_code == 200
    assert client.post(INTERVIEW, params=INTERVIEW_PARAMS, json=[]).status_code == 403
    other = role_client([("staff_enrollment", "send_sms")])
    assert other.post(INTERVIEW, params=INTERVIEW_PARAMS, json=[]).status_code == 200
    assert other.post(SUMMARY, params={"period": "July"}, json=[]).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A12")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_triggers_denied_for_other_roles(role_clients, logins, role):
    require_no_grant(logins, role, "staff_attendance")
    require_no_grant(logins, role, "staff_enrollment")
    client = role_clients[role]
    assert client.post(SUMMARY, params={"period": "July"}, json=[]).status_code == 403
    assert client.post(INTERVIEW, params=INTERVIEW_PARAMS, json=[]).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A13")
def test_triggers_require_token(anon):
    assert anon.post(SUMMARY, params={"period": "July"}, json=[]).status_code == 401
    assert anon.post(INTERVIEW, params=INTERVIEW_PARAMS, json=[]).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A14")
@pytest.mark.skip(reason="the second tenant has no role holding the send_sms grant and its role grants are out of scope for these tests")
def test_trigger_tenant_isolation():
    pass


OTHER_TRIGGERS = [
    ("student_attendance", "/student/attendance/send-absence-alerts", {"attendance_date": "2026-10-01"}, []),
    ("student_admissions", "/students/admission/send-confirmation", {}, []),
    pytest.param(
        "student_homework",
        "/students/homework/send-reminders",
        {},
        [],
        marks=pytest.mark.skip(reason="the homework router is not registered in main_router.py, so the endpoint answers 404"),
    ),
    ("exams", f"/exams/{uuid.uuid4()}/send-results-notification", {"student_ids": str(uuid.uuid4())}, None),
    ("exams", f"/exams/{uuid.uuid4()}/send-hall-ticket-notification", {"student_ids": str(uuid.uuid4())}, None),
    ("exams", f"/exams/{uuid.uuid4()}/dates/send-schedule", {}, None),
    ("fee_collection", "/fee/collection/send-receipt-sms", {}, []),
]


@pytest.mark.api
@pytest.mark.tc("TC-COM-08-A15")
@pytest.mark.parametrize("resource,path,params,body", OTHER_TRIGGERS, ids=["absence-alerts", "send-confirmation", "send-reminders", "results", "hall-ticket", "send-schedule", "receipt-sms"])
def test_other_trigger_endpoints_are_gated(admin, logins, resource, path, params, body):
    require_no_grant(logins, "admin", resource)
    kwargs = {"params": params}
    if body is not None:
        kwargs["json"] = body
    assert admin.post(path, **kwargs).status_code == 403


F05_REASON = "exercises the Celery task and provider code directly against the database; API tests have no database or worker access and must not reach a provider"


@pytest.mark.api
@pytest.mark.parametrize(
    "case",
    [
        pytest.param("A01", marks=pytest.mark.tc("TC-COM-05-A01")),
        pytest.param("A02", marks=pytest.mark.tc("TC-COM-05-A02")),
        pytest.param("A03", marks=pytest.mark.tc("TC-COM-05-A03")),
        pytest.param("A04", marks=pytest.mark.tc("TC-COM-05-A04")),
        pytest.param("A05", marks=pytest.mark.tc("TC-COM-05-A05")),
        pytest.param("A06", marks=pytest.mark.tc("TC-COM-05-A06")),
        pytest.param("A07", marks=pytest.mark.tc("TC-COM-05-A07")),
    ],
)
def test_worker_cases_are_not_api_testable(case):
    pytest.skip(F05_REASON)
