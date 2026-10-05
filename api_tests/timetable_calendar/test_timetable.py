import pytest

from api_tests.support import QA_B_TENANT
from api_tests.timetable_calendar.helpers import (
    DAYS,
    DENIED,
    RANDOM_ID,
    TT,
    save,
    sorted_rows,
    special_row,
    subject_row,
    tt_class,
)

NO_ROLE_GRANT = ["staff", "teacher", "student", "parent"]


def two_rows_and_lunch(pool):
    return [
        subject_row(pool, "09:00", "09:45", indexes=(0, 1, 2)),
        subject_row(pool, "09:45", "10:30", indexes=(3, 4)),
        special_row("12:00", "12:45"),
    ]


def sid(cls, index=0):
    return cls["sections"][index]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-06-A01")
def test_get_timetable_after_save(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    assert save(admin, sid(cls), two_rows_and_lunch(pool)).status_code == 200
    response = admin.get(f"{TT}/frontend/{sid(cls)}")
    assert response.status_code == 200
    data = response.json()
    assert data["section_id"] == sid(cls)
    assert data["section_name"] == cls["sections"][0]["name"]
    assert data["class_name"] == cls["name"]
    rows = sorted_rows(response)
    assert [r["time"] for r in rows] == [
        {"from": "09:00", "to": "09:45"},
        {"from": "09:45", "to": "10:30"},
        {"from": "12:00", "to": "12:45"},
    ]
    assert rows[0]["type"] == "subject" and rows[2]["type"] == "special"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-06-A02")
def test_get_timetable_missing(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    response = admin.get(f"{TT}/frontend/{sid(cls)}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Timetable not found for section"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-06-A03")
def test_get_timetable_unknown_and_malformed_section(admin):
    unknown = admin.get(f"{TT}/frontend/{RANDOM_ID}")
    assert unknown.status_code == 404
    assert admin.get(f"{TT}/frontend/not-a-uuid").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-06-A04")
def test_get_timetable_with_no_rows(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    assert save(admin, sid(cls), []).status_code == 200
    response = admin.get(f"{TT}/frontend/{sid(cls)}")
    assert response.status_code == 200
    assert response.json()["timetable_data"] == []


@pytest.mark.api
@pytest.mark.tc("TC-TTC-06-A05")
def test_special_row_shape(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    assert save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")]).status_code == 200
    assert save(admin, sid(cls), [special_row("12:00", "12:45", "SNACKS")], "put").status_code == 200
    row = sorted_rows(admin.get(f"{TT}/frontend/{sid(cls)}"))[0]
    assert row["type"] == "special" and row["label"] == "SNACKS"
    assert not row.get("subjects")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-06-A06")
def test_same_time_range_rows_merge(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    assert save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")]).status_code == 200
    rows = [
        {"time": {"from": "10:00", "to": "10:45"}, "type": "subject", "subjects": {"Monday": pool["subjects"][0]["id"]}},
        {"time": {"from": "10:00", "to": "10:45"}, "type": "subject", "subjects": {"Tuesday": pool["subjects"][1]["id"]}},
    ]
    assert save(admin, sid(cls), rows, "put").status_code == 200
    got = sorted_rows(admin.get(f"{TT}/frontend/{sid(cls)}"))
    assert len(got) == 1
    assert got[0]["subjects"] == {"Monday": pool["subjects"][0]["id"], "Tuesday": pool["subjects"][1]["id"]}


@pytest.mark.api
@pytest.mark.tc("TC-TTC-06-A07")
def test_admin_reads_timetable(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    assert admin.get(f"{TT}/frontend/{sid(cls)}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-06-A08")
@pytest.mark.parametrize("role", NO_ROLE_GRANT)
def test_timetable_read_denied(role_clients, admin, cleanup, pool, role):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    response = role_clients[role].get(f"{TT}/frontend/{sid(cls)}")
    assert response.status_code == 403
    assert response.json()["detail"].startswith("Permission not found in database")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-06-A09")
def test_timetable_read_needs_authentication(anon):
    assert anon.get(f"{TT}/frontend/{RANDOM_ID}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TTC-06-A10")
def test_timetable_read_tenant_isolation(admin, tenant_b, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    assert tenant_b.get(f"{TT}/frontend/{sid(cls)}").status_code == 404
    assert admin.get(f"{TT}/frontend/{sid(cls)}", headers={"cschema": QA_B_TENANT}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A01")
def test_create_timetable_counts(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    response = save(admin, sid(cls), two_rows_and_lunch(pool))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["message"] == "Timetable created successfully"
    assert data["created_slots"] == 15 and data["created_slot_times"] == 3
    assert data["timetable_id"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A02")
def test_create_then_read_rows(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), two_rows_and_lunch(pool))
    rows = sorted_rows(admin.get(f"{TT}/frontend/{sid(cls)}"))
    assert len(rows) == 3
    assert sorted(rows[0]["subjects"]) == sorted(DAYS)
    assert sorted(rows[1]["subjects"]) == sorted(DAYS)
    assert rows[2]["type"] == "special" and rows[2]["label"] == "LUNCH"
    assert rows[0]["subjects"]["Monday"] == pool["subjects"][0]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A03")
def test_create_drops_saturday(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    row = subject_row(pool, "09:00", "09:45")
    row["subjects"]["Saturday"] = pool["subjects"][5]["id"]
    response = save(admin, sid(cls), [row])
    assert response.status_code == 200
    assert response.json()["created_slots"] == 5
    got = sorted_rows(admin.get(f"{TT}/frontend/{sid(cls)}"))
    assert "Saturday" not in got[0]["subjects"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A04")
def test_create_with_only_saturday(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    row = {"time": {"from": "09:00", "to": "09:45"}, "type": "subject", "subjects": {"Saturday": pool["subjects"][0]["id"]}}
    response = save(admin, sid(cls), [row])
    assert response.status_code == 200
    data = response.json()
    assert data["created_slot_times"] == 1 and data["created_slots"] == 0
    assert admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"] == []


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A05")
def test_create_twice_fails(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    assert save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")]).status_code == 200
    again = save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    assert again.status_code == 409
    assert again.json()["detail"] == "A timetable already exists for this section"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A06")
def test_create_with_unknown_references(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    unknown_section = save(admin, RANDOM_ID, [subject_row(pool, "09:00", "09:45")])
    assert unknown_section.status_code == 404
    row = {"time": {"from": "09:00", "to": "09:45"}, "type": "subject", "subjects": {"Monday": RANDOM_ID}}
    unknown_subject = save(admin, sid(cls), [row])
    assert unknown_subject.status_code == 400
    assert admin.get(f"{TT}/frontend/{sid(cls)}").status_code == 404


BAD_ROWS = [
    {"time": {"from": "09:00", "to": "09:45"}, "type": "break", "label": "X"},
    {"time": {"from": "09:00", "to": "09:45"}, "type": "subject"},
    {"time": {"from": "09:00", "to": "09:45"}, "type": "subject", "subjects": {"Monday": "@S"}, "label": "X"},
    {"time": {"from": "09:00", "to": "09:45"}, "type": "special"},
    {"time": {"from": "09:00", "to": "09:45"}, "type": "special", "label": "X", "subjects": {"Monday": "@S"}},
]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A07")
@pytest.mark.parametrize("index", range(len(BAD_ROWS)))
def test_create_rejects_invalid_rows(admin, cleanup, pool, index):
    cls = tt_class(admin, cleanup, pool)
    row = dict(BAD_ROWS[index])
    if "subjects" in row:
        row["subjects"] = {"Monday": pool["subjects"][0]["id"]}
    assert save(admin, sid(cls), [row]).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A08")
def test_create_rejects_free_text_subject(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    row = {"time": {"from": "09:00", "to": "09:45"}, "type": "subject", "subjects": {"Saturday": "Holiday"}}
    assert save(admin, sid(cls), [row]).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A09")
@pytest.mark.parametrize("bad", ["9am", "25:00", "09:00:00"])
def test_create_rejects_bad_times(admin, cleanup, pool, bad):
    cls = tt_class(admin, cleanup, pool)
    response = save(admin, sid(cls), [subject_row(pool, bad, "10:00")])
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid time, use HH:MM"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A09")
def test_create_accepts_single_digit_hour(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    assert save(admin, sid(cls), [subject_row(pool, "9:00", "10:00")]).status_code == 200
    assert sorted_rows(admin.get(f"{TT}/frontend/{sid(cls)}"))[0]["time"]["from"] == "09:00"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A10")
def test_create_does_not_check_time_order_or_overlap(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    rows = [
        subject_row(pool, "10:00", "09:00"),
        subject_row(pool, "09:00", "10:00"),
        subject_row(pool, "09:30", "10:30"),
    ]
    assert save(admin, sid(cls), rows).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A11")
def test_create_with_empty_data(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    response = save(admin, sid(cls), [])
    assert response.status_code == 200
    assert response.json()["created_slots"] == 0 and response.json()["created_slot_times"] == 0


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A12")
def test_create_with_unmapped_subject(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    assert save(admin, sid(cls), [subject_row(pool, "09:00", "09:45", indexes=(5,))]).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A13")
def test_create_missing_fields(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    no_section = admin.post(f"{TT}/frontend", json={"timetable_data": [subject_row(pool, "09:00", "09:45")]})
    assert no_section.status_code == 422
    row = subject_row(pool, "09:00", "09:45")
    row["time"].pop("to")
    assert save(admin, sid(cls), [row]).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A14")
def test_replace_timetable(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), two_rows_and_lunch(pool))
    response = save(admin, sid(cls), [subject_row(pool, "08:00", "08:45")], "put")
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Timetable updated successfully"
    rows = admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"]
    assert len(rows) == 1 and rows[0]["time"] == {"from": "08:00", "to": "08:45"}


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A15")
def test_replace_keeps_saturday(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    row = subject_row(pool, "09:00", "09:45")
    row["subjects"]["Saturday"] = pool["subjects"][5]["id"]
    assert save(admin, sid(cls), [row], "put").status_code == 200
    got = admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"][0]
    assert got["subjects"]["Saturday"] == pool["subjects"][5]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A16")
def test_replace_special_row_counts_seven(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    response = save(admin, sid(cls), [special_row("12:00", "12:45")], "put")
    assert response.status_code == 200
    assert response.json()["created_slots"] == 7
    row = admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"][0]
    assert row["type"] == "special"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A17")
def test_replace_accepts_non_day_key(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    row = {"time": {"from": "09:00", "to": "09:45"}, "type": "subject", "subjects": {"Funday": pool["subjects"][0]["id"]}}
    assert save(admin, sid(cls), [row], "put").status_code == 200
    got = admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"][0]
    assert got["subjects"] == {"Funday": pool["subjects"][0]["id"]}


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A18")
def test_replace_merges_same_range(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    rows = [
        {"time": {"from": "09:00", "to": "09:45"}, "type": "subject", "subjects": {"Monday": pool["subjects"][0]["id"]}},
        {"time": {"from": "09:00", "to": "09:45"}, "type": "subject", "subjects": {"Tuesday": pool["subjects"][1]["id"]}},
    ]
    response = save(admin, sid(cls), rows, "put")
    assert response.json()["created_slot_times"] == 1
    got = admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"]
    assert len(got) == 1 and set(got[0]["subjects"]) == {"Monday", "Tuesday"}


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A19")
def test_replace_special_and_subject_same_range(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    rows = [special_row("09:00", "09:45", "ASSEMBLY"), subject_row(pool, "09:00", "09:45")]
    assert save(admin, sid(cls), rows, "put").status_code == 200
    got = admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"]
    assert len(got) == 1 and got[0]["type"] == "subject"
    assert not got[0].get("label")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A20")
def test_replace_without_timetable(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    response = save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")], "put")
    assert response.status_code == 404
    assert response.json()["detail"] == "Timetable not found for section"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A21")
def test_replace_uses_path_section(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    a, b = sid(cls, 0), sid(cls, 1)
    save(admin, a, [subject_row(pool, "09:00", "09:45")])
    save(admin, b, [subject_row(pool, "10:00", "10:45")])
    response = admin.put(
        f"{TT}/frontend/{a}", json={"section_id": b, "timetable_data": [subject_row(pool, "08:00", "08:45")]}
    )
    assert response.status_code == 200
    assert admin.get(f"{TT}/frontend/{a}").json()["timetable_data"][0]["time"]["from"] == "08:00"
    assert admin.get(f"{TT}/frontend/{b}").json()["timetable_data"][0]["time"]["from"] == "10:00"


def slot_ids(admin, section_id):
    data = admin.get(f"{TT}/section/{section_id}").json()["slot_time_data"]
    return {slot["id"] for group in data for slot in group["slots"]}


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A22")
def test_replace_changes_slot_ids(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    before = slot_ids(admin, sid(cls))
    assert len(before) == 5
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")], "put")
    after = slot_ids(admin, sid(cls))
    assert len(after) == 5 and not before & after


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A23")
def test_replace_round_trip(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    rows = [
        subject_row(pool, "09:00", "09:45", indexes=(0, 1)),
        subject_row(pool, "09:45", "10:30", indexes=(2, 3)),
        subject_row(pool, "10:45", "11:30", indexes=(4, 0)),
    ]
    assert save(admin, sid(cls), rows, "put").status_code == 200
    got = sorted_rows(admin.get(f"{TT}/frontend/{sid(cls)}"))
    assert [r["time"]["from"] for r in got] == ["09:00", "09:45", "10:45"]
    for sent, back in zip(rows, got):
        assert back["subjects"] == sent["subjects"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A24")
@pytest.mark.parametrize("role", NO_ROLE_GRANT)
def test_timetable_write_denied(role_clients, admin, cleanup, pool, role):
    cls = tt_class(admin, cleanup, pool)
    client = role_clients[role]
    body = {"section_id": sid(cls), "timetable_data": [subject_row(pool, "09:00", "09:45")]}
    assert client.post(f"{TT}/frontend", json=body).status_code == 403
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    assert client.put(f"{TT}/frontend/{sid(cls)}", json=body).status_code == 403
    assert len(admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"]) == 1


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A25")
def test_timetable_write_needs_authentication(anon, pool):
    body = {"section_id": RANDOM_ID, "timetable_data": []}
    assert anon.post(f"{TT}/frontend", json=body).status_code == 401
    assert anon.put(f"{TT}/frontend/{RANDOM_ID}", json=body).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TTC-07-A26")
def test_timetable_write_tenant_isolation(admin, tenant_b, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    row = subject_row(pool, "09:00", "09:45")
    created = tenant_b.post(f"{TT}/frontend", json={"section_id": sid(cls), "timetable_data": [row]})
    assert created.status_code == 404
    save(admin, sid(cls), [row])
    replaced = tenant_b.put(f"{TT}/frontend/{sid(cls)}", json={"section_id": sid(cls), "timetable_data": []})
    assert replaced.status_code == 404
    assert len(admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"]) == 1


@pytest.mark.api
@pytest.mark.tc("TC-TTC-08-A01")
def test_custom_special_label_round_trip(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    assert save(admin, sid(cls), [special_row("08:00", "08:30", "MORNING_PRAYER")], "put").status_code == 200
    row = admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"][0]
    assert row["label"] == "MORNING_PRAYER"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-08-A02")
def test_saturday_dropped_on_post_kept_on_put(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    row = subject_row(pool, "09:00", "09:45")
    row["subjects"]["Saturday"] = pool["subjects"][5]["id"]
    save(admin, sid(cls), [row])
    after_post = admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"][0]["subjects"]
    assert "Saturday" not in after_post
    save(admin, sid(cls), [row], "put")
    after_put = admin.get(f"{TT}/frontend/{sid(cls)}").json()["timetable_data"][0]["subjects"]
    assert after_put["Saturday"] == pool["subjects"][5]["id"]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-08-A03")
def test_saturday_free_text_rejected_on_put(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    row = subject_row(pool, "09:00", "09:45")
    row["subjects"]["Saturday"] = "Sports"
    assert save(admin, sid(cls), [row], "put").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-08-A04")
def test_put_with_unmapped_subject(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    assert save(admin, sid(cls), [subject_row(pool, "09:00", "09:45", indexes=(5,))], "put").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-08-A05")
def test_by_class_mappings_feed_the_subject_picker(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    base = "/masters/class-subject-mappings"
    created = []
    bulk = admin.post(
        f"{base}/bulk",
        json={
            "class_id": cls["id"],
            "section_id": None,
            "academic_year_id": pool["year"]["id"],
            "subjects": [{"subject_id": pool["subjects"][0]["id"]}],
        },
    )
    assert bulk.status_code == 201, bulk.text
    created += [m["id"] for m in bulk.json()["mappings"]]
    for mapping_id in created:
        cleanup.delete_later(admin, f"{base}/{mapping_id}")
    single = admin.post(
        f"{base}/",
        json={
            "class_id": cls["id"],
            "section_id": cls["sections"][0]["id"],
            "subject_id": pool["subjects"][1]["id"],
            "academic_year_id": pool["year"]["id"],
        },
    )
    assert single.status_code == 201
    cleanup.delete_later(admin, f"{base}/{single.json()['id']}")
    rows = admin.get(f"{base}/by-class/{cls['id']}")
    assert rows.status_code == 200
    subjects = [r["subject_id"] for r in rows.json()]
    assert subjects.count(pool["subjects"][0]["id"]) == 2
    assert subjects.count(pool["subjects"][1]["id"]) == 1


@pytest.mark.api
@pytest.mark.tc("TC-TTC-09-A01")
def test_delete_timetable(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    response = admin.delete(f"{TT}/frontend/{sid(cls)}")
    assert response.status_code == 200
    assert response.json() == {"message": f"Timetable deleted successfully for section {sid(cls)}"}


@pytest.mark.api
@pytest.mark.tc("TC-TTC-09-A02")
def test_read_after_delete(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    admin.delete(f"{TT}/frontend/{sid(cls)}")
    assert admin.get(f"{TT}/frontend/{sid(cls)}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TTC-09-A03")
def test_delete_twice_and_without_timetable(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    assert admin.delete(f"{TT}/frontend/{sid(cls)}").status_code == 200
    again = admin.delete(f"{TT}/frontend/{sid(cls)}")
    assert again.status_code == 404
    assert again.json()["detail"] == "Timetable not found for section"
    never = admin.delete(f"{TT}/frontend/{sid(cls, 1)}")
    assert never.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TTC-09-A04")
def test_create_again_after_delete(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    admin.delete(f"{TT}/frontend/{sid(cls)}")
    assert save(admin, sid(cls), [subject_row(pool, "10:00", "10:45")]).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-09-A05")
def test_class_delete_blocked_until_timetable_removed(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool, sections=("A",))
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    blocked = admin.delete(f"/masters/class_sections/{cls['id']}")
    assert blocked.status_code == 400
    assert "section-related record(s)" in blocked.json()["detail"]
    assert admin.delete(f"{TT}/frontend/{sid(cls)}").status_code == 200
    assert admin.delete(f"/masters/class_sections/{cls['id']}").status_code == 204


@pytest.mark.api
@pytest.mark.tc("TC-TTC-09-A06")
@pytest.mark.parametrize("role", NO_ROLE_GRANT)
def test_delete_timetable_denied(role_clients, admin, cleanup, pool, role):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    assert role_clients[role].delete(f"{TT}/frontend/{sid(cls)}").status_code == 403
    assert admin.get(f"{TT}/frontend/{sid(cls)}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-09-A07")
def test_delete_timetable_needs_authentication(anon):
    assert anon.delete(f"{TT}/frontend/{RANDOM_ID}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TTC-09-A08")
def test_delete_timetable_tenant_isolation(admin, tenant_b, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    assert tenant_b.delete(f"{TT}/frontend/{sid(cls)}").status_code == 404
    assert admin.get(f"{TT}/frontend/{sid(cls)}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TTC-11-A01")
@pytest.mark.parametrize("role", ["student", "parent"])
def test_student_parent_cannot_read_timetable_by_default(role_clients, admin, cleanup, pool, role):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    response = role_clients[role].get(f"{TT}/frontend/{sid(cls)}")
    assert response.status_code == 403
    assert response.json()["detail"].startswith("Permission not found in database")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-11-A02")
def test_parent_marker_for_default_denial(parent, admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    assert parent.get(f"{TT}/frontend/{sid(cls)}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TTC-11-A03")
@pytest.mark.skip(reason="Needs a fixture that grants timetable_management:read to Student and Parent; role grants are a global singleton the QA rules forbid changing")
def test_student_parent_read_with_grant():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TTC-11-A04")
def test_student_lists_subjects_used_by_timetable(student, admin, pool):
    response = student.get(f"/masters/subjects/?active_only=true&academic_year_id={pool['year']['id']}")
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    assert pool["subjects"][0]["id"] in [r["id"] for r in rows]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-11-A05")
@pytest.mark.skip(reason="The QA Student login has no linked student record, so my-admission has no section to return; creating a login-capable student belongs to the Students suite")
def test_student_my_admission():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-TTC-11-A06")
@pytest.mark.skip(reason="Depends on the timetable_management:read grant fixture for Student, which the QA rules forbid")
def test_student_reads_other_section_with_grant():
    pass


def create_legacy_source(admin, cleanup, pool):
    source = tt_class(admin, cleanup, pool, sections=("A",))
    assert save(admin, sid(source), [subject_row(pool, "09:00", "09:45"), subject_row(pool, "09:45", "10:30")]).status_code == 200
    groups = admin.get(f"{TT}/section/{sid(source)}").json()["slot_time_data"]
    return source, groups


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A01")
def test_grouped_read_shape(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45"), special_row("12:00", "12:45")])
    response = admin.get(f"{TT}/section/{sid(cls)}")
    assert response.status_code == 200
    data = response.json()
    assert data["section_id"] == sid(cls) and data["class_name"] == cls["name"]
    groups = data["slot_time_data"]
    assert len(groups) == 2
    for group in groups:
        assert "slot_time_id" in group
        for slot in group["slots"]:
            assert {"id", "day", "is_break", "break_label", "subject_options"} <= set(slot)
    subject_slots = [s for g in groups for s in g["slots"] if not s["is_break"]]
    assert len(subject_slots) == 5
    names = {o["subject_name"] for s in subject_slots for o in s["subject_options"]}
    assert names <= {s["name"] for s in pool["subjects"]} and names
    breaks = [s for g in groups for s in g["slots"] if s["is_break"]]
    assert breaks and all(s["break_label"] == "LUNCH" for s in breaks)


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A02")
def test_grouped_read_missing(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    response = admin.get(f"{TT}/section/{sid(cls)}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Timetable not found for section"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A03")
def test_legacy_bulk_create(admin, cleanup, pool):
    source, groups = create_legacy_source(admin, cleanup, pool)
    target = tt_class(admin, cleanup, pool, sections=("A",))
    body = {
        "section_id": sid(target),
        "slot_time_data": [
            {
                "slot_time_id": groups[0]["slot_time_id"],
                "slots": [
                    {"day": "Monday", "is_break": False, "subject_options": [{"subject_id": pool["subjects"][0]["id"]}]},
                    {"day": "Tuesday", "is_break": True, "break_label": "LUNCH"},
                ],
            }
        ],
    }
    response = admin.post(f"{TT}/bulk", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] and data["section_id"] == sid(target)
    read = admin.get(f"{TT}/section/{sid(target)}")
    assert read.status_code == 200
    slots = read.json()["slot_time_data"][0]["slots"]
    assert sorted(s["day"] for s in slots) == ["Monday", "Tuesday"]
    cleanup.delete_later(admin, f"{TT}/frontend/{sid(target)}")


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A04")
def test_legacy_bulk_create_twice(admin, cleanup, pool):
    source, groups = create_legacy_source(admin, cleanup, pool)
    target = tt_class(admin, cleanup, pool, sections=("A",))
    body = {
        "section_id": sid(target),
        "slot_time_data": [
            {
                "slot_time_id": groups[0]["slot_time_id"],
                "slots": [
                    {"day": "Monday", "is_break": False, "subject_options": [{"subject_id": pool["subjects"][0]["id"]}]}
                ],
            }
        ],
    }
    assert admin.post(f"{TT}/bulk", json=body).status_code == 200
    assert admin.post(f"{TT}/bulk", json=body).status_code == 400


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A05")
@pytest.mark.parametrize(
    "slot",
    [
        {"day": "Monday", "is_break": True},
        {"day": "Monday", "is_break": False},
    ],
)
def test_legacy_bulk_create_validation(admin, cleanup, pool, slot):
    cls = tt_class(admin, cleanup, pool, sections=("A",))
    body = {"section_id": sid(cls), "slot_time_data": [{"slot_time_id": RANDOM_ID, "slots": [slot]}]}
    assert admin.post(f"{TT}/bulk", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A06")
def test_legacy_bulk_create_unknown_slot_time(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool, sections=("A",))
    body = {
        "section_id": sid(cls),
        "slot_time_data": [
            {
                "slot_time_id": RANDOM_ID,
                "slots": [
                    {"day": "Monday", "is_break": False, "subject_options": [{"subject_id": pool["subjects"][0]["id"]}]}
                ],
            }
        ],
    }
    assert admin.post(f"{TT}/bulk", json=body).status_code == 400
    assert admin.get(f"{TT}/section/{sid(cls)}").status_code == 404


def first_subject_slot(admin, section_id):
    groups = admin.get(f"{TT}/section/{section_id}").json()["slot_time_data"]
    return next(s for g in groups for s in g["slots"] if not s["is_break"])


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A07")
def test_legacy_patch_replaces_subject_option(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    slot = first_subject_slot(admin, sid(cls))
    other = next(s for s in pool["subjects"] if s["id"] != slot["subject_options"][0]["subject_id"])
    response = admin.patch(
        f"{TT}/timetable/slots/bulk", json={"slots": [{"id": slot["id"], "subject_options": [{"subject_id": other["id"]}]}]}
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1 and rows[0]["id"] == slot["id"]
    assert [o["subject_id"] for o in rows[0]["subject_options"]] == [other["id"]]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A08")
def test_legacy_patch_sets_break_flag(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    slot = first_subject_slot(admin, sid(cls))
    response = admin.patch(
        f"{TT}/timetable/slots/bulk", json={"slots": [{"id": slot["id"], "is_break": True, "break_label": "LUNCH"}]}
    )
    assert response.status_code == 200, response.text
    row = response.json()[0]
    assert row["is_break"] is True and row["break_label"] == "LUNCH"
    assert [o["subject_id"] for o in row["subject_options"]] == [o["subject_id"] for o in slot["subject_options"]]


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A09")
def test_legacy_patch_requires_options_or_break(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    slot = first_subject_slot(admin, sid(cls))
    assert admin.patch(f"{TT}/timetable/slots/bulk", json={"slots": [{"id": slot["id"], "day": "Monday"}]}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A10")
def test_legacy_patch_break_with_options(admin, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    slot = first_subject_slot(admin, sid(cls))
    body = {
        "slots": [
            {
                "id": slot["id"],
                "is_break": True,
                "break_label": "LUNCH",
                "subject_options": [{"subject_id": pool["subjects"][0]["id"]}],
            }
        ]
    }
    assert admin.patch(f"{TT}/timetable/slots/bulk", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A11")
def test_legacy_patch_unknown_slot(admin, pool):
    body = {"slots": [{"id": RANDOM_ID, "subject_options": [{"subject_id": pool["subjects"][0]["id"]}]}]}
    response = admin.patch(f"{TT}/timetable/slots/bulk", json=body)
    assert response.status_code == 404
    assert response.json()["detail"] == f"Slot with id {RANDOM_ID} not found"


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A12")
def test_legacy_patch_single_segment_path_missing(admin, pool):
    body = {"slots": [{"id": RANDOM_ID, "subject_options": [{"subject_id": pool["subjects"][0]["id"]}]}]}
    assert admin.patch(f"{TT}/slots/bulk", json=body).status_code in (404, 405)


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A13")
def test_legacy_test_endpoint_removed(anon, admin):
    assert anon.get(f"{TT}/test").status_code in (401, 404, 405, 422)
    assert admin.get(f"{TT}/test").status_code in (404, 405, 422)


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A14")
@pytest.mark.parametrize("role", NO_ROLE_GRANT)
def test_legacy_endpoints_denied(role_clients, admin, cleanup, pool, role):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    client = role_clients[role]
    body = {"section_id": sid(cls), "slot_time_data": []}
    assert client.post(f"{TT}/bulk", json=body).status_code == 403
    assert client.get(f"{TT}/section/{sid(cls)}").status_code == 403
    patch = {"slots": [{"id": RANDOM_ID, "subject_options": [{"subject_id": pool["subjects"][0]["id"]}]}]}
    assert client.patch(f"{TT}/timetable/slots/bulk", json=patch).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A15")
def test_legacy_endpoints_need_authentication(anon, pool):
    assert anon.post(f"{TT}/bulk", json={"section_id": RANDOM_ID, "slot_time_data": []}).status_code == 401
    assert anon.get(f"{TT}/section/{RANDOM_ID}").status_code == 401
    patch = {"slots": [{"id": RANDOM_ID, "subject_options": [{"subject_id": pool["subjects"][0]["id"]}]}]}
    assert anon.patch(f"{TT}/timetable/slots/bulk", json=patch).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TTC-13-A16")
def test_legacy_tenant_isolation(admin, tenant_b, cleanup, pool):
    cls = tt_class(admin, cleanup, pool)
    save(admin, sid(cls), [subject_row(pool, "09:00", "09:45")])
    slot = first_subject_slot(admin, sid(cls))
    assert tenant_b.get(f"{TT}/section/{sid(cls)}").status_code == 404
    patch = {"slots": [{"id": slot["id"], "subject_options": [{"subject_id": pool["subjects"][1]["id"]}]}]}
    assert tenant_b.patch(f"{TT}/timetable/slots/bulk", json=patch).status_code == 404
    assert first_subject_slot(admin, sid(cls))["subject_options"] == slot["subject_options"]
