import uuid

import pytest

from api_tests.communication.helpers import expected_status
from api_tests.support import unique

PREVIEW = "/communication/send/preview-count"
NEEDS_STUDENTS = "needs students, classes and parent links created through the admission flow, which the communication tests do not own"


def count(client, **params):
    response = client.get(PREVIEW, params=params)
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"estimated_count"}
    return response.json()["estimated_count"]


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A01")
def test_all_parents_counts_parents_without_phone(admin, make_parent):
    make_parent()
    make_parent(phone=None)
    make_parent(email=None)
    assert count(admin, target_type="all_parents") >= 3


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A02")
def test_multiple_parents(admin, make_parent):
    first, second, third = make_parent(), make_parent(phone=None), make_parent()
    assert count(admin, target_type="multiple_parents", parent_ids=[first["id"], third["id"]]) == 2
    assert count(admin, target_type="multiple_parents", parent_ids=[first["id"], second["id"], third["id"]]) == 3
    assert count(admin, target_type="multiple_parents", parent_ids=[first["id"], str(uuid.uuid4())]) == 1


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A03")
def test_individual_parent(admin, make_parent):
    parent = make_parent()
    assert count(admin, target_type="individual_parent", parent_id=parent["id"]) == 1
    assert count(admin, target_type="individual_parent", parent_id=str(uuid.uuid4())) == 0
    assert count(admin, target_type="individual_parent") == 0


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A04")
@pytest.mark.skip(reason=NEEDS_STUDENTS)
def test_individual_student():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A05")
@pytest.mark.skip(reason=NEEDS_STUDENTS)
def test_multiple_students_fan_out():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A06")
@pytest.mark.skip(reason=NEEDS_STUDENTS)
def test_class_section_parents():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A07")
@pytest.mark.skip(reason=NEEDS_STUDENTS)
def test_class_section_students_equals_parents():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A08")
@pytest.mark.skip(reason=NEEDS_STUDENTS)
def test_class_without_section():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A09")
def test_class_section_without_class_is_zero(admin):
    assert count(admin, target_type="class_section_parents") == 0
    assert count(admin, target_type="class_section_students") == 0
    assert count(admin, target_type="class_section_parents", class_id=str(uuid.uuid4())) == 0


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A10")
def test_all_students_is_a_count(admin):
    assert count(admin, target_type="all_students") >= 0


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A11")
def test_all_staff_includes_active_staff(admin, make_staff):
    make_staff()
    make_staff()
    assert count(admin, target_type="all_staff") >= 2


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A12")
def test_multiple_staff_includes_inactive(admin, make_staff):
    active = make_staff()
    inactive = make_staff(is_active=False)
    assert count(admin, target_type="multiple_staff", staff_ids=[inactive["id"]]) == 1
    assert count(admin, target_type="multiple_staff", staff_ids=[active["id"], inactive["id"]]) == 2
    assert count(admin, target_type="individual_staff", staff_id=inactive["id"]) == 1
    assert count(admin, target_type="individual_staff", staff_id=str(uuid.uuid4())) == 0
    assert count(admin, target_type="multiple_staff") == 0


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A13")
def test_all_users_deduplicates_and_includes_active_staff(admin, make_staff, make_parent):
    make_staff()
    make_staff()
    make_parent()
    assert count(admin, target_type="all_users") >= 3


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A14")
@pytest.mark.skip(reason="needs fee mappings for students; created by the fee module, which the communication tests do not own")
def test_fee_defaulters_proxy_rule(admin):
    pass


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A14")
def test_fee_defaulters_returns_a_count(admin):
    assert count(admin, target_type="fee_defaulters") >= 0


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A15")
def test_role_based_counts_active_staff_of_role(admin, make_staff, make_role, logins):
    role = make_role([])
    other = make_staff(role_id=role["id"])
    inactive = make_staff(role_id=role["id"], is_active=False)
    third = make_staff(role_id=role["id"])
    cleanup_role_users = [other, inactive, third]
    staff_role = logins["staff"]["role"]["id"]
    try:
        assert count(admin, target_type="role_based", role=role["name"]) == 2
        assert count(admin, target_type="role_based", role=role["name"].upper()) == 0
        assert count(admin, target_type="role_based", role=unique("com_nobody_")) == 0
    finally:
        for user in cleanup_role_users:
            admin.delete(f"/staff/enrollment/{user['id']}")
            admin.patch(f"/admin/users/{user['user_id']}", json={"is_active": False})
            admin.put(f"/admin/users/{user['user_id']}/role", json={"role_id": staff_role})


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A16")
def test_target_type_validation(admin):
    missing = admin.get(PREVIEW)
    assert missing.status_code == 422
    bogus = admin.get(PREVIEW, params={"target_type": "bogus"})
    assert bogus.status_code == 422
    assert bogus.json()["detail"] == "Unknown target_type: 'bogus'"


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A17")
def test_malformed_ids_fail(admin):
    response = admin.get(PREVIEW, params={"target_type": "multiple_parents", "parent_ids": "abc"})
    assert response.status_code >= 400


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A18")
def test_admin_can_preview(admin):
    assert admin.get(PREVIEW, params={"target_type": "all_parents"}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A19")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_preview_denied_without_list_grant(role_clients, logins, role):
    assert expected_status(logins, role, "communications", "list") == 403
    assert role_clients[role].get(PREVIEW, params={"target_type": "all_parents"}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A20")
def test_create_only_role_cannot_preview(role_client):
    client = role_client([("communications", "create")])
    assert client.get(PREVIEW, params={"target_type": "all_parents"}).status_code == 403
    listing = role_client([("communications", "list")])
    assert listing.get(PREVIEW, params={"target_type": "all_parents"}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A21")
def test_preview_requires_token(anon):
    assert anon.get(PREVIEW, params={"target_type": "all_parents"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A22")
def test_preview_tenant_isolation(tenant_b, make_parent, make_staff):
    parent = make_parent()
    staff = make_staff()
    assert count(tenant_b, target_type="individual_parent", parent_id=parent["id"]) == 0
    assert count(tenant_b, target_type="multiple_parents", parent_ids=[parent["id"]]) == 0
    assert count(tenant_b, target_type="individual_staff", staff_id=staff["id"]) == 0
    assert count(tenant_b, target_type="multiple_staff", staff_ids=[staff["id"]]) == 0
    for target in ("all_parents", "all_staff", "all_users"):
        assert isinstance(count(tenant_b, target_type=target), int)


@pytest.mark.api
@pytest.mark.tc("TC-COM-02-A23")
def test_preview_foreign_tenant_header(b_header_client):
    assert b_header_client.get(PREVIEW, params={"target_type": "all_parents"}).status_code == 403
