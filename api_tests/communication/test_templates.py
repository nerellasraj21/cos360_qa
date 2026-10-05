import time
import uuid

import pytest

from api_tests.communication.helpers import expected_status, granted, template_body
from api_tests.support import unique

TPL = "/communication/templates"
FIELDS = {"id", "name", "channel", "body", "subject", "variables", "is_active", "updated_at"}


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A01")
def test_create_sms_template(admin, make_template):
    created = make_template(body="Dear {{name}}, fee {{amount}} due.")
    assert set(created) == FIELDS
    assert created["variables"] == ["name", "amount"]
    assert created["is_active"] is True and created["subject"] is None
    assert created["channel"] == "sms"
    assert uuid.UUID(created["id"])


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A02")
def test_create_email_template_with_subject(make_template):
    created = make_template(channel="email", body="Dear {{name}}", subject="Notice for {{name}}")
    assert created["subject"] == "Notice for {{name}}"
    assert created["channel"] == "email"


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A03")
def test_duplicate_name_and_channel(admin, make_template):
    first = make_template()
    again = admin.post(TPL, json=template_body(first["name"], "sms"))
    assert again.status_code == 400
    assert again.json()["detail"] == f"Template with name '{first['name']}' already exists for channel 'sms'."
    other_channel = admin.post(TPL, json=template_body(first["name"], "whatsapp"))
    assert other_channel.status_code == 201
    admin.delete(f"{TPL}/{other_channel.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A04")
def test_sms_body_length_boundary(admin, make_template):
    make_template(body="x" * 480)
    response = admin.post(TPL, json=template_body(unique("com_tpl_"), "sms", "x" * 481))
    assert response.status_code == 422
    assert "SMS body exceeds 480 characters" in response.text
    ok = admin.post(TPL, json=template_body(unique("com_tpl_"), "email", "x" * 481))
    assert ok.status_code == 201
    admin.delete(f"{TPL}/{ok.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A05")
@pytest.mark.parametrize(
    "payload",
    [
        {"name": "n", "channel": "push", "body": "b"},
        {"channel": "sms", "body": "b"},
        {"name": "n", "channel": "sms"},
        {"name": "n", "body": "b"},
    ],
    ids=["channel_push", "no_name", "no_body", "no_channel"],
)
def test_template_create_validation(admin, payload):
    assert admin.post(TPL, json=payload).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A06")
