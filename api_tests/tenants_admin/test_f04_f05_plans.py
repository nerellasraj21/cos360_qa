import uuid

import pytest

from api_tests.auth.helpers import detail_text
from api_tests.support import unique
from api_tests.tenants_admin import tmp_tenants
from api_tests.tenants_admin.conftest import MISSING_AUTH, ROLES, SA_REQUIRED

def plan_create_xfail():
    return pytest.mark.usefixtures()


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A01")
@plan_create_xfail()
def test_create_plan_201(superadmin):
    name = "qa_tmp_lite_" + unique()
    response = superadmin.post("/super_admin/plans/", params={"name": name, "description": "QA lite plan"})
    try:
        assert response.status_code == 201
        body = response.json()
        assert body["message"] == "Plan created successfully"
        assert body["plan"]["is_active"] is True
        assert len(body["next_steps"]) == 3
    finally:
        if response.status_code == 201:
            superadmin.put(f"/super_admin/plans/{body['plan']['id']}", params={"is_active": "false"})


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A02")
def test_create_duplicate_plan_name_400(superadmin):
    response = superadmin.post("/super_admin/plans/", params={"name": "Full", "description": "duplicate"})
    assert response.status_code == 400
    assert detail_text(response) == "Plan with name 'Full' already exists"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A03")
@plan_create_xfail()
def test_create_inactive_plan(superadmin):
    name = "qa_tmp_off_" + unique()
    response = superadmin.post("/super_admin/plans/", params={"name": name, "description": "d", "is_active": "false"})
    assert response.status_code == 201
    assert response.json()["plan"]["is_active"] is False


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A04")
def test_create_without_description_422(superadmin):
    response = superadmin.post("/super_admin/plans/", params={"name": "qa_tmp_nodesc_" + unique()})
    assert response.status_code == 422
    assert "description" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A05")
@plan_create_xfail()
def test_create_with_50_character_name(superadmin):
    name = ("qa_tmp_" + unique("n"))[:50].ljust(50, "x")
    response = superadmin.post("/super_admin/plans/", params={"name": name, "description": "d"})
    assert response.status_code == 201
    superadmin.put(f"/super_admin/plans/{response.json()['plan']['id']}", params={"is_active": "false"})


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A05")
def test_create_with_51_character_name_rejected(superadmin):
    name = "qa_tmp_" + "y" * 44
    response = superadmin.post("/super_admin/plans/", params={"name": name, "description": "d"})
    assert not response.is_success
    plans = superadmin.get("/super_admin/plans/").json()["plans"]
    assert name not in [p["name"] for p in plans]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A06")
def test_list_plans(superadmin):
    response = superadmin.get("/super_admin/plans/")
    assert response.status_code == 200
    body = response.json()
    assert body["total_plans"] == len(body["plans"])
    for plan in body["plans"]:
        assert {"id", "name", "description", "is_active", "tenant_count"} <= set(plan)
        assert "resources" not in plan
    full = next(p for p in body["plans"] if p["name"] == "Full")
    assert full["tenant_count"] >= 1


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A07")
def test_list_plans_with_resources(superadmin):
    body = superadmin.get("/super_admin/plans/", params={"include_resources": "true"}).json()
    full = next(p for p in body["plans"] if p["name"] == "Full")
    assert len(full["resources"]) == 66
    assert full["total_permissions"] == 66
    for plan in body["plans"]:
        assert "resources" in plan and "total_permissions" in plan


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A08")
def test_single_plan_total_permissions_counts_actions(superadmin, full_plan):
    response = superadmin.get(f"/super_admin/plans/{full_plan}", params={"include_resources": "true"})
    assert response.status_code == 200
    body = response.json()
    assert body["total_permissions"] == 276
    assert body["total_permissions"] == sum(len(r["actions"]) for r in body["resources"])


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A09")
def test_unknown_plan_404(superadmin):
    pid = str(uuid.uuid4())
    response = superadmin.get(f"/super_admin/plans/{pid}")
    assert response.status_code == 404
    assert detail_text(response) == f"Plan with ID {pid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A10")
def test_non_uuid_plan_422(superadmin):
    assert superadmin.get("/super_admin/plans/abc").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A11")
