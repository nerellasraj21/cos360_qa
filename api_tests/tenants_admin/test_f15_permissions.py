import uuid

import pytest

from api_tests.auth.helpers import detail_text, grant_permission
from api_tests.support import unique
from api_tests.tenants_admin.conftest import MISSING_AUTH, NON_ADMIN, denied_text

RP = "/auth/resource-permissions"
RM = "/admin/role-mgmt"


def put_perm(admin, role_id, resource, action, granted=True):
    return admin.put(
        f"{RM}/roles/{role_id}/permissions",
        params={"resource": resource, "action": action, "is_granted": "true" if granted else "false"},
    )


def create_rp(admin, role_id, resource, action, granted=True):
    return admin.post(RP + "/", json={"role_id": role_id, "resource": resource, "action": action, "is_granted": granted})


def rows_of(admin, role_id):
    return admin.get(f"{RP}/role/{role_id}").json()


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A01")
def test_role_permission_view(admin, role_ids):
    response = admin.get(f"{RM}/roles/{role_ids['Staff']}/permissions")
    assert response.status_code == 200
    body = response.json()
    summary = body["summary"]
    assert summary["total_permissions"] == summary["granted_permissions"] + summary["denied_permissions"]
    assert summary["resources_count"] == len(body["permissions"])
    assert body["role"]["name"] == "Staff"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A02")
def test_role_permission_view_unknown_role(admin):
    rid = str(uuid.uuid4())
    response = admin.get(f"{RM}/roles/{rid}/permissions")
    assert response.status_code == 404
    assert detail_text(response) == f"Role with ID {rid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A03")
def test_put_creates_permission(admin, custom_role):
    role = custom_role()
    response = put_perm(admin, role["id"], "tenadm_w", "read")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Permission created successfully"
    assert body["action_taken"] == "created"
    assert body["permission"] == {"resource": "tenadm_w", "action": "read", "old_value": None, "new_value": True}
    assert isinstance(body["impact"]["affected_users"], int)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A04")
def test_put_updates_permission(admin, custom_role):
    role = custom_role()
    put_perm(admin, role["id"], "tenadm_w", "read")
    response = put_perm(admin, role["id"], "tenadm_w", "read", granted=False)
    body = response.json()
    assert response.status_code == 200
    assert body["message"] == "Permission updated successfully"
    assert body["permission"]["old_value"] is True and body["permission"]["new_value"] is False


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A05")
def test_grant_and_revoke_apply_to_existing_token(admin, custom_role, new_staff, api_client):
    role = custom_role()
    user = new_staff("Staff", role_id=role["id"])
    client = api_client(token=user.login_data()["access_token"])
    assert client.get("/admin/users/").status_code == 403
    put_perm(admin, role["id"], "user_management", "list")
    assert client.get("/admin/users/").status_code == 200
    put_perm(admin, role["id"], "user_management", "list", granted=False)
    assert client.get("/admin/users/").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A06")
