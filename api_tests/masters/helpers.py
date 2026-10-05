import random

from api_tests.support import unique

POOL_YEAR_TITLE = "mstpool_year"
POOL_YEAR2_TITLE = "mstpool_year2"
POOL_CATEGORY_NAME = "mstpool_category"
POOL_SUBJECT_COUNT = 6
RANDOM_ID = "00000000-0000-4000-8000-000000000001"
ROLES = ["admin", "staff", "teacher", "student", "parent"]
DENIED = ["staff", "teacher", "student", "parent"]

_pool_cache: dict = {}


def year_body(prefix: str = "msty", **over) -> dict:
    n = random.randint(1100, 1900)
    body = {
        "title": unique(prefix),
        "start_date": f"{n}-04-01",
        "end_date": f"{n + 1}-03-31",
        "is_active": False,
    }
    body.update(over)
    return body


def make_year(admin, cleanup, **over) -> dict:
    response = admin.post("/masters/academic_years/", json=year_body(**over))
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/academic_years/{data['id']}/permanent")
    return data


def class_body(year_id: str, sections=("A", "B"), **over) -> dict:
    body = {"name": unique("mstc"), "short_code": unique("c")[:10], "academic_year_id": year_id}
    if sections is not None:
        body["sections"] = [{"name": s} for s in sections]
    body.update(over)
    return body


def make_class(admin, cleanup, year_id: str, sections=("A", "B"), **over) -> dict:
    response = admin.post("/masters/class_sections/", json=class_body(year_id, sections, **over))
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/class_sections/{data['id']}")
    return data


def find_or_create_year(admin, title: str, start: str, end: str) -> dict:
    listing = admin.get("/masters/academic_years/?active_only=false&limit=1000")
    assert listing.status_code == 200, listing.text
    for item in listing.json()["items"]:
        if item["title"] == title:
            return item
    response = admin.post(
        "/masters/academic_years/",
        json={"title": title, "start_date": start, "end_date": end, "is_active": False},
    )
    assert response.status_code == 201, response.text
    return response.json()


def find_or_create_category(admin, name: str) -> dict:
    listing = admin.get("/masters/subject_categories/categories?limit=1000")
    assert listing.status_code == 200, listing.text
    for item in listing.json()["items"]:
        if item["name"] == name:
            return item
    response = admin.post("/masters/subject_categories/categories", json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()


def get_pool(admin) -> dict:
    if _pool_cache:
        return _pool_cache
    year = find_or_create_year(admin, POOL_YEAR_TITLE, "1000-04-01", "1001-03-31")
    year2 = find_or_create_year(admin, POOL_YEAR2_TITLE, "1002-04-01", "1003-03-31")
    category = find_or_create_category(admin, POOL_CATEGORY_NAME)
    listing = admin.get(f"/masters/subjects/?active_only=false&academic_year_id={year['id']}")
    assert listing.status_code == 200, listing.text
    existing = {s["name"]: s for s in listing.json()}
    subjects = []
    for i in range(1, POOL_SUBJECT_COUNT + 1):
        name = f"mstpool_s{i}"
        subject = existing.get(name)
        if subject is None:
            response = admin.post(
                "/masters/subjects/",
                json={
                    "name": name,
                    "short_code": f"mstps{i}",
                    "category_id": category["id"],
                    "academic_year_id": year["id"],
                    "is_active": True,
                },
            )
            assert response.status_code == 200, response.text
            subject = response.json()
        elif not subject["is_active"]:
            response = admin.put(f"/masters/subjects/{subject['id']}", json={"is_active": True})
            assert response.status_code == 200, response.text
            subject = response.json()
        subjects.append(subject)
    _pool_cache.update({"year": year, "year2": year2, "category": category, "subjects": subjects})
    return _pool_cache


def make_category(admin, cleanup, **over) -> dict:
    body = {"name": unique("mstcat")}
    body.update(over)
    response = admin.post("/masters/subject_categories/categories", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/subject_categories/categories/{data['id']}")
    return data


def make_subject(admin, cleanup, year_id: str, category_id: str, **over) -> dict:
    body = {
        "name": unique("mstsub"),
        "short_code": unique("s")[:10],
        "category_id": category_id,
        "academic_year_id": year_id,
        "is_active": True,
    }
    body.update(over)
    response = admin.post("/masters/subjects/", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/subjects/{data['id']}")
    return data


def make_mapping(admin, cleanup, class_id, section_id, subject_id, year_id, **over) -> dict:
    body = {
        "class_id": class_id,
        "section_id": section_id,
        "subject_id": subject_id,
        "academic_year_id": year_id,
    }
    body.update(over)
    response = admin.post("/masters/class-subject-mappings/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/class-subject-mappings/{data['id']}")
    return data


def assert_denied(response):
    assert response.status_code == 403, response.text


def make_admission(
    admin, cleanup, year_id: str, class_id: str, section_id: str, father_email: str | None = None, student_extra: dict | None = None
) -> dict:
    token = unique("")
    father_email = father_email or f"mstf{token}@example.com"
    body = {
        "academic_year_id": year_id,
        "admitted_class_id": class_id,
        "admitted_section_id": section_id,
        "current_class_id": class_id,
        "current_section_id": section_id,
        "address_line1": "1 Test Street",
        "admission_number": f"MST{token}",
        "student": {
            "first_name": f"Mst{token}",
            "last_name": "Student",
            "date_of_birth": "2015-01-01",
            "gender": "Male",
            "father": {
                "name": f"MstFather{token}",
                "phone": "9" + str(random.randint(100000000, 999999999)),
                "email": father_email,
                "relation_to_student": "Father",
            },
            "mother": {"relation_to_student": "Mother"},
        },
    }
    body["student"].update(student_extra or {})
    response = admin.post("/students/admission/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/students/admission/{data['id']}")
    data["_father_email"] = father_email
    return data