@plan_create_xfail()
def test_update_plan_description(superadmin):
    plan = tmp_tenants.make_plan(superadmin)
    response = superadmin.put(f"/super_admin/plans/{plan['id']}", params={"description": "Updated"})
    assert response.status_code == 200
    body = response.json()["plan"]
    assert body["description"] == "Updated"
    assert body["name"] == plan["name"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A12")
def test_update_without_parameters_400(superadmin, full_plan):
    response = superadmin.put(f"/super_admin/plans/{full_plan}")
    assert response.status_code == 400
    assert detail_text(response) == "No update parameters provided"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A13")
def test_update_unknown_plan_404(superadmin):
    pid = str(uuid.uuid4())
    response = superadmin.put(f"/super_admin/plans/{pid}", params={"description": "x"})
    assert response.status_code == 404
    assert detail_text(response) == f"Plan with ID {pid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A14")
@plan_create_xfail()
def test_deactivated_plan_cannot_provision(superadmin):
    plan = tmp_tenants.make_plan(superadmin, {"academic_years": ["read"]})
    assert superadmin.put(f"/super_admin/plans/{plan['id']}", params={"is_active": "false"}).status_code == 200
    response = superadmin.post(
        "/super_admin/system/tenants/", params={"client_name": "qa_tmp_" + unique("d"), "plan_id": plan["id"]}
    )
    assert response.status_code == 404
    assert detail_text(response) == "Plan not found or inactive"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A15")
@pytest.mark.parametrize("role", ROLES)
def test_plan_endpoints_denied_to_tenant_roles(role_clients, role, full_plan):
    client = role_clients[role]
    calls = [
        client.get("/super_admin/plans/"),
        client.post("/super_admin/plans/", params={"name": "qa_tmp_never", "description": "x"}),
        client.get(f"/super_admin/plans/{full_plan}"),
        client.put(f"/super_admin/plans/{full_plan}", params={"description": "x"}),
    ]
    for response in calls:
        assert response.status_code == 403
        assert detail_text(response) == SA_REQUIRED


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A16")
def test_plan_list_requires_token(bare):
    response = bare.get("/super_admin/plans/")
    assert response.status_code == 401
    assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-04-A17")
@pytest.mark.skip(reason="blocked: super_admin_audit rows cannot be read through the API and the database must not be touched")
def test_plan_audit_rows():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A01")
def test_full_plan_resources(superadmin, full_plan):
    response = superadmin.get(f"/super_admin/plans/{full_plan}/resources")
    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["id"] == full_plan and body["plan"]["name"] == "Full"
    assert body["total_resources"] == 66
    assert body["total_permissions"] == 276
    names = [r["resource"] for r in body["resources"]]
    assert names == sorted(names)
    assert all(set(r) == {"resource", "actions"} for r in body["resources"])