def test_put_requires_is_granted_boolean(admin, custom_role):
    role = custom_role()
    url = f"{RM}/roles/{role['id']}/permissions"
    assert admin.put(url, params={"resource": "tenadm_w", "action": "read"}).status_code == 422
    assert admin.put(url, params={"resource": "tenadm_w", "action": "read", "is_granted": "maybe"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A07")
def test_put_resource_50_characters(admin, custom_role):
    role = custom_role()
    assert put_perm(admin, role["id"], "r" * 50, "read").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A07")
@pytest.mark.xfail(strict=True, reason="TEN-NAME-LENGTH: an over-long resource name fails in the database and answers 500 instead of a validation error")
def test_put_resource_51_characters_is_not_a_server_error(admin, custom_role):
    role = custom_role()
    assert put_perm(admin, role["id"], "r" * 51, "read").status_code != 500


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A08")
def test_put_action_30_characters(admin, custom_role):
    role = custom_role()
    assert put_perm(admin, role["id"], "tenadm_w", "a" * 30).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A08")
@pytest.mark.xfail(strict=True, reason="TEN-NAME-LENGTH: an over-long action name fails in the database and answers 500 instead of a validation error")
def test_put_action_31_characters_is_not_a_server_error(admin, custom_role):
    role = custom_role()
    assert put_perm(admin, role["id"], "tenadm_w", "a" * 31).status_code != 500


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A09")
def test_put_unknown_role_404(admin):
    rid = str(uuid.uuid4())
    response = put_perm(admin, rid, "tenadm_w", "read")
    assert response.status_code == 404
    assert detail_text(response) == f"Role with ID {rid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A10")
def test_admin_can_grant_pair_outside_plan_to_own_role(admin, role_ids, cleanup):
    resource = unique("tenadm_w")
    grant_permission(admin, cleanup, role_ids["Admin"], resource, "read")
    rows = [r for r in rows_of(admin, role_ids["Admin"]) if r["resource"] == resource]
    assert len(rows) == 1 and rows[0]["is_granted"] is True


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A11")
def test_bulk_update_counts(admin, custom_role):
    role = custom_role()
    put_perm(admin, role["id"], "tenadm_w", "read")
    body = {
        "permissions": [
            {"resource": "tenadm_w", "action": "read", "is_granted": False},
            {"resource": "tenadm_w", "action": "list", "is_granted": True},
            {"resource": "tenadm_w", "action": "update", "is_granted": True},
        ]
    }
    response = admin.post(f"{RM}/roles/{role['id']}/permissions/bulk", json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Bulk permission update completed successfully"
    assert data["summary"]["created_permissions"] == 2
    assert data["summary"]["updated_permissions"] == 1
    assert data["summary"]["total_changes"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A12")
@pytest.mark.parametrize("body", [{"permissions": []}, {}], ids=["empty", "missing"])
def test_bulk_without_permissions_400(admin, custom_role, body):
    role = custom_role()
    response = admin.post(f"{RM}/roles/{role['id']}/permissions/bulk", json=body)
    assert response.status_code == 400
    assert detail_text(response) == "No permissions provided in request body"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A13")
def test_bulk_skips_items_without_resource(admin, custom_role):
    role = custom_role()
    body = {"permissions": [{"action": "read", "is_granted": True}, {"resource": "tenadm_w", "action": "read", "is_granted": True}]}
    response = admin.post(f"{RM}/roles/{role['id']}/permissions/bulk", json=body)
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["total_processed"] == 2 and summary["total_changes"] == 1


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A14")
def test_bulk_unknown_role_404(admin):
    rid = str(uuid.uuid4())
    response = admin.post(f"{RM}/roles/{rid}/permissions/bulk", json={"permissions": [{"resource": "a", "action": "read"}]})
    assert response.status_code == 404
    assert detail_text(response) == f"Role with ID {rid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A15")
def test_templates_listing(admin):
    response = admin.get(f"{RM}/templates/")
    assert response.status_code == 200
    body = response.json()
    assert body["total_templates"] == 5
    assert set(body["templates"]) == {"Admin", "Teacher", "Staff", "Student", "Parent"}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A16")
def test_apply_teacher_template(admin, custom_role):
    role = custom_role()
    response = admin.post(f"{RM}/roles/{role['id']}/apply-template", params={"template_name": "Teacher"})
    assert response.status_code == 200
    assert response.json()["permissions_applied"] == 15
    rows = rows_of(admin, role["id"])
    assert len(rows) == 15 and all(r["is_granted"] for r in rows)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A17")
@pytest.mark.parametrize("template,count", [("Admin", 30), ("Staff", 13), ("Student", 8), ("Parent", 8)])
def test_apply_other_templates(admin, custom_role, template, count):
    role = custom_role()
    response = admin.post(f"{RM}/roles/{role['id']}/apply-template", params={"template_name": template})
    assert response.status_code == 200
    assert response.json()["permissions_applied"] == count


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A18")
def test_template_regrants_revoked_row(admin, custom_role):
    role = custom_role()
    admin.post(f"{RM}/roles/{role['id']}/apply-template", params={"template_name": "Teacher"})
    put_perm(admin, role["id"], "academic_years", "read", granted=False)
    admin.post(f"{RM}/roles/{role['id']}/apply-template", params={"template_name": "Teacher"})
    row = next(r for r in rows_of(admin, role["id"]) if r["resource"] == "academic_years" and r["action"] == "read")
    assert row["is_granted"] is True


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A19")
def test_unknown_template_400(admin, custom_role):
    role = custom_role()
    response = admin.post(f"{RM}/roles/{role['id']}/apply-template", params={"template_name": "Librarian"})
    assert response.status_code == 400
    assert detail_text(response) == "Template 'Librarian' not found. Available: ['Admin', 'Teacher', 'Staff', 'Student', 'Parent']"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A20")
def test_apply_template_unknown_role_404(admin):
    rid = str(uuid.uuid4())
    response = admin.post(f"{RM}/roles/{rid}/apply-template", params={"template_name": "Teacher"})
    assert response.status_code == 404
    assert detail_text(response) == f"Role with ID {rid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A21")
def test_admin_template_does_not_open_real_endpoints(admin, custom_role, new_staff, api_client):
    role = custom_role()
    admin.post(f"{RM}/roles/{role['id']}/apply-template", params={"template_name": "Admin"})
    user = new_staff("Staff", role_id=role["id"])
    client = api_client(token=user.login_data()["access_token"])
    assert client.get("/admin/users/").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A22")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_role_permission_endpoints_denied(role_clients, logins, role, role_ids):
    client = role_clients[role]
    rid = role_ids["Staff"]
    name = logins[role]["role"]["name"]
    expectations = [
        (client.get(f"{RM}/roles/{rid}/permissions"), "read"),
        (client.put(f"{RM}/roles/{rid}/permissions", params={"resource": "tenadm_never", "action": "read", "is_granted": "true"}), "update"),
        (client.post(f"{RM}/roles/{rid}/permissions/bulk", json={"permissions": [{"resource": "tenadm_never", "action": "read"}]}), "update"),
        (client.get(f"{RM}/templates/"), "read"),
        (client.post(f"{RM}/roles/{rid}/apply-template", params={"template_name": "Teacher"}), "update"),
    ]
    for response, action in expectations:
        assert response.status_code == 403
        assert detail_text(response) == denied_text(name, action, "role_management")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A23")
def test_create_resource_permission_normalises_names(admin, custom_role):
    role = custom_role()
    response = create_rp(admin, role["id"], "TenAdm_W", "READ")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "role_id", "resource", "action", "is_granted"}
    assert body["resource"] == "tenadm_w" and body["action"] == "read"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A24")
