import pytest


@pytest.mark.api
@pytest.mark.tc("TC-QA-00-A01")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher", "student", "parent"])
def test_every_role_can_log_in(logins, role):
    assert logins[role]["role"]["name"].lower() == role
    assert logins[role]["client_name"] == "qa_school"


@pytest.mark.api
@pytest.mark.tc("TC-QA-00-A02")
def test_admin_client_reads_tenant_data(admin):
    response = admin.get("/masters/academic_years/")
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-QA-00-A03")
def test_super_admin_and_second_tenant(superadmin, tenant_b):
    response = tenant_b.get("/auth/academic-years", headers={"cschema": "qa_school_b"})
    assert response.status_code == 200