def widget_plan(superadmin):
    return tmp_tenants.make_plan(superadmin, {"students": ["list"]})


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A02")
@plan_create_xfail()
def test_add_plan_resource(superadmin):
    plan = widget_plan(superadmin)
    response = superadmin.post(
        f"/super_admin/plans/{plan['id']}/resources", params={"resource_name": "qa_widgets", "action_name": "read"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["added_permission"] == {"resource": "qa_widgets", "action": "read"}
    assert body["impact"]["affected_tenants"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A03")
@plan_create_xfail()
def test_add_second_action_to_resource(superadmin):
    plan = widget_plan(superadmin)
    for action in ("read", "list"):
        assert (
            superadmin.post(
                f"/super_admin/plans/{plan['id']}/resources", params={"resource_name": "qa_widgets", "action_name": action}
            ).status_code
            == 201
        )
    resources = superadmin.get(f"/super_admin/plans/{plan['id']}/resources").json()["resources"]
    assert {"resource": "qa_widgets", "actions": ["read", "list"]} in resources


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A04")
@plan_create_xfail()
def test_add_duplicate_action_400(superadmin):
    plan = widget_plan(superadmin)
    params = {"resource_name": "qa_widgets", "action_name": "read"}
    assert superadmin.post(f"/super_admin/plans/{plan['id']}/resources", params=params).status_code == 201
    again = superadmin.post(f"/super_admin/plans/{plan['id']}/resources", params=params)
    assert again.status_code == 400
    assert detail_text(again) == "Resource 'qa_widgets:read' already exists for this plan"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A05")
@plan_create_xfail()
def test_remove_one_action(superadmin):
    plan = widget_plan(superadmin)
    for action in ("read", "list"):
        superadmin.post(
            f"/super_admin/plans/{plan['id']}/resources", params={"resource_name": "qa_widgets", "action_name": action}
        )
    response = superadmin.delete(
        f"/super_admin/plans/{plan['id']}/resources", params={"resource_name": "qa_widgets", "action_name": "read"}
    )
    assert response.status_code == 200
    assert "removed_permission" in response.json()
    resources = superadmin.get(f"/super_admin/plans/{plan['id']}/resources").json()["resources"]
    assert {"resource": "qa_widgets", "actions": ["list"]} in resources


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A06")
@plan_create_xfail()
def test_remove_last_action_removes_resource(superadmin):
    plan = widget_plan(superadmin)
    superadmin.post(
        f"/super_admin/plans/{plan['id']}/resources", params={"resource_name": "qa_widgets", "action_name": "list"}
    )
    response = superadmin.delete(
        f"/super_admin/plans/{plan['id']}/resources", params={"resource_name": "qa_widgets", "action_name": "list"}
    )
    assert response.status_code == 200
    names = [r["resource"] for r in superadmin.get(f"/super_admin/plans/{plan['id']}/resources").json()["resources"]]
    assert "qa_widgets" not in names


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A07")
def test_remove_unknown_resource_404(superadmin, full_plan):
    response = superadmin.delete(
        f"/super_admin/plans/{full_plan}/resources", params={"resource_name": "nope_" + unique(), "action_name": "read"}
    )
    assert response.status_code == 404
    assert detail_text(response).startswith("Resource 'nope_")
    assert detail_text(response).endswith("' not found for this plan")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A08")
def test_remove_unknown_action_404(superadmin, full_plan):
    response = superadmin.delete(
        f"/super_admin/plans/{full_plan}/resources", params={"resource_name": "students", "action_name": "no_such_action"}
    )
    assert response.status_code == 404
    assert detail_text(response) == "Resource 'students:no_such_action' not found for this plan"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A09")
def test_plan_resource_endpoints_unknown_plan_404(superadmin):
    pid = str(uuid.uuid4())
    params = {"resource_name": "students", "action_name": "list"}
    calls = [
        superadmin.get(f"/super_admin/plans/{pid}/resources"),
        superadmin.post(f"/super_admin/plans/{pid}/resources", params=params),
        superadmin.delete(f"/super_admin/plans/{pid}/resources", params=params),
    ]
    for response in calls:
        assert response.status_code == 404
        assert detail_text(response) == f"Plan with ID {pid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A10")
def test_add_without_action_name_422(superadmin, full_plan):
    response = superadmin.post(f"/super_admin/plans/{full_plan}/resources", params={"resource_name": "qa_widgets"})
    assert response.status_code == 422
    assert "action_name" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A11")
@pytest.mark.skip(reason="blocked: adding a resource to the Full plan is forbidden by the task rules and no other plan can be created (TEN-PLAN-CREATE)")
def test_full_plan_edit_does_not_propagate():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A12")
@plan_create_xfail()
def test_affected_tenants_for_single_tenant_plan(superadmin, tmp_main):
    plan = tmp_tenants.make_plan(superadmin, {"academic_years": ["read", "list"]})
    changed = superadmin.put(f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": plan["id"]})
    try:
        assert changed.status_code == 200
        added = superadmin.post(
            f"/super_admin/plans/{plan['id']}/resources", params={"resource_name": "qa_widgets", "action_name": "read"}
        )
        assert added.json()["impact"]["affected_tenants"] == 1
    finally:
        superadmin.put(f"/super_admin/system/tenants/{tmp_main.tenant_id}/plan", params={"plan_id": tmp_main.plan_id})


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A13")
@pytest.mark.parametrize("role", ROLES)
def test_plan_resource_endpoints_denied_to_tenant_roles(role_clients, role, full_plan):
    client = role_clients[role]
    params = {"resource_name": "qa_widgets", "action_name": "read"}
    calls = [
        client.get(f"/super_admin/plans/{full_plan}/resources"),
        client.post(f"/super_admin/plans/{full_plan}/resources", params=params),
        client.delete(f"/super_admin/plans/{full_plan}/resources", params=params),
    ]
    for response in calls:
        assert response.status_code == 403
        assert detail_text(response) == SA_REQUIRED


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A14")
def test_plan_resource_endpoints_require_token(bare, full_plan):
    params = {"resource_name": "qa_widgets", "action_name": "read"}
    calls = [
        bare.get(f"/super_admin/plans/{full_plan}/resources"),
        bare.post(f"/super_admin/plans/{full_plan}/resources", params=params),
        bare.delete(f"/super_admin/plans/{full_plan}/resources", params=params),
    ]
    for response in calls:
        assert response.status_code == 401
        assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-05-A15")
@pytest.mark.skip(reason="blocked: super_admin_audit rows cannot be read through the API and the database must not be touched")
def test_plan_resource_audit_rows():
    pass