def test_duplicate_resource_permission_400(admin, custom_role):
    role = custom_role()
    create_rp(admin, role["id"], "tenadm_w", "read")
    response = create_rp(admin, role["id"], "tenadm_w", "read")
    assert response.status_code == 400
    assert detail_text(response) == "Permission 'tenadm_w:read' already exists for role"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A25")
def test_create_for_unknown_role_404(admin):
    rid = str(uuid.uuid4())
    response = create_rp(admin, rid, "tenadm_w", "read")
    assert response.status_code == 404
    assert detail_text(response) == f"Role with ID {rid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A26")
@pytest.mark.parametrize(
    "resource,action",
    [("tenadm w", "read"), ("tenadm_w", "1bad"), ("r" * 51, "read"), ("tenadm_w", "a" * 31)],
    ids=["space", "digit_first", "resource51", "action31"],
)
def test_create_validation_422(admin, custom_role, resource, action):
    role = custom_role()
    assert create_rp(admin, role["id"], resource, action).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A27")
def test_create_revoked_permission(admin, custom_role):
    role = custom_role()
    response = create_rp(admin, role["id"], "tenadm_w", "read", granted=False)
    assert response.status_code == 201 and response.json()["is_granted"] is False


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A28")
def test_list_resource_permissions_pagination(admin):
    response = admin.get(RP + "/", params={"skip": 0, "limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 10
    assert body["total_count"] > 10
    assert body["has_next"] is True
    last = admin.get(RP + "/", params={"skip": body["total_count"] - 1, "limit": 10}).json()
    assert last["has_next"] is False and 1 <= len(last["items"]) <= 10


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A29")
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 1001}, {"skip": -1}])
def test_list_bounds_422(admin, params):
    assert admin.get(RP + "/", params=params).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A29")
def test_list_limit_1000_accepted(admin):
    assert admin.get(RP + "/", params={"limit": 1000}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A30")
def test_get_resource_permission(admin, custom_role):
    role = custom_role()
    created = create_rp(admin, role["id"], "tenadm_w", "read").json()
    response = admin.get(f"{RP}/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A31")
def test_unknown_permission_id_404(admin):
    pid = str(uuid.uuid4())
    for response in (admin.get(f"{RP}/{pid}"), admin.put(f"{RP}/{pid}", json={"is_granted": False}), admin.delete(f"{RP}/{pid}")):
        assert response.status_code == 404
        assert detail_text(response) == f"Permission with ID {pid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A32")
def test_update_resource_permission_revokes(admin, custom_role):
    role = custom_role()
    created = create_rp(admin, role["id"], "tenadm_w", "read").json()
    response = admin.put(f"{RP}/{created['id']}", json={"is_granted": False})
    assert response.status_code == 200 and response.json()["is_granted"] is False


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A33")
def test_update_ignores_other_fields(admin, custom_role):
    role = custom_role()
    created = create_rp(admin, role["id"], "tenadm_w", "read").json()
    response = admin.put(
        f"{RP}/{created['id']}", json={"role_id": role["id"], "resource": "other", "action": "list", "is_granted": True}
    )
    assert response.status_code == 200
    assert response.json()["resource"] == "tenadm_w" and response.json()["action"] == "read"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A34")
