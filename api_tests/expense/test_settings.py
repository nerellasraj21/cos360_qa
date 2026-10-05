import uuid

import pytest

from api_tests.expense.helpers import ROLES, forbidden_roles, other_tenant_header
from api_tests.support import items_of, unique

BASE = "/expense/settings/"


def new_setting(admin, cleanup, **over):
    body = {
        "setting_key": unique("exp_key_"),
        "setting_name": "qa setting",
        "setting_category": "approval",
        "numeric_value": "500.00",
    }
    body.update(over)
    response = admin.post(BASE, json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}{data['id']}")
    return data


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A01")
def test_create_setting(admin, cleanup):
    key = unique("exp_key_")
    response = admin.post(
        BASE,
        json={
            "setting_key": key,
            "setting_name": "QA limit",
            "setting_category": "approval",
            "numeric_value": "500.00",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}{data['id']}")
    assert data["setting_key"] == key
    assert data["version"] == 1
    assert data["is_active"] is True
    assert data["created_by_role"] == "Admin"
    assert data["numeric_value"] == "500.00"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A02")
def test_duplicate_setting_key(admin, cleanup):
    setting = new_setting(admin, cleanup)
    response = admin.post(
        BASE,
        json={"setting_key": setting["setting_key"], "setting_name": "again", "setting_category": "workflow"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "DUPLICATE_SETTING_KEY"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A03")
@pytest.mark.parametrize(
    "over",
    [
        {"setting_category": "budget"},
        {"compliance_level": "extreme"},
        {"string_value": "s" * 501},
        {"setting_key": ""},
        {"setting_name": "n" * 201},
    ],
    ids=["category", "compliance", "string_501", "key_empty", "name_201"],
)
def test_create_setting_validation(admin, over):
    body = {"setting_key": unique("exp_key_"), "setting_name": "qa", "setting_category": "approval"}
    body.update(over)
    assert admin.post(BASE, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A04")
def test_list_settings_filters(admin, cleanup):
    approval = new_setting(admin, cleanup, setting_category="approval")
    security = new_setting(admin, cleanup, setting_category="security")
    gone = new_setting(admin, cleanup, setting_category="approval")
    admin.delete(f"{BASE}{gone['id']}")
    only_approval = items_of(admin.get(BASE, params={"category": "approval"}))
    ids = [row["id"] for row in only_approval]
    assert approval["id"] in ids and security["id"] not in ids and gone["id"] not in ids
    assert all(row["setting_category"] == "approval" for row in only_approval)
    pairs = [(row["setting_category"], row["setting_key"]) for row in items_of(admin.get(BASE))]
    assert pairs == sorted(pairs)
    with_inactive = items_of(admin.get(BASE, params={"active_only": "false"}))
    assert gone["id"] in [row["id"] for row in with_inactive]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A05")
def test_get_setting(admin, cleanup):
    setting = new_setting(admin, cleanup)
    assert admin.get(f"{BASE}{setting['id']}").json()["setting_key"] == setting["setting_key"]
    missing = admin.get(f"{BASE}{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Expense setting not found"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A06")
def test_get_setting_value_by_key(admin, cleanup):
    setting = new_setting(admin, cleanup)
    response = admin.get(f"{BASE}key/{setting['setting_key']}/value")
    assert response.status_code == 200
    assert response.json() == {"setting_key": setting["setting_key"], "value": 500.0, "value_type": "numeric"}


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A06")
def test_value_type_precedence(admin, cleanup):
    both = new_setting(admin, cleanup, numeric_value=None, string_value="x", integer_value=3)
    assert admin.get(f"{BASE}key/{both['setting_key']}/value").json()["value_type"] == "string"
    flag = new_setting(admin, cleanup, numeric_value=None, boolean_value=False)
    body = admin.get(f"{BASE}key/{flag['setting_key']}/value").json()
    assert body["value"] is False and body["value_type"] == "boolean"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A07")
def test_get_value_unknown_key(admin):
    response = admin.get(f"{BASE}key/does_not_exist_{unique('k')}/value")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A08")
def test_update_setting(admin, cleanup, logins):
    setting = new_setting(admin, cleanup)
    response = admin.put(f"{BASE}{setting['id']}", json={"numeric_value": "750.00"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["numeric_value"] == "750.00"
    assert body["last_modified_by_user_id"] is not None
    assert body["last_modified_by_role"] == "Admin"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A08")
def test_update_ignores_key_and_category(admin, cleanup):
    setting = new_setting(admin, cleanup)
    response = admin.put(
        f"{BASE}{setting['id']}", json={"setting_key": unique("exp_key_"), "setting_category": "security"}
    )
    assert response.status_code == 200
    assert response.json()["setting_key"] == setting["setting_key"]
    assert response.json()["setting_category"] == "approval"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A09")
def test_delete_setting(admin, cleanup):
    setting = new_setting(admin, cleanup)
    response = admin.delete(f"{BASE}{setting['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert admin.get(f"{BASE}key/{setting['setting_key']}/value").status_code == 404


def _ensure_setting(admin, cleanup, key, numeric_value):
    rows = items_of(admin.get(BASE, params={"active_only": "false"}))
    existing = next((row for row in rows if row["setting_key"] == key), None)
    if existing is None:
        response = admin.post(
            BASE,
            json={
                "setting_key": key,
                "setting_name": key,
                "setting_category": "approval",
                "numeric_value": numeric_value,
            },
        )
        assert response.status_code == 201, response.text
        cleanup.delete_later(admin, f"{BASE}{response.json()['id']}")
        return response.json()
    previous = {"is_active": existing["is_active"], "numeric_value": existing["numeric_value"]}
    response = admin.put(f"{BASE}{existing['id']}", json={"is_active": True, "numeric_value": numeric_value})
    assert response.status_code == 200, response.text
    cleanup.add(admin.put, f"{BASE}{existing['id']}", json=previous)
    return response.json()


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A10")
def test_ui_common_settings(admin, cleanup):
    keys = ("auto_approval_limit", "require_receipts_over_amount")
    for key in keys:
        _ensure_setting(admin, cleanup, key, "500.00")
    response = admin.get(f"{BASE}ui/common")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["retrieved_at"], str)
    for key in keys:
        assert body["settings"][key]["type"] == "numeric"
        assert body["settings"][key]["value"] == 500.0
    allowed = {
        "auto_approval_limit",
        "require_receipts_over_amount",
        "default_approval_required",
        "max_file_size_mb",
        "allowed_file_types",
    }
    assert set(body["settings"]) <= allowed


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A11")
def test_reset_is_a_stub(admin, cleanup):
    setting = new_setting(admin, cleanup, numeric_value="321.00")
    response = admin.post(f"{BASE}{setting['id']}/reset")
    assert response.status_code == 200
    assert response.json() == {"message": "Setting reset to default value", "setting_id": setting["id"]}
    assert admin.get(f"{BASE}{setting['id']}").json()["numeric_value"] == "321.00"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A12")
@pytest.mark.parametrize("role", forbidden_roles(["admin"]))
def test_non_admin_roles_denied_everywhere(role_clients, admin, cleanup, role):
    setting = new_setting(admin, cleanup)
    client = role_clients[role]
    body = {"setting_key": unique("exp_key_"), "setting_name": "x", "setting_category": "approval"}
    assert client.post(BASE, json=body).status_code == 403
    assert client.get(BASE).status_code == 403
    assert client.get(f"{BASE}{setting['id']}").status_code == 403
    assert client.get(f"{BASE}key/{setting['setting_key']}/value").status_code == 403
    assert client.get(f"{BASE}ui/common").status_code == 403
    assert client.put(f"{BASE}{setting['id']}", json={"setting_name": "x"}).status_code == 403
    assert client.delete(f"{BASE}{setting['id']}").status_code == 403
    assert client.post(f"{BASE}{setting['id']}/reset").status_code == 403
    assert admin.get(f"{BASE}{setting['id']}").json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A12")
@pytest.mark.parametrize("role", ["admin"])
def test_admin_reads_allowed(role_clients, role):
    assert role_clients[role].get(BASE).status_code == 200
    assert set(ROLES) >= {role}


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A12")
def test_unauthenticated(anon):
    assert anon.get(BASE).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A13")
@pytest.mark.skip(reason="needs a custom role granted expense_settings:create; role grants are global state shared by parallel agents")
def test_custom_role_without_admin_name_denied():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-EXP-05-A14")
def test_tenant_isolation(admin, tenant_b, cleanup):
    setting = new_setting(admin, cleanup)
    listed = items_of(tenant_b.get(BASE, params={"active_only": "false"}))
    assert setting["id"] not in [row["id"] for row in listed]
    assert tenant_b.get(f"{BASE}{setting['id']}").status_code == 404
    assert tenant_b.get(f"{BASE}key/{setting['setting_key']}/value").status_code == 404
    created = tenant_b.post(
        BASE,
        json={"setting_key": setting["setting_key"], "setting_name": "b copy", "setting_category": "approval"},
    )
    assert created.status_code == 201, created.text
    cleanup.delete_later(tenant_b, f"{BASE}{created.json()['id']}")
    assert other_tenant_header(admin).get(BASE).status_code == 403
