import itertools

from api_tests.masters.helpers import DENIED, RANDOM_ID, ROLES, make_class, make_mapping  # noqa: F401
from api_tests.support import unique

HOL = "/masters/holidays"
TT = "/students/timetable"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

_counter = itertools.count(1)


def holiday_body(year_id, **over):
    body = {
        "name": unique("ttch"),
        "description": "Festival",
        "start_date": "1001-02-03",
        "end_date": "1001-02-05",
        "is_active": True,
        "academic_year_id": year_id,
        "color": "#ff8800",
    }
    body.update(over)
    return body


def make_holiday(admin, cleanup, year_id, **over):
    response = admin.post(f"{HOL}/", json=holiday_body(year_id, **over))
    assert response.status_code == 200, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{HOL}/{data['id']}")
    return data


def tt_class(admin, cleanup, pool, sections=("A", "B")):
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=sections)
    for section in cls["sections"]:
        cleanup.delete_later(admin, f"{TT}/frontend/{section['id']}")
    return cls


def subject_row(pool, frm, to, indexes=(0, 1, 2, 3, 4), days=DAYS):
    subjects = {day: pool["subjects"][indexes[i % len(indexes)]]["id"] for i, day in enumerate(days)}
    return {"time": {"from": frm, "to": to}, "type": "subject", "subjects": subjects}


def special_row(frm, to, label="LUNCH"):
    return {"time": {"from": frm, "to": to}, "type": "special", "label": label}


def save(admin, section_id, rows, method="post"):
    if method == "post":
        return admin.post(f"{TT}/frontend", json={"section_id": section_id, "timetable_data": rows})
    return admin.put(f"{TT}/frontend/{section_id}", json={"section_id": section_id, "timetable_data": rows})


def sorted_rows(response):
    return sorted(response.json()["timetable_data"], key=lambda r: r["time"]["from"])
