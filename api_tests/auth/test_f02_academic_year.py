import uuid

import pytest

from api_tests.auth.helpers import claims_of, detail_text, fresh_login, post_login
from api_tests.support import Api


def inactive_year(anon):
    years = anon.get("/auth/academic-years").json()
    for year in years:
        if not year["is_active"]:
            return year
    return None


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A01")
def test_year_list_order_and_flags(anon, admin):
    years = anon.get("/auth/academic-years").json()
    full = admin.get("/masters/academic_years/", params={"skip": 0, "limit": 100, "active_only": "false"}).json()
    starts = {row["id"]: row["start_date"] for row in full["items"]}
    listed = [y["id"] for y in years if y["id"] in starts]
    assert listed == sorted(listed, key=lambda i: starts[i], reverse=True)
    assert any(y["is_active"] for y in years)
    assert all(set(y) == {"id", "title", "is_active"} for y in years)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A02")
def test_year_list_is_public(anon):
    assert anon.get("/auth/academic-years").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A03")
def test_login_with_inactive_year_carries_that_year(anon, new_staff):
    year = inactive_year(anon)
    if year is None:
        pytest.skip("the QA tenant has no inactive academic year")
    user = new_staff("Staff")
    done = user.activate()
    response = fresh_login(user.username, user.password, year["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["academic_year_title"] == year["title"]
    assert body["academic_year_id"] == year["id"]
    assert claims_of(body["access_token"])["academic_year_id"] == year["id"]
    assert done["role"]["name"] == "Staff"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A04")
def test_login_without_year_422(anon):
    response = anon.post("/auth/login", json={"username": "x", "password": "y"})
    assert response.status_code == 422
    assert "academic_year_id" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A05")
@pytest.mark.parametrize("value", ["", "abc", None])
def test_login_with_blank_or_malformed_year_422(anon, value):
    response = anon.post("/auth/login", json={"username": "x", "password": "y", "academic_year_id": value})
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A06")
def test_login_with_unknown_year_400(anon, new_staff):
    user = new_staff("Staff")
    user.activate()
    response = post_login(anon, user.username, user.password, str(uuid.uuid4()))
    assert response.status_code == 400
    assert detail_text(response) == "Invalid academic year"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A07")
def test_login_with_year_of_other_tenant_400(anon, tenant_b, new_staff):
    user = new_staff("Staff")
    user.activate()
    response = post_login(anon, user.username, user.password, tenant_b.academic_year_id)
    assert response.status_code == 400
    assert detail_text(response) == "Invalid academic year"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A08")
def test_wrong_password_checked_before_year(anon, logins):
    response = post_login(anon, logins["admin"]["user"]["username"], "wrong-password-1", str(uuid.uuid4()))
    assert response.status_code == 401
    assert detail_text(response) == "Invalid Credentials"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A09")
def test_refresh_keeps_year(anon, new_staff):
    year = inactive_year(anon)
    if year is None:
        pytest.skip("the QA tenant has no inactive academic year")
    user = new_staff("Staff")
    user.activate()
    login_body = fresh_login(user.username, user.password, year["id"]).json()
    refreshed = anon.post("/auth/refresh", json={"refresh_token": login_body["refresh_token"]})
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["academic_year_id"] == year["id"]
    assert body["academic_year_title"] == year["title"]


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A10")
def test_years_of_other_tenant_not_listed(anon, tenant_b, superadmin):
    mine = {y["id"] for y in anon.get("/auth/academic-years").json()}
    other = Api(tenant_header="qa_school_b")
    try:
        theirs = {y["id"] for y in other.get("/auth/academic-years").json()}
    finally:
        other.close()
    assert tenant_b.academic_year_id in theirs
    assert not (mine & theirs)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-02-A11")
def test_activating_a_year_makes_it_the_only_active_year(admin, anon, year_id):
    years = anon.get("/auth/academic-years").json()
    previously_active = [y["id"] for y in years if y["is_active"]]
    target = next((y for y in years if not y["is_active"]), None)
    if target is None or len(previously_active) != 1:
        pytest.skip("needs exactly one active and one inactive academic year")
    try:
        response = admin.put(f"/masters/academic_years/{target['id']}", json={"is_active": True})
        assert response.status_code == 200, response.text
        after = anon.get("/auth/academic-years").json()
        assert [y["id"] for y in after if y["is_active"]] == [target["id"]]
    finally:
        restore = admin.put(f"/masters/academic_years/{previously_active[0]}", json={"is_active": True})
        assert restore.status_code == 200, restore.text
    final = anon.get("/auth/academic-years").json()
    assert [y["id"] for y in final if y["is_active"]] == previously_active