def test_delete_resource_permission(admin, custom_role):
    role = custom_role()
    created = create_rp(admin, role["id"], "tenadm_w", "read").json()
    assert admin.delete(f"{RP}/{created['id']}").status_code == 204
    assert admin.delete(f"{RP}/{created['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A35")
def test_rows_of_role_include_revoked(admin, custom_role):
    role = custom_role()
    create_rp(admin, role["id"], "tenadm_w", "read")
    create_rp(admin, role["id"], "tenadm_w", "list", granted=False)
    rows = rows_of(admin, role["id"])
    assert {(r["action"], r["is_granted"]) for r in rows} == {("read", True), ("list", False)}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A36")
def test_rows_of_unknown_role_empty(admin):
    response = admin.get(f"{RP}/role/{uuid.uuid4()}")
    assert response.status_code == 200 and response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A37")
def test_rows_of_resource_carry_role_name(admin, custom_role):
    role = custom_role()
    resource = unique("tenadm_w")
    create_rp(admin, role["id"], resource, "read")
    rows = admin.get(f"{RP}/resource/{resource}").json()
    assert len(rows) == 1
    assert rows[0]["role_name"] == role["name"]
    assert "role_description" in rows[0]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A38")
def test_bulk_create_returns_only_new_rows(admin, custom_role):
    role = custom_role()
    create_rp(admin, role["id"], "tenadm_w", "read")
    response = admin.post(
        RP + "/bulk",
        json={
            "role_id": role["id"],
            "permissions": [
                {"resource": "tenadm_w", "action": "read", "is_granted": True},
                {"resource": "tenadm_w", "action": "list", "is_granted": True},
            ],
        },
    )
    assert response.status_code == 200
    rows = response.json()
    assert [(r["resource"], r["action"]) for r in rows] == [("tenadm_w", "list")]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A39")
def test_bulk_create_unknown_role_404(admin):
    rid = str(uuid.uuid4())
    response = admin.post(RP + "/bulk", json={"role_id": rid, "permissions": [{"resource": "tenadm_w", "action": "read", "is_granted": True}]})
    assert response.status_code == 404
    assert detail_text(response) == f"Role with ID {rid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A40")
def test_role_summary(admin, custom_role):
    role = custom_role()
    create_rp(admin, role["id"], "tenadm_w", "read")
    create_rp(admin, role["id"], "tenadm_w", "list", granted=False)
    body = admin.get(f"{RP}/role/{role['id']}/summary").json()
    assert body["total_permissions"] == body["granted_permissions"] + body["denied_permissions"] == len(body["permissions"]) == 2
    assert body["role_name"] == role["name"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A41")
def test_summary_unknown_role_404(admin):
    rid = str(uuid.uuid4())
    response = admin.get(f"{RP}/role/{rid}/summary")
    assert response.status_code == 404
    assert detail_text(response) == f"Role with ID {rid} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A42")
def test_matrix(admin, custom_role):
    role = custom_role()
    create_rp(admin, role["id"], "tenadm_w", "read")
    matrix = admin.get(RP + "/matrix/all").json()
    names = [m["role_name"] for m in matrix]
    assert names == sorted(names, key=str.lower)
    entry = next(m for m in matrix if m["role_id"] == role["id"])
    assert entry["permissions_by_resource"] == {"tenadm_w": {"read": True}}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A43")
def test_delete_all_of_a_role(admin, custom_role):
    role = custom_role()
    create_rp(admin, role["id"], "tenadm_w", "read")
    create_rp(admin, role["id"], "tenadm_w", "list")
    response = admin.delete(f"{RP}/role/{role['id']}/all")
    assert response.status_code == 200
    assert response.json() == {"message": f"Deleted 2 permissions for role {role['id']}"}
    assert rows_of(admin, role["id"]) == []


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A44")
def test_delete_all_of_a_resource(admin, custom_role):
    first, second = custom_role(), custom_role()
    resource = unique("tenadm_w")
    create_rp(admin, first["id"], resource, "read")
    create_rp(admin, second["id"], resource, "read")
    response = admin.delete(f"{RP}/resource/{resource}/all")
    assert response.status_code == 200
    assert response.json() == {"message": f"Deleted 2 permissions for resource '{resource}'"}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A45")
