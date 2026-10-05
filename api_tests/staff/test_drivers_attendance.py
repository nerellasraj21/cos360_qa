import datetime
import uuid

import pytest

from api_tests.staff.helpers import expected_status, granted, rand_past_date
from api_tests.support import unique

ATT = "/staff/attendance"


def post_attendance(admin, staff_id, date, status="absent", **extra):
    response = admin.post(ATT, json={"staff_id": staff_id, "date": date, "status": status, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def next_days(count, start=None):
    base = datetime.date.fromisoformat(start or rand_past_date(1960, 1975))
    return [(base + datetime.timedelta(days=i)).isoformat() for i in range(count)]


@pytest.mark.api
@pytest.mark.tc("TC-STF-09-A01")
def test_driver_listed(admin, make_staff, get_or_create_designation):
    designation = get_or_create_designation("Driver")
    staff = make_staff(first_name=unique("stf_drv_"), last_name="Kumar", designation_id=designation["id"])
    response = admin.get("/staff/drivers")
    assert response.status_code == 200
    mine = next(d for d in response.json() if d["user_id"] == staff["user_id"])
    assert mine["full_name"] == f"{staff['first_name']} Kumar"


@pytest.mark.api
@pytest.mark.tc("TC-STF-09-A02")
def test_driver_response_keys(admin, make_staff, get_or_create_designation):
    designation = get_or_create_designation("Driver")
    staff = make_staff(designation_id=designation["id"])
    mine = next(d for d in admin.get("/staff/drivers").json() if d["user_id"] == staff["user_id"])
    assert set(mine) == {"full_name", "user_id"}
    assert mine["full_name"] == staff["first_name"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-09-A03")
def test_driver_designation_match_is_case_insensitive_exact(admin, make_staff, get_or_create_designation):
    lower = make_staff(designation_id=get_or_create_designation("driver")["id"])
    upper = make_staff(designation_id=get_or_create_designation("DRIVER")["id"])
    bus = make_staff(designation_id=get_or_create_designation("Bus Driver")["id"])
    user_ids = [d["user_id"] for d in admin.get("/staff/drivers").json()]
    assert lower["user_id"] in user_ids and upper["user_id"] in user_ids
    assert bus["user_id"] not in user_ids


@pytest.mark.api
@pytest.mark.tc("TC-STF-09-A04")
def test_inactive_driver_is_listed(admin, make_staff, get_or_create_designation):
    designation = get_or_create_designation("Driver")
    staff = make_staff(designation_id=designation["id"], is_active=False)
    assert staff["user_id"] in [d["user_id"] for d in admin.get("/staff/drivers").json()]


@pytest.mark.api
@pytest.mark.tc("TC-STF-09-A05")
def test_driver_list_in_tenant_without_drivers(tenant_b):
    response = tenant_b.get("/staff/drivers")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.api
@pytest.mark.parametrize(
    "role",
    [
        pytest.param("admin", marks=pytest.mark.tc("TC-STF-09-A06")),
        pytest.param("staff", marks=pytest.mark.tc("TC-STF-09-A06")),
        pytest.param("teacher", marks=pytest.mark.tc("TC-STF-09-A06")),
        pytest.param("student", marks=pytest.mark.tc("TC-STF-09-A07")),
        pytest.param("parent", marks=pytest.mark.tc("TC-STF-09-A07")),
    ],
)
def test_drivers_role_matrix(role_clients, logins, role):
    expected = expected_status(logins, role, "transport_trips", "read")
    assert expected == (200 if role in ("admin", "staff", "teacher") else 403)
    assert role_clients[role].get("/staff/drivers").status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-STF-09-A08")
def test_drivers_require_token(anon):
    assert anon.get("/staff/drivers").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STF-09-A09")
def test_driver_tenant_isolation(tenant_b, make_staff, get_or_create_designation):
    designation = get_or_create_designation("Driver")
    staff = make_staff(designation_id=designation["id"])
    assert staff["user_id"] not in [d["user_id"] for d in tenant_b.get("/staff/drivers").json()]


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A01")
def test_create_attendance(admin, make_staff):
    staff = make_staff()
    date = rand_past_date()
    data = post_attendance(admin, staff["id"], date)
    assert data["status"] == "absent" and data["remarks"] is None
    assert data["staff_id"] == staff["id"] and data["date"] == date
    assert set(data) == {"id", "staff_id", "date", "status", "remarks"}


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A02")
@pytest.mark.parametrize("status", ["absent", "late", "half_day", "leave"])
def test_create_attendance_each_status(admin, make_staff, status):
    staff = make_staff()
    assert post_attendance(admin, staff["id"], rand_past_date(), status)["status"] == status


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A03")
@pytest.mark.parametrize(
    "payload",
    [
        {"status": "Present"},
        {"status": "holiday"},
        {"status": "absent", "date": None},
        {"status": "absent", "staff_id": None},
    ],
    ids=["Present", "holiday", "no_date", "no_staff"],
)
def test_create_attendance_validation(admin, make_staff, payload):
    staff = make_staff()
    body = {"staff_id": staff["id"], "date": rand_past_date(), "status": "absent"}
    body.update(payload)
    body = {k: v for k, v in body.items() if v is not None}
    assert admin.post(ATT, json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A04")
def test_duplicate_attendance_for_same_day(admin, make_staff):
    staff = make_staff()
    date = rand_past_date()
    first = post_attendance(admin, staff["id"], date, "absent")
    response = admin.post(ATT, json={"staff_id": staff["id"], "date": date, "status": "late"})
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Error creating staff attendance")
    assert admin.get(f"{ATT}/{first['id']}").json()["status"] == "absent"


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A05")
def test_attendance_for_unknown_staff(admin):
    response = admin.post(ATT, json={"staff_id": str(uuid.uuid4()), "date": rand_past_date(), "status": "absent"})
    assert response.status_code == 500


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A06")
def test_attendance_in_the_future_is_accepted(admin, make_staff):
    staff = make_staff()
    future = (datetime.date.today() + datetime.timedelta(days=366)).isoformat()
    assert post_attendance(admin, staff["id"], future)["date"] == future


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A07")
def test_patch_attendance(admin, make_staff):
    staff = make_staff()
    row = post_attendance(admin, staff["id"], rand_past_date())
    response = admin.patch(f"{ATT}/{row['id']}", json={"status": "late", "remarks": "Bus delay"})
    assert response.status_code == 200
    assert response.json()["status"] == "late" and response.json()["remarks"] == "Bus delay"


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A08")
def test_patch_attendance_status_is_case_sensitive(admin, make_staff):
    staff = make_staff()
    row = post_attendance(admin, staff["id"], rand_past_date())
    assert admin.patch(f"{ATT}/{row['id']}", json={"status": "Late"}).status_code == 422
    assert admin.get(f"{ATT}/{row['id']}").json()["status"] == "absent"


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A09")
def test_patch_and_delete_unknown_attendance(admin):
    missing = str(uuid.uuid4())
    patch = admin.patch(f"{ATT}/{missing}", json={"status": "late"})
    delete = admin.delete(f"{ATT}/{missing}")
    assert patch.status_code == 404 and delete.status_code == 404
    assert patch.json()["detail"] == "Attendance record not found"
    assert delete.json()["detail"] == "Attendance record not found"


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A10")
def test_delete_attendance(admin, make_staff):
    staff = make_staff()
    date = rand_past_date()
    row = post_attendance(admin, staff["id"], date)
    response = admin.delete(f"{ATT}/{row['id']}")
    assert response.status_code == 200
    assert response.json() == {"detail": "Staff attendance deleted successfully"}
    assert admin.get(f"{ATT}/{row['id']}").status_code == 404
    day = admin.get(f"{ATT}/by-date/{date}").json()
    assert staff["id"] not in [r["staff_id"] for r in day]


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A11")
def test_bulk_update_by_date_new_row_before_existing_row(admin, make_staff):
    first, second = make_staff(), make_staff()
    date = rand_past_date()
    existing = post_attendance(admin, second["id"], date, "absent")
    response = admin.patch(
        f"{ATT}/by-date/{date}",
        json=[{"staff_id": first["id"], "status": "absent"}, {"staff_id": second["id"], "status": "late", "remarks": "r"}],
    )
    assert response.status_code == 200
    by_staff = {r["staff_id"]: r for r in response.json()}
    assert by_staff[first["id"]]["status"] == "absent"
    assert by_staff[second["id"]]["status"] == "late"
    assert by_staff[second["id"]]["id"] == existing["id"]
    assert by_staff[second["id"]]["remarks"] == "r"


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A11")
def test_bulk_update_by_date_existing_row_before_new_row(admin, make_staff):
    first, second = make_staff(), make_staff()
    date = rand_past_date()
    existing = post_attendance(admin, second["id"], date, "absent")
    response = admin.patch(
        f"{ATT}/by-date/{date}",
        json=[{"staff_id": second["id"], "status": "late", "remarks": "r"}, {"staff_id": first["id"], "status": "absent"}],
    )
    assert response.status_code == 200
    by_staff = {r["staff_id"]: r for r in response.json()}
    assert by_staff[first["id"]]["status"] == "absent"
    assert by_staff[second["id"]]["status"] == "late"
    assert by_staff[second["id"]]["id"] == existing["id"]
    assert by_staff[second["id"]]["remarks"] == "r"


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A12")
def test_bulk_update_rejections(admin, make_staff):
    staff = make_staff()
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    entry = [{"staff_id": staff["id"], "status": "absent"}]
    future = admin.patch(f"{ATT}/by-date/{tomorrow}", json=entry)
    assert future.status_code == 400 and future.json()["detail"] == "Cannot update attendance for future dates"
    empty = admin.patch(f"{ATT}/by-date/{rand_past_date()}", json=[])
    assert empty.status_code == 400 and empty.json()["detail"] == "No attendance updates provided"
    sick = admin.patch(f"{ATT}/by-date/{rand_past_date()}", json=[{"staff_id": staff["id"], "status": "sick"}])
    assert sick.status_code == 400
    assert sick.json()["detail"] == "Invalid attendance status 'sick'. Must be one of: present, absent, late, half_day, leave"


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A13")
def test_bulk_update_with_unknown_staff_rolls_back(admin, make_staff):
    staff = make_staff()
    date = rand_past_date()
    response = admin.patch(
        f"{ATT}/by-date/{date}",
        json=[{"staff_id": staff["id"], "status": "absent"}, {"staff_id": str(uuid.uuid4()), "status": "absent"}],
    )
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Error updating staff attendance by date")
    assert staff["id"] not in [r["staff_id"] for r in admin.get(f"{ATT}/by-date/{date}").json()]


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A14")
def test_bulk_update_invalid_date_segment(admin, make_staff):
    staff = make_staff()
    response = admin.patch(f"{ATT}/by-date/2026-13-01", json=[{"staff_id": staff["id"], "status": "absent"}])
    assert response.status_code == 422


WRITE_CALLS = [
    ("create", "POST", ATT),
    ("update", "PATCH", ATT + "/{att}"),
    ("delete", "DELETE", ATT + "/{att}"),
    ("update", "PATCH", ATT + "/by-date/{date}"),
]


def write_call(client, method, template, staff_id, att_id, date):
    path = template.format(att=att_id, date=date)
    if method == "POST":
        return client.post(path, json={"staff_id": staff_id, "date": date, "status": "absent"})
    if method == "PATCH" and "by-date" in path:
        return client.patch(path, json=[{"staff_id": staff_id, "status": "absent"}])
    if method == "PATCH":
        return client.patch(path, json={"status": "late"})
    return client.delete(path)


@pytest.mark.api
@pytest.mark.parametrize(
    "role",
    [
        pytest.param("staff", marks=pytest.mark.tc("TC-STF-10-A15")),
        pytest.param("teacher", marks=pytest.mark.tc("TC-STF-10-A17")),
        pytest.param("student", marks=pytest.mark.tc("TC-STF-10-A17")),
        pytest.param("parent", marks=pytest.mark.tc("TC-STF-10-A17")),
    ],
)
def test_attendance_writes_denied_without_grant(role_clients, logins, make_staff, role):
    admin = role_clients["admin"]
    staff = make_staff()
    date = rand_past_date()
    row = post_attendance(admin, staff["id"], date)
    client = role_clients[role]
    for action, method, template in WRITE_CALLS:
        assert not granted(logins, role, "staff_attendance", action)
        assert write_call(client, method, template, staff["id"], row["id"], date).status_code == 403, (role, method)
    assert admin.get(f"{ATT}/{row['id']}").json()["status"] == "absent"


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A16")
def test_attendance_actions_are_independent(role_client, admin, make_staff):
    client = role_client([("staff_attendance", "create")])
    staff = make_staff()
    date = rand_past_date()
    created = client.post(ATT, json={"staff_id": staff["id"], "date": date, "status": "absent"})
    assert created.status_code == 200
    att_id = created.json()["id"]
    assert client.patch(f"{ATT}/{att_id}", json={"status": "late"}).status_code == 403
    assert client.delete(f"{ATT}/{att_id}").status_code == 403
    assert admin.get(f"{ATT}/{att_id}").json()["status"] == "absent"


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A18")
def test_attendance_writes_require_token(anon):
    missing = str(uuid.uuid4())
    assert anon.post(ATT, json={"staff_id": missing, "date": "2000-01-01", "status": "absent"}).status_code == 401
    assert anon.patch(f"{ATT}/{missing}", json={"status": "late"}).status_code == 401
    assert anon.delete(f"{ATT}/{missing}").status_code == 401
    assert anon.patch(f"{ATT}/by-date/2000-01-01", json=[{"staff_id": missing, "status": "absent"}]).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A19")
def test_attendance_write_tenant_isolation(admin, tenant_b, make_staff):
    staff = make_staff()
    row = post_attendance(admin, staff["id"], rand_past_date())
    patch = tenant_b.patch(f"{ATT}/{row['id']}", json={"status": "late"})
    assert patch.status_code == 404 and patch.json()["detail"] == "Attendance record not found"
    assert tenant_b.delete(f"{ATT}/{row['id']}").status_code == 404
    assert admin.get(f"{ATT}/{row['id']}").json()["status"] == "absent"


@pytest.mark.api
@pytest.mark.tc("TC-STF-10-A20")
def test_attendance_foreign_tenant_header(b_header_client, make_staff):
    staff = make_staff()
    response = b_header_client.post(ATT, json={"staff_id": staff["id"], "date": rand_past_date(), "status": "absent"})
    assert response.status_code == 403


@pytest.fixture
def week(admin, make_staff):
    one, two = make_staff(first_name=unique("stf_asha_")), make_staff(first_name=unique("stf_ravi_"))
    d1, d2 = next_days(2)
    rows = {
        "one_d1": post_attendance(admin, one["id"], d1, "absent"),
        "two_d1": post_attendance(admin, two["id"], d1, "late"),
        "one_d2": post_attendance(admin, one["id"], d2, "half_day"),
    }
    return {"one": one, "two": two, "d1": d1, "d2": d2, "rows": rows}


def mine(rows, week):
    return [r for r in rows if r["staff_id"] in (week["one"]["id"], week["two"]["id"])]


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A01")
def test_by_date_lists_only_that_day(admin, week):
    response = admin.get(f"{ATT}/by-date/{week['d1']}")
    assert response.status_code == 200
    got = mine(response.json(), week)
    assert sorted(r["id"] for r in got) == sorted([week["rows"]["one_d1"]["id"], week["rows"]["two_d1"]["id"]])
    assert all(r["date"] == week["d1"] for r in response.json())


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A02")
def test_range_is_inclusive(admin, week):
    response = admin.get(ATT, params={"start_date": week["d1"], "end_date": week["d2"]})
    assert response.status_code == 200
    assert len(mine(response.json(), week)) == 3


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A03")
def test_one_sided_range_is_ignored(admin, week):
    response = admin.get(ATT, params={"start_date": week["d2"]})
    assert response.status_code == 200
    got = mine(response.json(), week)
    assert len(got) == 3
    assert any(r["date"] < week["d2"] for r in got)


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A04")
def test_name_filter(admin, week):
    response = admin.get(
        ATT, params={"start_date": week["d1"], "end_date": week["d2"], "name": week["one"]["first_name"][:12]}
    )
    assert response.status_code == 200
    got = response.json()
    assert {r["staff_id"] for r in got} == {week["one"]["id"]}
    assert len(got) == 2


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A05")
def test_staff_filter_with_start_date(admin, week):
    response = admin.get(f"/staff/{week['one']['id']}/attendance/filter", params={"start_date": week["d2"]})
    assert response.status_code == 200
    assert [r["date"] for r in response.json()] == [week["d2"]]


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A06")
def test_staff_filter_without_dates(admin, week):
    response = admin.get(f"/staff/{week['one']['id']}/attendance/filter")
    assert sorted(r["date"] for r in response.json()) == sorted([week["d1"], week["d2"]])
    only_end = admin.get(f"/staff/{week['one']['id']}/attendance/filter", params={"end_date": week["d1"]})
    assert [r["date"] for r in only_end.json()] == [week["d1"]]


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A07")
def test_staff_filter_unknown_staff(admin):
    response = admin.get(f"/staff/{uuid.uuid4()}/attendance/filter")
    assert response.status_code == 200 and response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A08")
def test_single_attendance_record(admin, week):
    row = week["rows"]["one_d1"]
    response = admin.get(f"{ATT}/{row['id']}")
    assert response.status_code == 200 and response.json() == row
    missing = admin.get(f"{ATT}/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Staff attendance record not found"


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A09")
def test_attendance_lookup_validation(admin, week):
    assert admin.get(f"{ATT}/by-date/2026-13-45").status_code == 422
    assert admin.get(f"{ATT}/by-date/abc").status_code == 422
    assert admin.get(f"/staff/{week['one']['id']}/attendance/filter", params={"start_date": "x"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A10")
def test_day_without_exceptions(admin):
    response = admin.get(f"{ATT}/by-date/{rand_past_date(1900, 1930)}")
    assert response.status_code == 200 and response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A11")
def test_attendance_response_fields(admin, week):
    row = next(r for r in admin.get(f"{ATT}/by-date/{week['d1']}").json() if r["id"] == week["rows"]["one_d1"]["id"])
    assert set(row) == {"id", "staff_id", "date", "status", "remarks"}
    assert datetime.date.fromisoformat(row["date"]).isoformat() == week["d1"]


def read_calls(week):
    return [
        ("list", f"{ATT}"),
        ("list", f"{ATT}/by-date/{week['d1']}"),
        ("list", f"/staff/{week['one']['id']}/attendance/filter"),
        ("read", f"{ATT}/{week['rows']['one_d1']['id']}"),
    ]


@pytest.mark.api
@pytest.mark.parametrize(
    "role",
    [
        pytest.param("admin", marks=pytest.mark.tc("TC-STF-11-A12")),
        pytest.param("staff", marks=pytest.mark.tc("TC-STF-11-A13")),
        pytest.param("teacher", marks=pytest.mark.tc("TC-STF-11-A13")),
        pytest.param("student", marks=pytest.mark.tc("TC-STF-11-A13")),
        pytest.param("parent", marks=pytest.mark.tc("TC-STF-11-A13")),
    ],
)
def test_attendance_reads_role_matrix(role_clients, logins, week, role):
    for action, path in read_calls(week):
        assert role_clients[role].get(path).status_code == expected_status(logins, role, "staff_attendance", action), path


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A14")
def test_read_and_list_are_independent(role_client, week):
    listing = role_client([("staff_attendance", "list")])
    for action, path in read_calls(week):
        expected = 200 if action == "list" else 403
        assert listing.get(path).status_code == expected, path
    reading = role_client([("staff_attendance", "read")])
    for action, path in read_calls(week):
        expected = 200 if action == "read" else 403
        assert reading.get(path).status_code == expected, path


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A15")
def test_attendance_reads_require_token(anon, week):
    for _, path in read_calls(week):
        assert anon.get(path).status_code == 401, path


@pytest.mark.api
@pytest.mark.tc("TC-STF-11-A16")
def test_attendance_reads_tenant_isolation(tenant_b, b_header_client, week):
    ids = {r["id"] for r in week["rows"].values()}
    assert not ids & {r["id"] for r in tenant_b.get(ATT).json()}
    assert not ids & {r["id"] for r in tenant_b.get(f"{ATT}/by-date/{week['d1']}").json()}
    assert tenant_b.get(f"/staff/{week['one']['id']}/attendance/filter").json() == []
    assert tenant_b.get(f"{ATT}/{week['rows']['one_d1']['id']}").status_code == 404
    assert b_header_client.get(ATT).status_code == 403
