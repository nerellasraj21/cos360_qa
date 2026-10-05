import random

import pytest

from api_tests.masters.helpers import RANDOM_ID, ROLES, make_admission, make_class
from api_tests.support import QA_B_TENANT, QA_TENANT, Api, unique

BASE = "/parents"
SALARY_VALUES = ["below_1l", "1l_3l", "3l_5l", "5l_10l", "above_10l"]
ALL_DENIED = ["teacher", "student", "parent"]


def phone():
    return "9" + str(random.randint(100000000, 999999999))


def parent_body(token=None, **over):
    token = token or unique("")
    body = {
        "name": f"mstp_{token}",
        "email": f"mstp{token}@example.com",
        "relation_to_student": "Father",
    }
    body.update(over)
    return body


def make_parent(admin, cleanup, **over):
    response = admin.post(f"{BASE}/", json=parent_body(**over))
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}/{data['id']}")
    return data


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A01")
def test_create_parent_creates_login(admin, cleanup, pool):
    body = parent_body(phone=phone(), occupation="Engineer", gender="Male", salary_range="3l_5l")
    response = admin.post(f"{BASE}/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"{BASE}/{data['id']}")
    assert {"id", "name", "email", "phone", "occupation", "aadhar_number", "gender", "relation_to_student",
            "salary_range", "students"} <= set(data)
    assert data["name"] == body["name"] and data["email"] == body["email"]
    assert data["students"] == []
    anonymous = Api(tenant_header=QA_TENANT)
    try:
        attempt = anonymous.post(
            "/auth/login",
            json={"username": body["email"], "password": "parent@123", "academic_year_id": pool["year"]["id"]},
        )
    finally:
        anonymous.close()
    assert attempt.status_code == 200, attempt.text
    assert "change_password_token" in attempt.text or attempt.json().get("role", {}).get("name") == "Parent"


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A01")
def test_create_parent_with_phone_only_and_without_contact(admin, cleanup):
    number = phone()
    data = make_parent(admin, cleanup, email=None, phone=number)
    assert data["phone"] == number and data["email"] is None
    response = admin.post(f"{BASE}/", json={"name": "x", "relation_to_student": "Mother"})
    assert response.status_code == 400
    duplicate = admin.post(f"{BASE}/", json={"relation_to_student": "Mother", "phone": number})
    assert duplicate.status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A01")
def test_create_parent_duplicate_email_conflicts(admin, cleanup):
    first = make_parent(admin, cleanup)
    response = admin.post(f"{BASE}/", json=parent_body(email=first["email"]))
    assert response.status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A01")
def test_blank_name_defaults_to_relation(admin, cleanup):
    data = make_parent(admin, cleanup, name="", relation_to_student="Mother")
    assert data["name"] == "Mother"


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A02")
@pytest.mark.parametrize(
    "override",
    [
        {"relation_to_student": "Uncle"},
        {"aadhar_number": "12345678901"},
        {"email": "x"},
        {"salary_range": "2l_4l"},
    ],
)
def test_create_parent_validation(admin, override):
    response = admin.post(f"{BASE}/", json=parent_body(**override))
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A03")
def test_list_parents_shape_and_order(admin, cleanup):
    token = unique("")
    names = [f"mstl{token}_{c}" for c in ("a", "b", "c")]
    for name in reversed(names):
        make_parent(admin, cleanup, name=name, email=f"{name}@example.com")
    response = admin.get(f"{BASE}/?limit=1000")
    assert response.status_code == 200
    data = response.json()
    first = data
    assert set(data) == {"items", "total_count", "has_next", "skip", "limit"}
    items = list(data["items"])
    skip = len(items)
    while data["has_next"]:
        data = admin.get(f"{BASE}/?skip={skip}&limit=1000").json()
        items.extend(data["items"])
        skip += len(data["items"])
    mine = [p["name"] for p in items if token in p["name"]]
    assert mine == names
    assert all("students" in p for p in items)
    assert first["skip"] == 0 and first["limit"] == 1000


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A04")
def test_list_pagination(admin, cleanup):
    for _ in range(3):
        make_parent(admin, cleanup)
    first = admin.get(f"{BASE}/?skip=0&limit=2").json()
    assert len(first["items"]) == 2 and first["has_next"] is True
    total = admin.get(f"{BASE}/?skip=0&limit=1").json()["total_count"]
    last = admin.get(f"{BASE}/?skip={total - 2}&limit=2").json()
    assert len(last["items"]) >= 1
    assert last["has_next"] is ((total - 2 + 2) < last["total_count"])


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A05")
@pytest.mark.parametrize("query", ["limit=0", "limit=1001", "skip=-1"])
def test_list_bounds(admin, query):
    assert admin.get(f"{BASE}/?{query}").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A06")
def test_search_query_case_insensitive(admin, cleanup):
    token = unique("Ravi")
    by_name = make_parent(admin, cleanup, name=f"{token}-name")
    by_email = make_parent(admin, cleanup, name=f"x_{unique('')}", email=f"{token.upper()}@example.com")
    other = make_parent(admin, cleanup)
    response = admin.get(f"{BASE}/search", params={"search_query": token.lower()})
    assert response.status_code == 200
    ids = [p["id"] for p in response.json()["items"]]
    assert by_name["id"] in ids and by_email["id"] in ids and other["id"] not in ids


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A07")
def test_search_relation_exact(admin, cleanup):
    token = unique("")
    mother = make_parent(admin, cleanup, name=f"mstr{token}_m", relation_to_student="Mother")
    father = make_parent(admin, cleanup, name=f"mstr{token}_f", relation_to_student="Father")
    rows = admin.get(f"{BASE}/search", params={"search_query": f"mstr{token}", "relation_to_student": "Mother"}).json()
    ids = [p["id"] for p in rows["items"]]
    assert mother["id"] in ids and father["id"] not in ids
    assert all(p["relation_to_student"] == "Mother" for p in rows["items"])


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A08")
def test_search_filters_are_anded(admin, cleanup):
    token = unique("")
    father = make_parent(admin, cleanup, email=f"mstand{token}_f@example.com", relation_to_student="Father")
    mother = make_parent(admin, cleanup, email=f"mstand{token}_m@example.com", relation_to_student="Mother")
    response = admin.get(f"{BASE}/search", params={"email": f"mstand{token}", "relation_to_student": "Father"})
    ids = [p["id"] for p in response.json()["items"]]
    assert ids == [father["id"]]
    assert mother["id"] not in ids


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A09")
def test_search_limit_bounds(admin):
    assert admin.get(f"{BASE}/search?limit=100").status_code == 200
    assert admin.get(f"{BASE}/search?limit=101").status_code == 422
    assert admin.get(f"{BASE}/search?limit=0").status_code == 422
    assert admin.get(f"{BASE}/search?skip=-1").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A10")
def test_get_parent_and_not_found(admin, cleanup):
    parent = make_parent(admin, cleanup)
    ok = admin.get(f"{BASE}/{parent['id']}")
    assert ok.status_code == 200 and ok.json() == parent
    missing = admin.get(f"{BASE}/{RANDOM_ID}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Parent not found"


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A10")
def test_parent_lists_linked_student(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=("A",))
    admission = make_admission(admin, cleanup, pool["year"]["id"], cls["id"], cls["sections"][0]["id"])
    found = admin.get(f"{BASE}/search", params={"email": admission["_father_email"]}).json()["items"]
    assert len(found) == 1
    parent = admin.get(f"{BASE}/{found[0]['id']}").json()
    student = admission["student"]
    assert [s["id"] for s in parent["students"]] == [student["id"]]
    assert set(parent["students"][0]) == {"id", "first_name", "last_name"}
    assert parent["students"][0]["first_name"] == student["first_name"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A11")
def test_patch_parent(admin, cleanup):
    parent = make_parent(admin, cleanup, phone=phone())
    response = admin.patch(f"{BASE}/{parent['id']}", json={"occupation": "Engineer", "salary_range": "3l_5l"})
    assert response.status_code == 200
    data = response.json()
    assert data["occupation"] == "Engineer" and data["salary_range"] == "3l_5l"
    assert data["name"] == parent["name"] and data["email"] == parent["email"] and data["phone"] == parent["phone"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A12")
@pytest.mark.parametrize(
    "body",
    [{"gender": "M"}, {"email": ""}, {"relation_to_student": "Uncle"}, {"salary_range": "x"}],
)
def test_patch_parent_validation(admin, cleanup, body):
    parent = make_parent(admin, cleanup)
    assert admin.patch(f"{BASE}/{parent['id']}", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A13")
def test_patch_parent_overlong_aadhar(admin, cleanup):
    parent = make_parent(admin, cleanup)
    response = admin.patch(f"{BASE}/{parent['id']}", json={"aadhar_number": "1234567890123"})
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Error updating parent")


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A14")
def test_patch_unknown_parent(admin):
    assert admin.patch(f"{BASE}/{RANDOM_ID}", json={"occupation": "x"}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A15")
def test_delete_parent_keeps_student(admin, cleanup, pool):
    cls = make_class(admin, cleanup, pool["year"]["id"], sections=("A",))
    admission = make_admission(admin, cleanup, pool["year"]["id"], cls["id"], cls["sections"][0]["id"])
    found = admin.get(f"{BASE}/search", params={"email": admission["_father_email"]}).json()["items"]
    parent_id = found[0]["id"]
    response = admin.delete(f"{BASE}/{parent_id}")
    assert response.status_code == 204
    assert admin.get(f"{BASE}/{parent_id}").status_code == 404
    student = admin.get(f"/students/admission/id/{admission['student']['id']}")
    assert student.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A15")
def test_delete_plain_parent(admin):
    created = admin.post(f"{BASE}/", json=parent_body())
    assert created.status_code == 201
    assert admin.delete(f"{BASE}/{created.json()['id']}").status_code == 204


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A16")
def test_delete_unknown_parent(admin):
    assert admin.delete(f"{BASE}/{RANDOM_ID}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A17")
@pytest.mark.parametrize("role", ROLES)
def test_salary_dropdown_all_roles(role_clients, role):
    response = role_clients[role].get(f"{BASE}/salary-ranges/dropdown")
    assert response.status_code == 200
    rows = response.json()
    assert [r["value"] for r in rows] == SALARY_VALUES
    assert all(set(r) == {"value", "label", "display"} and r["label"] and r["display"] for r in rows)


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A18")
@pytest.mark.parametrize("role", ["admin", "staff"])
def test_parent_matrix_granted(role_clients, admin, cleanup, role):
    parent = make_parent(admin, cleanup)
    client = role_clients[role]
    assert client.get(f"{BASE}/").status_code == 200
    assert client.get(f"{BASE}/search").status_code == 200
    assert client.get(f"{BASE}/{parent['id']}").status_code == 200
    assert client.patch(f"{BASE}/{parent['id']}", json={"occupation": "Teacher"}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A18")
def test_staff_can_create_parent(staff, admin, cleanup):
    response = staff.post(f"{BASE}/", json=parent_body())
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{BASE}/{response.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A19")
def test_staff_cannot_delete_parent(staff, admin, cleanup):
    parent = make_parent(admin, cleanup)
    assert staff.delete(f"{BASE}/{parent['id']}").status_code == 403
    assert admin.get(f"{BASE}/{parent['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A20")
@pytest.mark.parametrize("role", ALL_DENIED)
def test_parent_endpoints_denied(role_clients, admin, cleanup, role):
    parent = make_parent(admin, cleanup)
    client = role_clients[role]
    assert client.post(f"{BASE}/", json=parent_body()).status_code == 403
    assert client.get(f"{BASE}/").status_code == 403
    assert client.get(f"{BASE}/search").status_code == 403
    assert client.get(f"{BASE}/{parent['id']}").status_code == 403
    assert client.patch(f"{BASE}/{parent['id']}", json={"occupation": "x"}).status_code == 403
    assert client.delete(f"{BASE}/{parent['id']}").status_code == 403
    assert admin.get(f"{BASE}/{parent['id']}").json()["occupation"] == parent["occupation"]


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A21")
def test_parent_endpoints_need_authentication(anon):
    assert anon.post(f"{BASE}/", json=parent_body()).status_code == 401
    for path in ("/", "/search", f"/{RANDOM_ID}", "/salary-ranges/dropdown"):
        assert anon.get(f"{BASE}{path}").status_code == 401, path
    assert anon.patch(f"{BASE}/{RANDOM_ID}", json={"occupation": "x"}).status_code == 401
    assert anon.delete(f"{BASE}/{RANDOM_ID}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-11-A22")
def test_parent_tenant_isolation(admin, tenant_b, cleanup):
    parent = make_parent(admin, cleanup)
    assert parent["id"] not in [p["id"] for p in tenant_b.get(f"{BASE}/?limit=1000").json()["items"]]
    assert tenant_b.get(f"{BASE}/search", params={"email": parent["email"]}).json()["items"] == []
    assert tenant_b.get(f"{BASE}/{parent['id']}").status_code == 404
    assert tenant_b.patch(f"{BASE}/{parent['id']}", json={"occupation": "x"}).status_code == 404
    assert tenant_b.delete(f"{BASE}/{parent['id']}").status_code == 404
    assert admin.get(f"{BASE}/{parent['id']}").status_code == 200
    assert admin.get(f"{BASE}/", headers={"cschema": QA_B_TENANT}).status_code == 403