def test_client_variables_are_ignored(admin, make_template):
    created = make_template(body="{{name}}", variables=["zzz"])
    assert created["variables"] == ["name"]
    assert admin.get(f"{TPL}/{created['id']}").json()["variables"] == ["name"]


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A07")
def test_list_is_plain_array_ordered_by_name(admin, make_template):
    prefix = unique("com_ord_")
    names = [f"{prefix}{c}" for c in ("b", "a", "c")]
    made = [make_template(name=n) for n in names]
    admin.put(f"{TPL}/{made[2]['id']}", json={"is_active": False})
    response = admin.get(TPL)
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    mine = [i["name"] for i in items if i["name"].startswith(prefix)]
    assert mine == sorted(names)
    assert {i["is_active"] for i in items if i["name"].startswith(prefix)} == {True, False}


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A08")
def test_list_filters(admin, make_template):
    sms = make_template(channel="sms")
    email = make_template(channel="email", subject="s")
    off = make_template(channel="sms")
    admin.put(f"{TPL}/{off['id']}", json={"is_active": False})
    by_channel = admin.get(TPL, params={"channel": "email"}).json()
    assert email["id"] in [i["id"] for i in by_channel] and sms["id"] not in [i["id"] for i in by_channel]
    assert all(i["channel"] == "email" for i in by_channel)
    inactive = admin.get(TPL, params={"is_active": "false"}).json()
    assert off["id"] in [i["id"] for i in inactive] and sms["id"] not in [i["id"] for i in inactive]
    both = admin.get(TPL, params={"channel": "sms", "is_active": "true"}).json()
    assert sms["id"] in [i["id"] for i in both]
    assert off["id"] not in [i["id"] for i in both] and email["id"] not in [i["id"] for i in both]


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A08")
def test_list_with_unknown_channel_is_not_a_server_error(admin):
    response = admin.get(TPL, params={"channel": "push"})
    assert response.status_code in (200, 422)


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A09")
def test_list_with_trailing_slash(admin, make_template):
    created = make_template()
    response = admin.get(TPL + "/")
    assert response.status_code == 200
    assert created["id"] in [i["id"] for i in response.json()]


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A10")
def test_list_ignores_paging_parameters(admin, make_template):
    first, second = make_template(), make_template()
    response = admin.get(TPL, params={"page": 2, "page_size": 1})
    ids = [i["id"] for i in response.json()]
    assert first["id"] in ids and second["id"] in ids
    assert len(ids) > 1


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A11")
def test_get_template(admin, make_template):
    created = make_template()
    response = admin.get(f"{TPL}/{created['id']}")
    assert response.status_code == 200 and response.json() == created
    missing = admin.get(f"{TPL}/{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["detail"] == "Template not found."
    assert admin.get(f"{TPL}/abc").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A12")
def test_update_body_rederives_variables(admin, make_template):
    created = make_template(body="Hi {{name}}")
    time.sleep(0.05)
    response = admin.put(f"{TPL}/{created['id']}", json={"body": "Hi {{name}} {{x}}"})
    assert response.status_code == 200
    assert response.json()["variables"] == ["name", "x"]
    assert response.json()["updated_at"] >= created["updated_at"]
    cleared = admin.put(f"{TPL}/{created['id']}", json={"body": "no variables"})
    assert cleared.json()["variables"] == []


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A13")
def test_update_name_and_subject(admin, make_template):
    created = make_template(channel="email", subject="old")
    new_name = unique("com_ren_")
    response = admin.put(f"{TPL}/{created['id']}", json={"name": new_name, "subject": "S"})
    assert response.status_code == 200
    assert response.json()["name"] == new_name and response.json()["subject"] == "S"
    assert response.json()["body"] == created["body"]


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A14")
def test_deactivate_and_reactivate_through_put(admin, make_template):
    created = make_template()
    assert admin.put(f"{TPL}/{created['id']}", json={"is_active": False}).json()["is_active"] is False
    assert admin.put(f"{TPL}/{created['id']}", json={"is_active": True}).json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A15")
def test_channel_cannot_be_changed(admin, make_template):
    created = make_template(channel="sms")
    response = admin.put(f"{TPL}/{created['id']}", json={"channel": "email"})
    assert response.status_code == 200
    assert response.json()["channel"] == "sms"


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A16")
def test_rename_to_clashing_name(admin, make_template):
    first = make_template()
    second = make_template()
    response = admin.put(f"{TPL}/{second['id']}", json={"name": first["name"]})
    assert response.status_code == 400
    assert admin.get(f"{TPL}/{second['id']}").json()["name"] == second["name"]


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A17")
def test_update_has_no_sms_length_check(admin, make_template):
    created = make_template()
    response = admin.put(f"{TPL}/{created['id']}", json={"body": "x" * 481})
    assert response.status_code == 200
    assert len(response.json()["body"]) == 481


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A18")
def test_delete_is_idempotent_soft_deactivate(admin, make_template):
    created = make_template()
    for _ in range(2):
        response = admin.delete(f"{TPL}/{created['id']}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False
        assert response.json()["id"] == created["id"]
    assert admin.get(f"{TPL}/{created['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A19")
def test_update_and_delete_unknown_template(admin):
    missing = str(uuid.uuid4())
    put = admin.put(f"{TPL}/{missing}", json={"name": "x"})
    delete = admin.delete(f"{TPL}/{missing}")
    assert put.status_code == 404 and delete.status_code == 404
    assert put.json()["detail"] == "Template not found."


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A20")
def test_admin_on_all_template_endpoints(admin, make_template):
    created = make_template()
    assert admin.get(TPL).status_code == 200
    assert admin.get(f"{TPL}/{created['id']}").status_code == 200
    assert admin.put(f"{TPL}/{created['id']}", json={"subject": "s"}).status_code == 200
    assert admin.delete(f"{TPL}/{created['id']}").status_code == 200


def template_calls(template_id):
    return [
        ("create", "POST", TPL, template_body(unique("com_den_"))),
        ("list", "GET", TPL, None),
        ("list", "GET", f"{TPL}/{template_id}", None),
        ("update", "PUT", f"{TPL}/{template_id}", {"subject": "denied"}),
        ("update", "DELETE", f"{TPL}/{template_id}", None),
    ]


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A21")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_templates_denied_without_grants(role_clients, logins, make_template, role):
    created = make_template()
    for action, method, path, body in template_calls(created["id"]):
        assert not granted(logins, role, "communications", action)
        kwargs = {"json": body} if body is not None else {}
        assert role_clients[role].request(method, path, **kwargs).status_code == 403, (role, method, path)
    after = role_clients["admin"].get(f"{TPL}/{created['id']}").json()
    assert after["is_active"] is True and after["subject"] is None


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A22")
def test_list_only_role(role_client, make_template, admin):
    client = role_client([("communications", "list")])
    created = make_template()
    assert client.get(TPL).status_code == 200
    assert client.get(f"{TPL}/{created['id']}").status_code == 200
    assert client.post(TPL, json=template_body(unique("com_den_"))).status_code == 403
    assert client.put(f"{TPL}/{created['id']}", json={"subject": "x"}).status_code == 403
    assert client.delete(f"{TPL}/{created['id']}").status_code == 403
    assert admin.get(f"{TPL}/{created['id']}").json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A23")
def test_update_only_role(role_client, make_template, admin):
    client = role_client([("communications", "update")])
    created = make_template()
    assert client.put(f"{TPL}/{created['id']}", json={"subject": "by update role"}).status_code == 200
    assert client.get(TPL).status_code == 403
    assert client.get(f"{TPL}/{created['id']}").status_code == 403
    assert client.post(TPL, json=template_body(unique("com_den_"))).status_code == 403
    assert client.delete(f"{TPL}/{created['id']}").status_code == 200
    assert admin.get(f"{TPL}/{created['id']}").json()["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A24")
def test_templates_require_token(anon):
    missing = str(uuid.uuid4())
    for _, method, path, body in template_calls(missing):
        kwargs = {"json": body} if body is not None else {}
        assert anon.request(method, path, **kwargs).status_code == 401, (method, path)


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A25")
def test_template_tenant_isolation(tenant_b, make_template, cleanup):
    created = make_template()
    assert created["id"] not in [i["id"] for i in tenant_b.get(TPL).json()]
    assert tenant_b.get(f"{TPL}/{created['id']}").status_code == 404
    assert tenant_b.put(f"{TPL}/{created['id']}", json={"subject": "x"}).status_code == 404
    clone = tenant_b.post(TPL, json=template_body(created["name"], created["channel"]))
    assert clone.status_code == 201
    cleanup.add(tenant_b.delete, f"{TPL}/{clone.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A26")
def test_template_foreign_tenant_header(b_header_client):
    assert b_header_client.get(TPL).status_code == 403
    assert b_header_client.post(TPL, json=template_body(unique("com_hdr_"))).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-COM-01-A27")
@pytest.mark.skip(reason="would need a real send that queues a message and dispatches the Celery task")
def test_jinja_expression_is_rendered_at_send_time():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-00-A01")
def test_role_grants_match_documented_defaults(logins):
    assert all(granted(logins, "admin", "communications", a) for a in ("create", "read", "update", "list"))
    assert not granted(logins, "admin", "communications", "delete")
    for role in ("staff", "teacher", "student", "parent"):
        assert not any(granted(logins, role, "communications", a) for a in ("create", "read", "update", "list"))
    assert expected_status(logins, "staff", "communications", "list") == 403