def test_resource_dropdown(admin, custom_role):
    role = custom_role()
    resource = unique("tenadm_w")
    create_rp(admin, role["id"], resource, "read")
    items = admin.get(RP + "/dropdown/resources").json()
    names = {i["resource"]: i["display_name"] for i in items}
    assert names["academic_years"] == "Academic Years"
    assert names[resource] == resource.replace("_", " ").title()


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A46")
def test_action_dropdown(admin, custom_role):
    role = custom_role()
    create_rp(admin, role["id"], unique("tenadm_w"), "read_own")
    names = {i["action"]: i["display_name"] for i in admin.get(RP + "/dropdown/actions").json()}
    assert names["read_own"] == "Read Own"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A47")
def test_check_endpoint(admin, custom_role):
    role = custom_role()
    create_rp(admin, role["id"], "tenadm_w", "read")
    create_rp(admin, role["id"], "tenadm_w", "list", granted=False)

    def check(action):
        return admin.get(f"{RP}/check/{role['id']}/tenadm_w/{action}").json()

    assert check("read") == {"role_id": role["id"], "resource": "tenadm_w", "action": "read", "permission_granted": True}
    assert check("list")["permission_granted"] is False
    assert check("update")["permission_granted"] is False


def every_call(client, rid):
    pid = str(uuid.uuid4())
    body = {"role_id": rid, "resource": "tenadm_never", "action": "read", "is_granted": True}
    return [
        (client.post(RP + "/", json=body), "create"),
        (client.get(RP + "/"), "list"),
        (client.get(f"{RP}/{pid}"), "read"),
        (client.put(f"{RP}/{pid}", json={"is_granted": False}), "update"),
        (client.delete(f"{RP}/{pid}"), "delete"),
        (client.get(f"{RP}/role/{rid}"), "read"),
        (client.get(f"{RP}/resource/tenadm_never"), "read"),
        (client.post(RP + "/bulk", json={"role_id": rid, "permissions": [{"resource": "tenadm_never", "action": "read", "is_granted": True}]}), "create"),
        (client.get(f"{RP}/role/{rid}/summary"), "read"),
        (client.get(RP + "/matrix/all"), "read"),
        (client.delete(f"{RP}/role/{rid}/all"), "delete"),
        (client.delete(f"{RP}/resource/tenadm_never/all"), "delete"),
        (client.get(RP + "/dropdown/resources"), "read"),
        (client.get(RP + "/dropdown/actions"), "read"),
        (client.get(f"{RP}/check/{rid}/tenadm_never/read"), "read"),
    ]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A48")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_resource_permission_endpoints_denied(role_clients, logins, role, custom_role):
    target = custom_role()
    name = logins[role]["role"]["name"]
    for response, action in every_call(role_clients[role], target["id"]):
        assert response.status_code == 403
        assert detail_text(response) == denied_text(name, action, "resource_permission_management")
    assert rows_of(role_clients["admin"], target["id"]) == []


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A48")
def test_resource_permission_reads_allowed_for_admin(admin, custom_role):
    role = custom_role()
    for path in (RP + "/", f"{RP}/role/{role['id']}", RP + "/matrix/all", RP + "/dropdown/resources", RP + "/dropdown/actions"):
        assert admin.get(path).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A49")
def test_resource_permission_endpoints_require_token(anon, role_ids):
    for response, _ in every_call(anon, role_ids["Staff"]):
        assert response.status_code == 401
        assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A50")
def test_other_tenant_permissions_invisible(admin, tenant_b, custom_role):
    foreign_roles = {r["name"]: r["id"] for r in tenant_b.get("/admin/role-mgmt/roles/").json()["roles"]}
    foreign_row = tenant_b.get(RP + "/", params={"limit": 1}).json()["items"][0]
    assert admin.get(f"{RP}/{foreign_row['id']}").status_code == 404
    assert admin.get(f"{RP}/role/{foreign_roles['Staff']}").json() == []
    assert admin.get(f"{RP}/role/{foreign_roles['Staff']}/summary").status_code == 404
    mine = {r["role_id"] for r in admin.get(RP + "/matrix/all").json()}
    assert foreign_roles["Staff"] not in mine


@pytest.mark.api
@pytest.mark.tc("TC-TEN-15-A51")
def test_grant_shows_at_next_login_only(admin, custom_role, new_staff):
    role = custom_role()
    user = new_staff("Staff", role_id=role["id"])
    before = user.login_data()
    resource = unique("tenadm_w")
    create_rp(admin, role["id"], resource, "read")
    after = user.login_data()
    assert resource not in before["permissions"]
    assert after["permissions"][resource] == ["read"]
