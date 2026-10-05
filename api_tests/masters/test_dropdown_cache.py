import pytest

from api_tests.masters.helpers import make_category, make_class, make_subject, make_year
from api_tests.support import unique

CLASSES = "/masters/class_sections"
SUBJECTS = "/masters/subjects"
HOLIDAYS = "/masters/holidays"
CATEGORIES = "/masters/subject_categories/categories"
YEARS = "/masters/academic_years"


@pytest.mark.api
@pytest.mark.tc("TC-MST-15-A01")
def test_create_is_visible_in_every_dropdown(admin, cleanup, pool):
    admin.get(f"{YEARS}/dropdown?active_only=false")
    year = make_year(admin, cleanup)
    assert {"id": year["id"], "title": year["title"]} in admin.get(f"{YEARS}/dropdown?active_only=false").json()

    admin.get(f"{CLASSES}/dropdown")
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=None)
    assert {"id": cls["id"], "name": cls["name"]} in admin.get(f"{CLASSES}/dropdown").json()

    admin.get(f"{CATEGORIES}/dropdown")
    category = make_category(admin, cleanup)
    assert {"id": category["id"], "name": category["name"]} in admin.get(f"{CATEGORIES}/dropdown").json()

    admin.get(f"{SUBJECTS}/dropdown")
    subject = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    assert {"id": subject["id"], "name": subject["name"]} in admin.get(f"{SUBJECTS}/dropdown").json()

    admin.get(f"{HOLIDAYS}/dropdown")
    body = {
        "name": unique("mstcache"),
        "start_date": "1001-01-01",
        "end_date": "1001-01-02",
        "is_active": True,
        "academic_year_id": pool["year2"]["id"],
    }
    created = admin.post(f"{HOLIDAYS}/", json=body)
    assert created.status_code == 200
    holiday = created.json()
    cleanup.delete_later(admin, f"{HOLIDAYS}/{holiday['id']}")
    assert {"id": holiday["id"], "name": holiday["name"]} in admin.get(f"{HOLIDAYS}/dropdown").json()


@pytest.mark.api
@pytest.mark.tc("TC-MST-15-A02")
def test_subject_rename_is_visible_immediately(admin, cleanup, pool):
    subject = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    admin.get(f"{SUBJECTS}/dropdown")
    new = unique("mstsub")
    assert admin.put(f"{SUBJECTS}/{subject['id']}", json={"name": new}).status_code == 200
    rows = admin.get(f"{SUBJECTS}/dropdown").json()
    assert {"id": subject["id"], "name": new} in rows
    assert {"id": subject["id"], "name": subject["name"]} not in rows


@pytest.mark.api
@pytest.mark.tc("TC-MST-15-A03")
def test_subject_deactivation_is_visible_immediately(admin, cleanup, pool):
    subject = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    assert subject["id"] in [r["id"] for r in admin.get(f"{SUBJECTS}/dropdown").json()]
    assert admin.delete(f"{SUBJECTS}/{subject['id']}").status_code == 204
    assert subject["id"] not in [r["id"] for r in admin.get(f"{SUBJECTS}/dropdown").json()]


@pytest.mark.api
@pytest.mark.tc("TC-MST-15-A04")
def test_section_add_and_rename_are_visible_immediately(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=("A",))
    path = f"{CLASSES}/by_class_id/{cls['id']}/sections"
    assert [r["name"] for r in admin.get(path).json()] == ["A"]
    assert admin.post(f"{CLASSES}/{cls['id']}/sections", json=[{"name": "B"}]).status_code == 201
    assert sorted(r["name"] for r in admin.get(path).json()) == ["A", "B"]
    section = cls["sections"][0]
    assert admin.put(f"{CLASSES}/sections/{section['id']}", json={"id": None, "name": "A2"}).status_code == 200
    assert sorted(r["name"] for r in admin.get(path).json()) == ["A2", "B"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-15-A05")
def test_dropdown_cache_is_tenant_scoped(admin, tenant_b, cleanup, pool):
    subject = make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    for _ in range(2):
        rows = tenant_b.get(f"{SUBJECTS}/dropdown").json()
        assert subject["id"] not in [r["id"] for r in rows]
        assert subject["name"] not in [r["name"] for r in rows]
    assert subject["id"] in [r["id"] for r in admin.get(f"{SUBJECTS}/dropdown").json()]


@pytest.mark.api
@pytest.mark.tc("TC-MST-15-A06")
def test_salary_ranges_are_stable(admin, tenant_b):
    first = admin.get("/parents/salary-ranges/dropdown").json()
    second = admin.get("/parents/salary-ranges/dropdown").json()
    other_tenant = tenant_b.get("/parents/salary-ranges/dropdown").json()
    assert first == second == other_tenant
    assert len(first) == 5


@pytest.mark.api
@pytest.mark.tc("TC-MST-15-A07")
def test_dropdown_item_shapes(admin, cleanup, pool):
    make_year(admin, cleanup)
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=("A",))
    make_category(admin, cleanup)
    make_subject(admin, cleanup, pool["year"]["id"], pool["category"]["id"])
    years = admin.get(f"{YEARS}/dropdown?active_only=false").json()
    assert years and all(set(r) == {"id", "title"} for r in years)
    for path in (
        f"{CLASSES}/dropdown",
        f"{CLASSES}/by_class_id/{cls['id']}/sections",
        f"{SUBJECTS}/dropdown",
        f"{CATEGORIES}/dropdown",
        f"{HOLIDAYS}/dropdown",
    ):
        rows = admin.get(path).json()
        assert all(set(r) == {"id", "name"} for r in rows), path
