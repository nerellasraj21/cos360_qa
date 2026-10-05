import uuid

import pytest

from api_tests.communication.helpers import granted

LOGS = "/communication/logs"
LOG_FIELDS = {
    "id",
    "template_id",
    "recipient_name",
    "recipient_phone",
    "recipient_email",
    "channel",
    "message",
    "status",
    "provider_message_id",
    "error_message",
    "triggered_by",
    "target_type",
    "target_ref",
    "created_at",
}


def find_mine(client, failed_log, **params):
    response = client.get(LOGS, params={"page_size": 100, **params})
    assert response.status_code == 200, response.text
    return [i for i in response.json()["items"] if i["id"] == failed_log["log"]["id"]], response.json()


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A01")
def test_logs_list_shape_and_order(admin, failed_log):
    response = admin.get(LOGS)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["page"] == 1 and body["page_size"] == 20
    assert 1 <= len(body["items"]) <= 20
    assert body["total"] >= len(body["items"])
    stamps = [i["created_at"] for i in body["items"]]
    assert stamps == sorted(stamps, reverse=True)
    assert all(set(i) == LOG_FIELDS for i in body["items"])


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A02")
def test_logs_second_page(admin, failed_log):
    body = admin.get(LOGS, params={"page": 2, "page_size": 1}).json()
    assert body["page"] == 2 and body["page_size"] == 1
    assert len(body["items"]) <= 1
    first = admin.get(LOGS, params={"page": 1, "page_size": 1}).json()
    if body["items"] and first["items"]:
        assert body["items"][0]["id"] != first["items"][0]["id"]
    assert body["total"] >= 1


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A03")
def test_logs_paging_boundaries(admin):
    assert admin.get(LOGS, params={"page_size": 100}).status_code == 200
    assert admin.get(LOGS, params={"page_size": 101}).status_code == 422
    assert admin.get(LOGS, params={"page_size": 0}).status_code == 422
    assert admin.get(LOGS, params={"page": 0}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A04")
def test_logs_filters(admin, failed_log):
    for params in (
        {"channel": "sms"},
        {"status": "failed"},
        {"target_type": "individual_staff"},
        {"channel": "sms", "status": "failed", "target_type": "individual_staff"},
    ):
        mine, body = find_mine(admin, failed_log, **params)
        assert len(mine) == 1, params
        for item in body["items"]:
            for key, value in params.items():
                assert item[key] == value
    mine, body = find_mine(admin, failed_log, status="sent")
    assert mine == [] and all(i["status"] == "sent" for i in body["items"])
    mine, _ = find_mine(admin, failed_log, target_type="multiple_parents")
    assert mine == []


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A05")
def test_logs_date_filter(admin, failed_log):
    created = failed_log["log"]["created_at"][:10]
    mine, _ = find_mine(admin, failed_log, date_from=created)
    assert len(mine) == 1
    mine, _ = find_mine(admin, failed_log, date_from="2999-01-01")
    assert mine == []


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A06")
@pytest.mark.parametrize(
    "params",
    [{"date_from": "abc"}, {"status": "bogus"}, {"channel": "bogus"}],
    ids=["date_from", "status", "channel"],
)
def test_logs_invalid_filter_values_fail(admin, params):
    response = admin.get(LOGS, params=params)
    assert response.status_code >= 400
    assert "items" not in response.json()


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A07")
def test_render_failure_log_fields(admin, failed_log):
    mine, _ = find_mine(admin, failed_log, status="failed")
    assert len(mine) == 1
    log = mine[0]
    assert log["message"] == "" and log["error_message"]
    assert log["provider_message_id"] is None
    assert log["recipient_name"] == failed_log["staff"]["first_name"]
    assert log["target_ref"] == {"staff_id": failed_log["staff"]["id"]}


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A08")
def test_log_detail(admin, failed_log):
    response = admin.get(f"{LOGS}/{failed_log['log']['id']}")
    assert response.status_code == 200
    assert set(response.json()) == LOG_FIELDS
    assert response.json()["target_ref"] == {"staff_id": failed_log["staff"]["id"]}
    assert response.json()["id"] == failed_log["log"]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A09")
def test_log_detail_unknown_and_malformed(admin):
    response = admin.get(f"{LOGS}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Log entry not found."
    assert admin.get(f"{LOGS}/abc").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A10")
def test_contacts_are_not_masked(admin, failed_log):
    response = admin.get(f"{LOGS}/{failed_log['log']['id']}")
    assert response.json()["recipient_phone"] == failed_log["staff"]["phone"]
    assert "*" not in response.json()["recipient_phone"]


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A11")
def test_admin_reads_logs(admin, failed_log):
    assert admin.get(LOGS).status_code == 200
    assert admin.get(f"{LOGS}/{failed_log['log']['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A12")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_logs_denied_without_grants(role_clients, logins, failed_log, role):
    assert not granted(logins, role, "communications", "list")
    assert not granted(logins, role, "communications", "read")
    assert role_clients[role].get(LOGS).status_code == 403
    assert role_clients[role].get(f"{LOGS}/{failed_log['log']['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A13")
def test_list_and_read_are_independent(role_client, failed_log):
    listing = role_client([("communications", "list")])
    assert listing.get(LOGS).status_code == 200
    assert listing.get(f"{LOGS}/{failed_log['log']['id']}").status_code == 403
    reading = role_client([("communications", "read")])
    assert reading.get(f"{LOGS}/{failed_log['log']['id']}").status_code == 200
    assert reading.get(LOGS).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A14")
def test_logs_require_token(anon, failed_log):
    assert anon.get(LOGS).status_code == 401
    assert anon.get(f"{LOGS}/{failed_log['log']['id']}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A15")
def test_logs_tenant_isolation(tenant_b, failed_log):
    body = tenant_b.get(LOGS, params={"page_size": 100}).json()
    assert failed_log["log"]["id"] not in [i["id"] for i in body["items"]]
    assert tenant_b.get(f"{LOGS}/{failed_log['log']['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-COM-06-A16")
def test_logs_foreign_tenant_header(b_header_client, failed_log):
    assert b_header_client.get(LOGS).status_code == 403
    assert b_header_client.get(f"{LOGS}/{failed_log['log']['id']}").status_code == 403
