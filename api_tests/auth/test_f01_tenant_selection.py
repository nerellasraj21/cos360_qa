import pytest

from api_tests.auth.helpers import detail_text
from api_tests.support import QA_B_TENANT, QA_TENANT, Api


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A01")
def test_academic_years_public_with_header(anon):
    response = anon.get("/auth/academic-years")
    assert response.status_code == 200
    years = response.json()
    assert isinstance(years, list) and years
    for year in years:
        assert set(year) == {"id", "title", "is_active"}
        assert isinstance(year["is_active"], bool)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A02")
def test_header_is_sanitised(anon):
    plain = anon.get("/auth/academic-years").json()
    shouting = Api(tenant_header="QA_School")
    try:
        response = shouting.get("/auth/academic-years")
    finally:
        shouting.close()
    assert response.status_code == 200
    assert [y["id"] for y in response.json()] == [y["id"] for y in plain]


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A03")
def test_unknown_tenant_404():
    client = Api(tenant_header="no_such_school")
    try:
        response = client.get("/auth/academic-years")
    finally:
        client.close()
    assert response.status_code == 404
    assert detail_text(response) == "Tenant 'no_such_school' not found or inactive"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A04")
def test_invalid_header_characters_rejected_with_400():
    client = Api(tenant_header="!!!")
    try:
        response = client.get("/auth/academic-years")
    finally:
        client.close()
    assert response.status_code == 400
    assert "Invalid 'cschema' header" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A04")
def test_invalid_header_returns_no_data():
    client = Api(tenant_header="!!!")
    try:
        response = client.get("/auth/academic-years")
    finally:
        client.close()
    assert response.status_code >= 400
    assert "title" not in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A05")
def test_missing_header_and_token_rejected_with_400():
    client = Api()
    try:
        response = client.get("/auth/academic-years")
    finally:
        client.close()
    assert response.status_code == 400
    assert "Tenant must be specified via 'cschema' header" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A05")
def test_missing_header_and_token_returns_no_data():
    client = Api()
    try:
        response = client.get("/auth/academic-years")
    finally:
        client.close()
    assert response.status_code >= 400
    assert "title" not in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A06")
def test_header_with_space_cannot_address_tenant():
    client = Api(tenant_header="qa school")
    try:
        response = client.get("/auth/academic-years")
    finally:
        client.close()
    assert response.status_code == 404
    assert detail_text(response) == "Tenant 'qaschool' not found or inactive"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A07")
def test_deactivated_tenant_not_found(superadmin, tmp_main):
    tmp_main.set_active(False)
    try:
        client = tmp_main.anon()
        try:
            response = client.get("/auth/academic-years")
        finally:
            client.close()
        assert response.status_code == 404
        assert detail_text(response) == f"Tenant '{tmp_main.client_name}' not found or inactive"
    finally:
        tmp_main.set_active(True)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A08")
def test_token_with_other_tenant_header_forbidden(admin):
    response = admin.get("/admin/users/", headers={"cschema": QA_B_TENANT})
    assert response.status_code == 403
    assert detail_text(response) == "Tenant does not match your session"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A09")
def test_token_with_same_tenant_header_ok(admin):
    response = admin.get("/admin/users/", headers={"cschema": QA_TENANT})
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A10")
def test_token_without_header_uses_token_tenant(admin, logins):
    response = admin.get("/admin/users/", params={"search": logins["admin"]["user"]["username"]})
    assert response.status_code == 200
    names = {u["username"] for u in response.json()["users"]}
    assert logins["admin"]["user"]["username"] in names


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A11")
def test_token_of_deactivated_tenant_invalid_connection(superadmin, tmp_main):
    token = tmp_main.admin_login()["access_token"]
    client = Api(token=token)
    try:
        assert client.get("/admin/users/").status_code == 200
        tmp_main.set_active(False)
        try:
            response = client.get("/admin/users/")
            assert response.status_code == 401
            assert detail_text(response) == "Invalid connection"
        finally:
            tmp_main.set_active(True)
        assert client.get("/admin/users/").status_code == 200
    finally:
        client.close()


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A12")
def test_token_without_tenant_claim_out_of_date(logins):
    from api_tests.auth.helpers import mint

    token = mint({"sub": logins["admin"]["user"]["id"], "username": "qa_admin", "role": "Admin"})
    client = Api(token=token, tenant_header=QA_TENANT)
    try:
        response = client.get("/admin/users/")
    finally:
        client.close()
    assert response.status_code == 401
    assert detail_text(response) == "Your session is out of date. Please log in again."


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-01-A13")
def test_same_username_in_two_tenants_isolated(admin, tenant_b, cleanup, new_staff):
    mine = new_staff("Staff")
    listing = admin.get("/admin/users/", params={"search": mine.username}).json()
    assert [u["username"] for u in listing["users"]] == [mine.username]
    other = tenant_b.get("/admin/users/", params={"search": mine.username}).json()
    assert other["users"] == []
    assert other["total"] == 0
    names_a = {u["username"] for u in admin.get("/admin/users/", params={"search": mine.username}).json()["users"]}
    names_b = {u["username"] for u in tenant_b.get("/admin/users/?limit=100").json()["users"]}
    assert mine.username in names_a
    assert mine.username not in names_b
