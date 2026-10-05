import pytest

from api_tests.support import QA_B_TENANT, unique
from api_tests.timetable_calendar.helpers import DENIED, HOL, RANDOM_ID, ROLES, holiday_body, make_holiday

ITEM_KEYS = {"id", "name", "description", "start_date", "end_date", "is_active", "academic_year_id", "color"}
READERS = ["admin", "staff", "teacher"]
NO_GRANT = ["student", "parent"]


def ids(response):
    return [i["id"] for i in response.json()["items"]]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-01-A01")
def test_list_default_limit_is_ten(admin, cleanup, pool):
    year = pool["year2"]["id"]
    for _ in range(12):
        make_holiday(admin, cleanup, year)
    response = admin.get(f"{HOL}/?academic_year_id={year}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["total_count"] >= 12
    assert data["has_next"] is True


@pytest.mark.api
@pytest.mark.tc("TC-TTC-01-A02")
def test_list_second_page(admin, cleanup, pool):
    year = pool["year2"]["id"]
    for _ in range(3):
        make_holiday(admin, cleanup, year)
    first = admin.get(f"{HOL}/?academic_year_id={year}&skip=0&limit=2").json()
    total = first["total_count"]
    assert total >= 3 and first["has_next"] is True
    last = admin.get(f"{HOL}/?academic_year_id={year}&skip={total - 2}&limit=2").json()
    assert len(last["items"]) >= 1
    assert last["has_next"] is ((total - 2 + 2) < last["total_count"])


@pytest.mark.api
@pytest.mark.tc("TC-TTC-01-A03")
def test_list_limit_100_filters_by_year(admin, cleanup, pool):
    mine = [make_holiday(admin, cleanup, pool["year2"]["id"]) for _ in range(3)]
    other = make_holiday(admin, cleanup, pool["year"]["id"])
    response = admin.get(f"{HOL}/?limit=100&academic_year_id={pool['year2']['id']}")
    assert response.status_code == 200
    got = ids(response)
    assert all(m["id"] in got for m in mine)
    assert other["id"] not in got
    assert all(i["academic_year_id"] == pool["year2"]["id"] for i in response.json()["items"])


@pytest.mark.api
@pytest.mark.tc("TC-TTC-01-A04")
def test_list_hides_inactive_by_default(admin, cleanup, pool):
    year = pool["year2"]["id"]
    inactive = make_holiday(admin, cleanup, year, is_active=False)
    default = admin.get(f"{HOL}/?academic_year_id={year}&limit=1000")
    assert inactive["id"] not in ids(default)
    full = admin.get(f"{HOL}/?academic_year_id={year}&limit=1000&active_only=false")
    assert inactive["id"] in ids(full)


@pytest.mark.api
@pytest.mark.tc("TC-TTC-01-A05")
@pytest.mark.parametrize("query", ["skip=-1", "limit=-1"])
def test_list_negative_params(admin, query):
    response = admin.get(f"{HOL}/?{query}")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid query parameters."


@pytest.mark.api
@pytest.mark.tc("TC-TTC-01-A06")
def test_list_item_shape(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    items = admin.get(f"{HOL}/?academic_year_id={pool['year2']['id']}&limit=1000").json()["items"]
    row = next(i for i in items if i["id"] == holiday["id"])
    assert set(row) == ITEM_KEYS
    assert row["start_date"] == "1001-02-03" and row["end_date"] == "1001-02-05"
    assert row["color"] == "#ff8800"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-01-A07")
@pytest.mark.parametrize("role", READERS)
def test_list_read_matrix(role_clients, role):
    assert role_clients[role].get(f"{HOL}/").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-01-A08")
@pytest.mark.parametrize("role", NO_GRANT)
def test_list_denied_for_student_and_parent(role_clients, role):
    assert role_clients[role].get(f"{HOL}/").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TTC-01-A09")
def test_list_needs_authentication(anon):
    assert anon.get(f"{HOL}/").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TTC-01-A10")
def test_list_tenant_isolation(admin, tenant_b, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    own = tenant_b.get(f"{HOL}/?limit=1000")
    assert own.status_code == 200 and holiday["id"] not in ids(own)
    scoped = tenant_b.get(f"{HOL}/?academic_year_id={pool['year2']['id']}&limit=1000")
    assert scoped.status_code == 200 and scoped.json()["items"] == []
    assert admin.get(f"{HOL}/", headers={"cschema": QA_B_TENANT}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A01")
def test_create_holiday(admin, cleanup, pool):
    body = holiday_body(pool["year2"]["id"], start_date="1001-11-08", end_date="1001-11-10")
    response = admin.post(f"{HOL}/", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{HOL}/{data['id']}")
    assert set(data) == ITEM_KEYS
    for key, value in body.items():
        assert data[key] == value


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A02")
def test_create_without_is_active_is_hidden(admin, cleanup, pool):
    year = pool["year2"]["id"]
    body = holiday_body(year)
    body.pop("is_active")
    response = admin.post(f"{HOL}/", json=body)
    assert response.status_code == 200
    data = response.json()
    cleanup.delete_later(admin, f"{HOL}/{data['id']}")
    assert data["is_active"] is False
    assert data["id"] not in ids(admin.get(f"{HOL}/?academic_year_id={year}&limit=1000"))
    assert data["id"] in ids(admin.get(f"{HOL}/?academic_year_id={year}&limit=1000&active_only=false"))


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A03")
def test_create_single_day_holiday(admin, cleanup, pool):
    make_holiday(admin, cleanup, pool["year2"]["id"], start_date="1001-03-01", end_date="1001-03-01")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A04")
def test_create_end_before_start(admin, pool):
    response = admin.post(
        f"{HOL}/", json=holiday_body(pool["year2"]["id"], start_date="1001-03-05", end_date="1001-03-01")
    )
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A05")
def test_create_name_length(admin, cleanup, pool):
    year = pool["year2"]["id"]
    ok = admin.post(f"{HOL}/", json=holiday_body(year, name="h" + unique("")[:8] + "x" * 41))
    assert ok.status_code == 200, ok.text
    cleanup.delete_later(admin, f"{HOL}/{ok.json()['id']}")
    assert len(ok.json()["name"]) == 50
    too_long = admin.post(f"{HOL}/", json=holiday_body(year, name="h" + unique("") + "x" * 42))
    assert too_long.status_code == 400
    assert too_long.json()["detail"].startswith("Error creating holiday")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A06")
def test_create_description_length(admin, cleanup, pool):
    year = pool["year2"]["id"]
    ok = admin.post(f"{HOL}/", json=holiday_body(year, description="d" * 100))
    assert ok.status_code == 200, ok.text
    cleanup.delete_later(admin, f"{HOL}/{ok.json()['id']}")
    too_long = admin.post(f"{HOL}/", json=holiday_body(year, description="d" * 101))
    assert too_long.status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A07")
def test_create_colour_formats(admin, cleanup, pool):
    year = pool["year2"]["id"]
    ok = admin.post(f"{HOL}/", json=holiday_body(year, color="#ff8800"))
    assert ok.status_code == 200
    cleanup.delete_later(admin, f"{HOL}/{ok.json()['id']}")
    assert admin.post(f"{HOL}/", json=holiday_body(year, color="#ff880011")).status_code == 422
    assert admin.post(f"{HOL}/", json=holiday_body(year, color="red")).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A08")
@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.pop("name"),
        lambda b: b.pop("academic_year_id"),
        lambda b: b.update(start_date="not-a-date"),
    ],
)
def test_create_validation_errors(admin, pool, mutate):
    body = holiday_body(pool["year2"]["id"])
    mutate(body)
    assert admin.post(f"{HOL}/", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A09")
def test_create_unknown_year(admin):
    response = admin.post(f"{HOL}/", json=holiday_body(RANDOM_ID))
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Error creating holiday")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A10")
@pytest.mark.parametrize("role", DENIED)
def test_create_denied(role_clients, pool, role):
    response = role_clients[role].post(f"{HOL}/", json=holiday_body(pool["year2"]["id"]))
    assert response.status_code == 403
    assert response.json()["detail"].startswith("Permission not found in database")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A11")
def test_create_needs_authentication(anon, pool):
    assert anon.post(f"{HOL}/", json=holiday_body(pool["year2"]["id"])).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A12")
def test_create_invalidates_dropdown(admin, cleanup, pool):
    admin.get(f"{HOL}/dropdown")
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    rows = admin.get(f"{HOL}/dropdown").json()
    assert {"id": holiday["id"], "name": holiday["name"]} in rows


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A13")
@pytest.mark.skip(reason="The test API runs with rate limiting disabled, so the 429 cannot be produced")
def test_create_rate_limit():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TTC-02-A14")
def test_create_tenant_isolation(admin, tenant_b, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    assert tenant_b.get(f"{HOL}/{holiday['id']}").status_code == 404
    assert holiday["id"] not in [r["id"] for r in tenant_b.get(f"{HOL}/dropdown").json()]
    twin = tenant_b.post(f"{HOL}/", json=holiday_body(tenant_b.academic_year_id, name=holiday["name"]))
    assert twin.status_code == 200, twin.text
    cleanup.delete_later(tenant_b, f"{HOL}/{twin.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A01")
def test_update_name_only(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    new = unique("ttch")
    response = admin.put(f"{HOL}/{holiday['id']}", json={"name": new})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == new
    for key in ("start_date", "end_date", "color", "is_active", "description"):
        assert data[key] == holiday[key]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A02")
def test_update_dates(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    response = admin.put(f"{HOL}/{holiday['id']}", json={"start_date": "1001-11-12", "end_date": "1001-11-14"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["start_date"] == "1001-11-12" and data["end_date"] == "1001-11-14"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A03")
def test_update_colour_and_description(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    response = admin.put(f"{HOL}/{holiday['id']}", json={"color": "#00aa00", "description": "New"})
    assert response.status_code == 200
    assert response.json()["color"] == "#00aa00" and response.json()["description"] == "New"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A04")
def test_update_end_before_start(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    both = admin.put(f"{HOL}/{holiday['id']}", json={"start_date": "1001-05-10", "end_date": "1001-05-01"})
    assert both.status_code == 422
    against_stored = admin.put(f"{HOL}/{holiday['id']}", json={"end_date": "1001-01-01"})
    assert against_stored.status_code in (400, 422)
    assert admin.get(f"{HOL}/{holiday['id']}").json()["end_date"] == holiday["end_date"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A05")
def test_update_overlong_name(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    response = admin.put(f"{HOL}/{holiday['id']}", json={"name": "n" * 51})
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Error updating holiday")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A06")
def test_update_cannot_change_year(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    response = admin.put(f"{HOL}/{holiday['id']}", json={"academic_year_id": pool["year"]["id"]})
    assert response.status_code == 200
    assert response.json()["academic_year_id"] == pool["year2"]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A07")
def test_update_unknown_holiday(admin):
    response = admin.put(f"{HOL}/{RANDOM_ID}", json={"name": "x"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Holiday not found"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A08")
@pytest.mark.parametrize("role", DENIED)
def test_update_denied(role_clients, admin, cleanup, pool, role):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    assert role_clients[role].put(f"{HOL}/{holiday['id']}", json={"name": unique("ttch")}).status_code == 403
    assert admin.get(f"{HOL}/{holiday['id']}").json()["name"] == holiday["name"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A09")
def test_update_needs_authentication(anon):
    assert anon.put(f"{HOL}/{RANDOM_ID}", json={"name": "x"}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A10")
def test_update_invalidates_dropdown(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    admin.get(f"{HOL}/dropdown")
    new = unique("ttch")
    assert admin.put(f"{HOL}/{holiday['id']}", json={"name": new}).status_code == 200
    assert {"id": holiday["id"], "name": new} in admin.get(f"{HOL}/dropdown").json()


@pytest.mark.api
@pytest.mark.tc("TC-TTC-03-A11")
def test_update_tenant_isolation(admin, tenant_b, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    response = tenant_b.put(f"{HOL}/{holiday['id']}", json={"name": unique("ttch")})
    assert response.status_code == 404
    assert admin.get(f"{HOL}/{holiday['id']}").json()["name"] == holiday["name"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-04-A01")
def test_deactivate_holiday(admin, cleanup, pool):
    year = pool["year2"]["id"]
    holiday = make_holiday(admin, cleanup, year)
    response = admin.delete(f"{HOL}/{holiday['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert holiday["id"] not in ids(admin.get(f"{HOL}/?academic_year_id={year}&limit=1000"))
    assert holiday["id"] in ids(admin.get(f"{HOL}/?academic_year_id={year}&limit=1000&active_only=false"))


@pytest.mark.api
@pytest.mark.tc("TC-TTC-04-A02")
def test_deactivate_twice(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    assert admin.delete(f"{HOL}/{holiday['id']}").status_code == 200
    assert admin.delete(f"{HOL}/{holiday['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-04-A03")
def test_deactivate_unknown(admin):
    assert admin.delete(f"{HOL}/{RANDOM_ID}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TTC-04-A04")
def test_activate_restores_visibility(admin, cleanup, pool):
    year = pool["year2"]["id"]
    holiday = make_holiday(admin, cleanup, year)
    admin.delete(f"{HOL}/{holiday['id']}")
    response = admin.patch(f"{HOL}/{holiday['id']}/activate")
    assert response.status_code == 200 and response.json()["is_active"] is True
    assert holiday["id"] in ids(admin.get(f"{HOL}/?academic_year_id={year}&limit=1000"))
    assert admin.patch(f"{HOL}/{holiday['id']}/activate").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-04-A05")
def test_activate_unknown(admin):
    assert admin.patch(f"{HOL}/{RANDOM_ID}/activate").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TTC-04-A06")
def test_deactivate_and_activate_update_dropdown(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    entry = {"id": holiday["id"], "name": holiday["name"]}
    assert entry in admin.get(f"{HOL}/dropdown").json()
    admin.delete(f"{HOL}/{holiday['id']}")
    assert entry not in admin.get(f"{HOL}/dropdown").json()
    admin.patch(f"{HOL}/{holiday['id']}/activate")
    assert entry in admin.get(f"{HOL}/dropdown").json()


@pytest.mark.api
@pytest.mark.tc("TC-TTC-04-A07")
@pytest.mark.parametrize("role", DENIED)
def test_deactivate_activate_denied(role_clients, admin, cleanup, pool, role):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    client = role_clients[role]
    assert client.delete(f"{HOL}/{holiday['id']}").status_code == 403
    assert client.patch(f"{HOL}/{holiday['id']}/activate").status_code == 403
    assert admin.get(f"{HOL}/{holiday['id']}").json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-TTC-04-A08")
def test_deactivate_activate_need_authentication(anon):
    assert anon.delete(f"{HOL}/{RANDOM_ID}").status_code == 401
    assert anon.patch(f"{HOL}/{RANDOM_ID}/activate").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TTC-04-A09")
def test_deactivate_activate_tenant_isolation(admin, tenant_b, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    assert tenant_b.delete(f"{HOL}/{holiday['id']}").status_code == 404
    assert tenant_b.patch(f"{HOL}/{holiday['id']}/activate").status_code == 404
    assert admin.get(f"{HOL}/{holiday['id']}").json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-TTC-05-A01")
def test_dropdown_active_only(admin, cleanup, pool):
    year = pool["year2"]["id"]
    a = make_holiday(admin, cleanup, year, name=unique("ttcha"))
    b = make_holiday(admin, cleanup, year, name=unique("ttchb"))
    off = make_holiday(admin, cleanup, year, is_active=False)
    rows = admin.get(f"{HOL}/dropdown").json()
    assert all(set(r) == {"id", "name"} for r in rows)
    assert {"id": a["id"], "name": a["name"]} in rows and {"id": b["id"], "name": b["name"]} in rows
    assert off["id"] not in [r["id"] for r in rows]
    names = [r["name"] for r in rows]
    assert names == sorted(names)


@pytest.mark.api
@pytest.mark.tc("TC-TTC-05-A02")
def test_dropdown_active_only_false(admin, cleanup, pool):
    off = make_holiday(admin, cleanup, pool["year2"]["id"], is_active=False)
    rows = admin.get(f"{HOL}/dropdown?active_only=false").json()
    assert {"id": off["id"], "name": off["name"]} in rows


@pytest.mark.api
@pytest.mark.tc("TC-TTC-05-A03")
def test_get_holiday(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    response = admin.get(f"{HOL}/{holiday['id']}")
    assert response.status_code == 200 and response.json() == holiday


@pytest.mark.api
@pytest.mark.tc("TC-TTC-05-A04")
def test_get_unknown_holiday(admin):
    response = admin.get(f"{HOL}/{RANDOM_ID}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Holiday not found"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-05-A05")
def test_get_holiday_bad_uuid(admin):
    assert admin.get(f"{HOL}/not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-05-A06")
@pytest.mark.parametrize("role", READERS)
def test_holiday_read_matrix(role_clients, admin, cleanup, pool, role):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    client = role_clients[role]
    assert client.get(f"{HOL}/dropdown").status_code == 200
    assert client.get(f"{HOL}/{holiday['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-05-A07")
@pytest.mark.parametrize("role", NO_GRANT)
def test_holiday_read_denied(role_clients, admin, cleanup, pool, role):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    client = role_clients[role]
    assert client.get(f"{HOL}/dropdown").status_code == 403
    assert client.get(f"{HOL}/{holiday['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TTC-05-A08")
def test_holiday_reads_need_authentication(anon):
    assert anon.get(f"{HOL}/dropdown").status_code == 401
    assert anon.get(f"{HOL}/{RANDOM_ID}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TTC-05-A09")
def test_holiday_read_tenant_isolation(admin, tenant_b, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    assert holiday["id"] not in [r["id"] for r in tenant_b.get(f"{HOL}/dropdown?active_only=false").json()]
    assert tenant_b.get(f"{HOL}/{holiday['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TTC-05-A10")
def test_rename_visible_in_dropdown_immediately(admin, cleanup, pool):
    holiday = make_holiday(admin, cleanup, pool["year2"]["id"])
    admin.get(f"{HOL}/dropdown")
    new = unique("ttch")
    admin.put(f"{HOL}/{holiday['id']}", json={"name": new})
    assert {"id": holiday["id"], "name": new} in admin.get(f"{HOL}/dropdown").json()


@pytest.mark.api
@pytest.mark.tc("TC-TTC-12-A01")
def test_calendar_read_as_teacher(teacher, admin, cleanup, pool):
    year = pool["year2"]["id"]
    holiday = make_holiday(admin, cleanup, year)
    response = teacher.get(f"{HOL}/?academic_year_id={year}&active_only=true&limit=100")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"items", "total_count", "has_next"}
    assert len(data["items"]) <= 100
    assert holiday["id"] in [i["id"] for i in data["items"]]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-12-A02")
@pytest.mark.skip(
    reason="Needs 101 active holidays in one year; each run would leave 101 undeletable rows. The page-size boundary is covered by TC-TTC-01-A01 and A02"
)
def test_calendar_limit_100_boundary():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TTC-12-A03")
def test_calendar_limit_has_no_upper_bound(admin):
    assert admin.get(f"{HOL}/?limit=1000").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-12-A04")
def test_calendar_read_as_staff(staff, pool):
    year = pool["year2"]["id"]
    assert staff.get(f"{HOL}/?academic_year_id={year}&active_only=true&limit=100").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-12-A05")
@pytest.mark.parametrize("role", NO_GRANT)
def test_calendar_read_denied_for_student_parent(role_clients, pool, role):
    year = pool["year2"]["id"]
    assert role_clients[role].get(f"{HOL}/?academic_year_id={year}&active_only=true&limit=100").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TTC-12-A06")
def test_calendar_needs_authentication(anon, pool):
    year = pool["year2"]["id"]
    assert anon.get(f"{HOL}/?academic_year_id={year}&active_only=true&limit=100").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TTC-12-A07")
def test_calendar_tenant_isolation(tenant_b, pool):
    response = tenant_b.get(f"{HOL}/?academic_year_id={pool['year2']['id']}&active_only=true&limit=100")
    assert response.status_code == 200 and response.json()["items"] == []
