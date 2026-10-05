import pytest

pytestmark = pytest.mark.api

SELF_SERVICE = {
    "fee_receipts": {"read_own", "list_own", "read_related", "list_related"},
    "fee_transactions": {"read_own", "list_own", "read_related", "list_related"},
    "fee_collection": {"read_related"},
}


def fee_perms(login_payload):
    return {k: set(v) for k, v in login_payload["permissions"].items() if k.startswith("fee")}


@pytest.mark.tc("TC-FEE-17-A01")
def test_login_permissions_per_role(logins):
    admin = fee_perms(logins["admin"])
    for resource in (
        "fee_categories", "fee_types", "fee_terms", "fee_class_mappings", "fee_class_mapping_term_amounts", "fee_student_mappings",
        "fee_transactions", "fee_receipts", "fee_refunds", "fee_collection", "fee_concessions", "fee_old", "fee_reports",
    ):
        assert resource in admin, resource
    assert {"approve", "process"} <= admin["fee_refunds"]
    assert {"export", "read"} == admin["fee_reports"]
    staff = fee_perms(logins["staff"])
    assert staff["fee_student_mappings"] == {"create", "list", "read", "update"}
    assert "fee_collection" not in staff and "fee_concessions" not in staff and "fee_old" not in staff
    assert staff["fee_categories"] == {"list", "read"}
    assert "delete" not in staff["fee_student_mappings"]
    assert "approve" not in staff["fee_refunds"] and "process" not in staff["fee_refunds"]
    assert fee_perms(logins["teacher"]) == {}
    for role in ("student", "parent"):
        perms = fee_perms(logins[role])
        for resource, actions in perms.items():
            assert resource in SELF_SERVICE and actions <= SELF_SERVICE[resource], (role, resource, actions)
    menu_text = str(logins["admin"]["menu"]).lower()
    assert "fee" in menu_text


@pytest.mark.tc("TC-FEE-17-A02")
@pytest.mark.skip(reason="needs a temporary grant change on the shared Student role, which would race with other workers and is not permitted in the QA tenant")
def test_grant_change_visible_after_new_login():
    pass
