import uuid

import pytest

from api_tests.fee import helpers as h

ROLES = ["admin", "staff", "teacher", "student", "parent"]
pytestmark = pytest.mark.api
C = "/fee/collection"


def rid():
    return str(uuid.uuid4())


def preview(client, student_id, year_id):
    return client.get(f"{C}/summary/{student_id}/sms-preview", params={"academic_year_id": year_id})


@pytest.fixture
def send_sms_grant(admin, logins):
    roles = h.ok(admin.get("/admin/role-mgmt/roles/")).json()
    items = roles["roles"] if isinstance(roles, dict) else roles
    admin_role = next(r for r in items if r["name"] == "Admin")
    role_id = admin_role["id"]
    before = h.ok(
        admin.put(
            f"/admin/role-mgmt/roles/{role_id}/permissions",
            params={"resource": "fee_collection", "action": "send_sms", "is_granted": "true"},
        )
    ).json()
    old = before["permission"]["old_value"]
    yield role_id
    admin.put(
        f"/admin/role-mgmt/roles/{role_id}/permissions",
        params={"resource": "fee_collection", "action": "send_sms", "is_granted": "true" if old else "false"},
    )


@pytest.mark.tc("TC-FEE-14-A01")
def test_sms_preview(admin, w1, year_id):
    s = w1["student"]
    data = h.ok(preview(admin, s["id"], year_id)).json()
    assert data["can_send"] is True
    assert data["due_amount"] == "12000.00"
    assert data["admission_number"] == s["admission_number"]
    assert data["student_name"] == f"{s['first_name']} Tester"
    assert data["parent_phone"] in (s["father_phone"], str(int(s["father_phone"]) + 1))
    assert data["parent_name"]
    assert data["message"].startswith(f"Dear {data['parent_name']}, fee due for {data['student_name']} (Adm: {s['admission_number']}) is Rs.12,000.00 for ")
    assert data["message"].endswith(". Please pay at the earliest.")


@pytest.mark.tc("TC-FEE-14-A01")
def test_sms_preview_includes_old_fee_and_payments(admin, cleanup, w1, year_id):
    s = w1["student"]
    t = w1["tuition"]["id"]
    h.ok(h.pay(admin, s, year_id, "6000.00", [(t, "6000.00")]))
    old = h.ok(
        admin.post(
            "/fee/old-fees/",
            json={"student_id": s["id"], "academic_year_label": "2024-25", "fee_type_name": "Tuition Fee", "original_amount": "900.00", "paid_amount": "0"},
        ),
        201,
    ).json()
    cleanup.delete_later(admin, f"/fee/old-fees/{old['id']}")
    data = h.ok(preview(admin, s["id"], year_id)).json()
    assert h.D(data["due_amount"]) == h.D("6900.00")
    assert "is Rs.6,900.00 for" in data["message"]


@pytest.mark.tc("TC-FEE-14-A02")
@pytest.mark.skip(reason="admission requires a parent phone, so a student whose parent has no phone cannot be created through the API")
def test_sms_preview_without_parent_phone():
    pass


@pytest.mark.tc("TC-FEE-14-A03")
def test_sms_preview_unknown_student(admin, year_id):
    r = preview(admin, rid(), year_id)
    assert r.status_code == 404
    assert "Student not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-14-A04")
def test_sms_preview_requires_year(admin, w1):
    assert admin.get(f"{C}/summary/{w1['student']['id']}/sms-preview").status_code == 422


@pytest.mark.tc("TC-FEE-14-A05")
@pytest.mark.skip(reason="a successful or failed send would call the SMS provider; sends are not exercised")
def test_sms_send_success():
    pass


@pytest.mark.tc("TC-FEE-14-A06")
@pytest.mark.skip(reason="the provider failure path needs a mocked provider, which is not possible against the running API")
def test_sms_send_failure():
    pass


@pytest.mark.tc("TC-FEE-14-A07")
@pytest.mark.skip(reason="a parent without a phone cannot be created through admission")
def test_sms_send_without_parent_phone():
    pass


@pytest.mark.tc("TC-FEE-14-A08")
def test_sms_send_unknown_student(admin, year_id):
    r = admin.post(f"{C}/summary/{rid()}/send-sms", params={"academic_year_id": year_id})
    assert r.status_code == 404
    assert "Student not found" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-14-A08")
def test_sms_send_requires_year(admin, w1):
    assert admin.post(f"{C}/summary/{w1['student']['id']}/send-sms").status_code == 422


@pytest.mark.tc("TC-FEE-14-A09")
def test_receipt_resend_unknown_receipts_are_skipped(admin, send_sms_grant):
    r = h.ok(admin.post(f"{C}/send-receipt-sms", json=[rid(), rid()]))
    data = r.json()
    assert data["status"] == "queued"
    assert data["queued_count"] == 0 and data["skipped_count"] == 2


@pytest.mark.tc("TC-FEE-14-A10")
def test_receipt_resend_empty_list(admin, send_sms_grant):
    data = h.ok(admin.post(f"{C}/send-receipt-sms", json=[])).json()
    assert data["status"] == "queued" and data["queued_count"] == 0 and data["skipped_count"] == 0


@pytest.mark.tc("TC-FEE-14-A11")
def test_receipt_resend_invalid_item(admin):
    assert admin.post(f"{C}/send-receipt-sms", json=["not-a-uuid"]).status_code == 422


@pytest.mark.tc("TC-FEE-14-A12")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_sms_preview_and_send_denied_roles(role, role_clients, w1, year_id):
    client = role_clients[role]
    assert preview(client, w1["student"]["id"], year_id).status_code == 403
    r = client.post(f"{C}/summary/{w1['student']['id']}/send-sms", params={"academic_year_id": year_id})
    assert r.status_code == 403


@pytest.mark.tc("TC-FEE-14-A12")
def test_sms_preview_admin_allowed(admin, w1, year_id):
    assert preview(admin, w1["student"]["id"], year_id).status_code == 200


@pytest.mark.tc("TC-FEE-14-A13")
@pytest.mark.parametrize("role", ROLES)
def test_receipt_resend_role_matrix_default_grants(role, role_clients):
    r = role_clients[role].post(f"{C}/send-receipt-sms", json=[rid()])
    assert r.status_code == 403


@pytest.mark.tc("TC-FEE-14-A14")
def test_sms_no_token_header_isolation(anon, mismatched_admin, tenant_b, w1, year_id):
    sid = w1["student"]["id"]
    assert preview(anon, sid, year_id).status_code == 401
    assert anon.post(f"{C}/summary/{sid}/send-sms", params={"academic_year_id": year_id}).status_code == 401
    assert anon.post(f"{C}/send-receipt-sms", json=[rid()]).status_code == 401
    assert preview(mismatched_admin, sid, year_id).status_code == 403
    r = preview(tenant_b, sid, tenant_b.academic_year_id)
    assert r.status_code == 404
    assert "Student not found" in h.detail_text(r)
    r = tenant_b.post(f"{C}/summary/{sid}/send-sms", params={"academic_year_id": tenant_b.academic_year_id})
    assert r.status_code == 404
