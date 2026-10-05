import uuid

import pytest

from api_tests.communication.conftest import NOBODY
from api_tests.communication.helpers import granted
from api_tests.support import unique

SEND = "/communication/send"
TPL = "/communication/templates"
NO_SEND = "would queue a message and dispatch the Celery task; communication tests never reach a provider or the queue"
CUSTOM_BODY = "Hello {{name}}, amount {{amount}} due on {{due_date}}."


def nobody(**extra):
    payload = {**NOBODY, "variables": {}}
    payload.update(extra)
    return payload


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A01")
@pytest.mark.skip(reason=NO_SEND)
def test_send_to_single_parent():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A02")
@pytest.mark.skip(reason=NO_SEND)
def test_recipients_without_phone_are_skipped():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A03")
@pytest.mark.skip(reason=NO_SEND)
def test_email_send_drops_recipients_without_email():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A04")
@pytest.mark.skip(reason=NO_SEND)
def test_student_fan_out():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A05")
def test_missing_user_variables(admin, make_template):
    template = make_template(body=CUSTOM_BODY)
    response = admin.post(SEND, json=nobody(template_id=template["id"]))
    assert response.status_code == 400
    assert response.json()["detail"] == "Missing user-provided template variables: ['amount', 'due_date']"
    partial = admin.post(SEND, json=nobody(template_id=template["id"], variables={"amount": "5"}))
    assert partial.status_code == 400
    assert partial.json()["detail"] == "Missing user-provided template variables: ['due_date']"


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A06")
@pytest.mark.skip(reason=NO_SEND)
def test_variables_are_rendered_into_the_message():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A07")
def test_extra_variables_field_is_ignored(admin, make_template):
    template = make_template(body=CUSTOM_BODY)
    response = admin.post(
        SEND, json=nobody(template_id=template["id"], extra_variables={"amount": "500", "due_date": "2026-10-31"})
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Missing user-provided template variables: ['amount', 'due_date']"


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A08")
@pytest.mark.skip(reason=NO_SEND)
def test_user_variable_overrides_system_variable():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A09")
def test_inactive_template_cannot_be_sent(admin, make_template):
    template = make_template()
    admin.delete(f"{TPL}/{template['id']}")
    response = admin.post(SEND, json=nobody(template_id=template["id"]))
    assert response.status_code == 400
    assert response.json()["detail"] == "Template is inactive and cannot be used for sending."


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A10")
def test_unknown_and_malformed_template_id(admin):
    unknown = admin.post(SEND, json=nobody(template_id=str(uuid.uuid4())))
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Template not found."
    assert admin.post(SEND, json=nobody(template_id="abc")).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A11")
@pytest.mark.skip(reason=NO_SEND)
def test_template_channel_wins_over_request_channel():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A12")
def test_send_schema_validation(admin, make_template):
    template = make_template()
    assert admin.post(SEND, json={"template_id": template["id"]}).status_code == 422
    response = admin.post(SEND, json={"target_type": "all_parents"})
    assert response.status_code == 422
    assert "template_id is required unless channel is 'whatsapp' with a free-text message." in response.text


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A13")
def test_unknown_target_type_is_a_client_error(admin, make_template):
    template = make_template()
    response = admin.post(SEND, json={"template_id": template["id"], "target_type": "bogus", "target_ref": {}, "variables": {}})
    assert response.status_code in (400, 422)


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A14")
@pytest.mark.skip(reason=NO_SEND)
def test_free_text_whatsapp_send():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A15")
@pytest.mark.parametrize("target", ["all_users", "fee_defaulters", "role_based"])
def test_free_text_whatsapp_target_restriction(admin, target):
    response = admin.post(SEND, json={"channel": "whatsapp", "message": "Hello {{name}}", "target_type": target})
    assert response.status_code == 422
    assert f"target_type '{target}' is not allowed for a template-less WhatsApp send." in response.text


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A16")
def test_free_text_is_whatsapp_only(admin):
    sms = admin.post(SEND, json={"channel": "sms", "message": "Hi", "target_type": "all_parents"})
    assert sms.status_code == 422
    blank = admin.post(SEND, json={"channel": "whatsapp", "message": "   ", "target_type": "all_parents"})
    assert blank.status_code == 422
    assert "message is required for a template-less WhatsApp send." in blank.text


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A17")
def test_render_failure_is_logged_not_queued(failed_log):
    log = failed_log["log"]
    assert log["status"] == "failed"
    assert log["message"] == ""
    assert log["error_message"]
    assert log["provider_message_id"] is None
    assert log["template_id"] == failed_log["template"]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A18")
def test_audience_resolving_to_nobody(admin, make_template):
    template = make_template()
    response = admin.post(SEND, json=nobody(template_id=template["id"]))
    assert response.status_code == 200
    assert response.json() == {"queued_count": 0}


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A19")
@pytest.mark.skip(reason="needs the Celery dispatch patched, which cannot be done against a running server")
def test_dispatch_failure_is_swallowed():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A20")
@pytest.mark.skip(reason=NO_SEND)
def test_template_edit_does_not_change_queued_messages():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A21")
@pytest.mark.skip(reason=NO_SEND)
def test_all_users_send_deduplicates():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A22")
@pytest.mark.skip(reason="needs the rate limiter enabled; the test API runs with rate limiting disabled")
def test_send_rate_limit():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A23")
def test_admin_may_send(admin, make_template):
    template = make_template()
    assert admin.post(SEND, json=nobody(template_id=template["id"])).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A24")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_send_denied_without_create_grant(role_clients, logins, make_template, role):
    assert not granted(logins, role, "communications", "create")
    template = make_template()
    response = role_clients[role].post(SEND, json=nobody(template_id=template["id"]))
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A25")
def test_send_needs_create_not_list(role_client, make_template):
    template = make_template()
    listing = role_client([("communications", "list")])
    assert listing.post(SEND, json=nobody(template_id=template["id"])).status_code == 403
    creating = role_client([("communications", "create")])
    response = creating.post(SEND, json=nobody(template_id=template["id"]))
    assert response.status_code == 200 and response.json() == {"queued_count": 0}


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A26")
def test_send_requires_token(anon):
    assert anon.post(SEND, json=nobody(template_id=str(uuid.uuid4()))).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A27")
def test_send_with_other_tenants_template(tenant_b, make_template):
    template = make_template()
    response = tenant_b.post(SEND, json=nobody(template_id=template["id"]))
    assert response.status_code == 404
    assert response.json()["detail"] == "Template not found."


@pytest.mark.api
@pytest.mark.tc("TC-COM-03-A28")
def test_send_foreign_tenant_header(b_header_client, make_template):
    template = make_template()
    assert b_header_client.post(SEND, json=nobody(template_id=template["id"])).status_code == 403


STAFF_BODY = "Dear {{staff_name}}, welcome to {{school_name}}."


@pytest.mark.api
@pytest.mark.tc("TC-COM-04-A01")
def test_quick_send_payload_with_extra_variables_fails(admin, make_template, make_staff):
    template = make_template(body=STAFF_BODY)
    staff = make_staff()
    response = admin.post(
        SEND,
        json={
            "template_id": template["id"],
            "target_type": "individual_staff",
            "target_ref": {"staff_id": staff["id"]},
            "extra_variables": {"school_name": "QA School"},
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Missing user-provided template variables: ['school_name', 'staff_name']"


@pytest.mark.api
@pytest.mark.tc("TC-COM-04-A02")
@pytest.mark.skip(reason=NO_SEND)
def test_quick_send_with_variables_queues_one_message():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-04-A03")
def test_individual_staff_without_phone_queues_nothing(admin, role_client, make_template):
    template = make_template()
    client = role_client([("profile", "read_own"), ("profile", "update_own")])
    assert client.put("/profile/staff/me", json={"phone": ""}).status_code == 200
    assert admin.get(f"/staff/enrollment/{client.staff['id']}").json()["phone"] == ""
    response = admin.post(
        SEND,
        json={
            "template_id": template["id"],
            "target_type": "individual_staff",
            "target_ref": {"staff_id": client.staff["id"]},
            "variables": {},
        },
    )
    assert response.status_code == 200 and response.json() == {"queued_count": 0}


@pytest.mark.api
@pytest.mark.tc("TC-COM-04-A04")
def test_individual_staff_unknown_id_queues_nothing(admin, make_template):
    template = make_template(body=STAFF_BODY)
    response = admin.post(
        SEND,
        json={
            "template_id": template["id"],
            "target_type": "individual_staff",
            "target_ref": {"staff_id": str(uuid.uuid4())},
            "variables": {"staff_name": "x", "school_name": "y"},
        },
    )
    assert response.status_code == 200 and response.json() == {"queued_count": 0}


@pytest.mark.api
@pytest.mark.tc("TC-COM-04-A05")
def test_quick_send_template_list_includes_inactive(admin, make_template):
    active = make_template()
    inactive = make_template()
    admin.delete(f"{TPL}/{inactive['id']}")
    response = admin.get(TPL, params={"channel": "sms", "page_size": 100})
    assert response.status_code == 200
    by_id = {i["id"]: i for i in response.json()}
    assert by_id[active["id"]]["is_active"] is True
    assert by_id[inactive["id"]]["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-COM-04-A06")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_quick_send_denied_for_roles(role_clients, make_template, make_staff, role):
    template = make_template(body=STAFF_BODY)
    staff = make_staff()
    response = role_clients[role].post(
        SEND,
        json={
            "template_id": template["id"],
            "target_type": "individual_staff",
            "target_ref": {"staff_id": staff["id"]},
            "variables": {"staff_name": unique("x"), "school_name": "y"},
        },
    )
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-COM-04-A07")
def test_quick_send_requires_token(anon):
    response = anon.post(
        SEND, json={"template_id": str(uuid.uuid4()), "target_type": "individual_staff", "target_ref": {"staff_id": str(uuid.uuid4())}}
    )
    assert response.status_code == 401
