import pytest

from api_tests.students import helpers as h
from api_tests.support import items_of, unique

DD_PATHS = ["/students/admission/students/dropdown", "/students/admission/students/dropdown/simple"]


def ids_of(response):
    return [i["id"] for i in items_of(response)]


def student_ids_of_list(response):
    return [i["student"]["id"] for i in response.json()["items"]]


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A01")
def test_list_pagination(admin, grid):
    params = {"class_id": grid.klass["id"], "limit": 2}
    first = admin.get("/students/admission/", params={**params, "skip": 0})
    assert first.status_code == 200
    body = first.json()
    assert set(body) >= {"items", "total_count", "has_next"}
    assert len(body["items"]) == 2 and body["has_next"] is True and body["total_count"] == 4
    second = admin.get("/students/admission/", params={**params, "skip": 2})
    assert len(second.json()["items"]) == 2 and second.json()["has_next"] is False
    seen = student_ids_of_list(first) + student_ids_of_list(second)
    assert sorted(seen) == sorted(m.student_id for m in (grid.a1, grid.a2, grid.b1, grid.i1))


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A02")
@pytest.mark.parametrize("params,status", [({"limit": 0}, 422), ({"limit": 101}, 422), ({"skip": -1}, 422), ({"limit": 100}, 200)])
def test_list_bounds(admin, params, status):
    assert admin.get("/students/admission/", params=params).status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A03")
def test_list_filters_by_class_and_section(admin, grid):
    response = admin.get(
        "/students/admission/",
        params={"class_id": grid.klass["id"], "section_id": grid.klass["sections"]["B"], "limit": 100},
    )
    assert student_ids_of_list(response) == [grid.b1.student_id]
    in_a = admin.get(
        "/students/admission/",
        params={"class_id": grid.klass["id"], "section_id": grid.klass["sections"]["A"], "limit": 100},
    )
    assert sorted(student_ids_of_list(in_a)) == sorted([grid.a1.student_id, grid.a2.student_id, grid.i1.student_id])


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A04")
def test_list_as_of_date(admin, grid):
    base = {"class_id": grid.klass["id"], "limit": 100}
    before = admin.get("/students/admission/", params={**base, "as_of_date": h.past_date(11)})
    assert grid.a1.student_id not in student_ids_of_list(before)
    assert grid.a2.student_id in student_ids_of_list(before)
    equal = admin.get("/students/admission/", params={**base, "as_of_date": h.past_date(10)})
    assert grid.a1.student_id in student_ids_of_list(equal)


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A05")
def test_list_includes_inactive_and_omits_guardian(admin, grid):
    items = admin.get("/students/admission/", params={"class_id": grid.klass["id"], "limit": 100}).json()["items"]
    inactive = next(i for i in items if i["student"]["id"] == grid.i1.student_id)
    assert inactive["student"]["is_active"] is False
    with_guardian = next(i for i in items if i["student"]["id"] == grid.a1.student_id)
    assert with_guardian["student"]["guardian"] is None
    assert with_guardian["student"]["father"] is not None and with_guardian["student"]["mother"] is not None
    full = admin.get(f"/students/admission/id/{grid.a1.student_id}").json()
    assert full["student"]["guardian"] is not None


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A06")
def test_search_by_name(admin, grid):
    created = grid.a2
    by_first = admin.get("/students/admission/search", params={"query": created.first_name.upper()})
    assert by_first.status_code == 200
    assert created.student_id in ids_of(by_first)
    assert len(by_first.json()) <= 10
    full = admin.get("/students/admission/search", params={"query": f"{created.first_name} {created.tag}ln"})
    assert created.student_id in ids_of(full)
    by_number = admin.get("/students/admission/search", params={"query": created.number})
    assert created.student_id not in ids_of(by_number)


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A07")
def test_search_requires_query(admin):
    assert admin.get("/students/admission/search", params={"query": ""}).status_code == 422
    assert admin.get("/students/admission/search").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A08")
def test_student_lists_and_searches_only_own_row(family):
    listing = family.c1_student.get("/students/admission/")
    assert listing.status_code == 200
    assert listing.json()["total_count"] == 1
    assert student_ids_of_list(listing) == [family.c1.student_id]
    search = family.c1_student.get("/students/admission/search", params={"query": "stu_"})
    assert search.status_code == 200
    assert ids_of(search) == [family.c1.student_id]


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A08")
def test_shared_qa_student_has_no_records(student):
    listing = student.get("/students/admission/")
    assert listing.status_code == 200
    assert listing.json() == {"items": [], "total_count": 0, "has_next": False}


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A09")
def test_parent_lists_only_linked_children(family):
    listing = family.parent.get("/students/admission/", params={"limit": 100})
    assert listing.status_code == 200
    assert sorted(student_ids_of_list(listing)) == sorted([family.c1.student_id, family.c2.student_id])
    assert listing.json()["total_count"] == 2
    search = family.parent.get("/students/admission/search", params={"query": "stu_"})
    assert sorted(ids_of(search)) == sorted([family.c1.student_id, family.c2.student_id])
    other = family.other_parent.get("/students/admission/", params={"limit": 100})
    assert student_ids_of_list(other) == [family.other.student_id]


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A09")
def test_shared_qa_parent_has_no_children(parent):
    assert parent.get("/students/admission/").json() == {"items": [], "total_count": 0, "has_next": False}


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A10")
@pytest.mark.parametrize("role", ["staff", "teacher"])
def test_staff_and_teacher_list_everything(role_clients, family, role):
    response = role_clients[role].get("/students/admission/", params={"class_id": family.klass["id"], "limit": 100})
    assert response.status_code == 200
    found = student_ids_of_list(response)
    for member in (family.c1, family.c2, family.other):
        assert member.student_id in found


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A11")
def test_dropdowns_exclude_inactive_by_default(admin, grid):
    active = {grid.a1.student_id, grid.a2.student_id, grid.b1.student_id}
    for path in DD_PATHS:
        default = admin.get(path, params={"class_id": grid.klass["id"]})
        assert default.status_code == 200
        assert set(ids_of(default)) == active
        everyone = admin.get(path, params={"class_id": grid.klass["id"], "active_only": "false"})
        assert set(ids_of(everyone)) == active | {grid.i1.student_id}
    rich = next(r for r in admin.get(DD_PATHS[0], params={"class_id": grid.klass["id"]}).json() if r["id"] == grid.a2.student_id)
    assert rich["display_name"] == f"{grid.a2.first_name} {grid.a2.tag}ln ({grid.a2.number})"
    assert set(rich) == {"id", "display_name", "first_name", "last_name", "admission_number"}
    simple = admin.get(DD_PATHS[1], params={"class_id": grid.klass["id"]}).json()[0]
    assert set(simple) == {"id", "name"}


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A11")
def test_dropdown_filters_by_section(admin, grid):
    response = admin.get(
        DD_PATHS[1], params={"class_id": grid.klass["id"], "section_id": grid.klass["sections"]["B"]}
    )
    assert ids_of(response) == [grid.b1.student_id]


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A12")
@pytest.mark.parametrize("path", DD_PATHS)
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 403), ("parent", 403)]
)
def test_dropdown_permission_matrix(role_clients, path, role, status):
    assert role_clients[role].get(path).status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A13")
def test_by_admission_lookup(admin, family):
    adm = family.c1
    ok = admin.get(f"/students/admission/by-admission/{adm.admission_id}")
    assert ok.status_code == 200
    assert ok.json()["id"] == adm.student_id
    for bad in (adm.student_id, "00000000-0000-0000-0000-000000000001"):
        missing = admin.get(f"/students/admission/by-admission/{bad}")
        assert missing.status_code == 404
        assert missing.json()["detail"]["message"] == "Admission ID not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A14")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 403), ("parent", 403)]
)
def test_by_admission_permission_matrix(role_clients, family, role, status):
    response = role_clients[role].get(f"/students/admission/by-admission/{family.c1.admission_id}")
    assert response.status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A15")
@pytest.mark.parametrize(
    "path",
    [
        "/students/admission/",
        "/students/admission/search?query=a",
        "/students/admission/by-admission/00000000-0000-0000-0000-000000000001",
        *DD_PATHS,
    ],
)
def test_reads_require_token(anon, path):
    assert anon.get(path).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-06-A16")
def test_list_tenant_isolation(admin, tenant_b, tenant_b_name, family):
    listing = tenant_b.get("/students/admission/", params={"limit": 100})
    assert listing.status_code == 200
    assert family.c1.student_id not in student_ids_of_list(listing)
    for path in ("/students/admission/", "/students/admission/search?query=stu_", *DD_PATHS):
        assert admin.get(path, headers={"cschema": tenant_b_name}).status_code == 403
    assert family.c1.student_id not in ids_of(tenant_b.get("/students/admission/search", params={"query": "stu_"}))


@pytest.mark.api
@pytest.mark.tc("TC-STU-07-A01")
def test_admin_reads_full_admission(admin, family):
    adm = family.other
    response = admin.get(f"/students/admission/id/{adm.student_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == adm.admission_id
    assert body["admission_number"] == adm.number
    assert body["address_line1"] == "12 Test Street"
    student = body["student"]
    assert student["id"] == adm.student_id
    assert {"father", "mother", "guardian", "photo_url", "is_active"} <= set(student)
    assert student["father"]["name"] == f"{adm.tag} Father"
    assert student["mother"]["email"] == adm.mother_email
    assert student["date_of_birth"] == "2015-04-10"


@pytest.mark.api
@pytest.mark.tc("TC-STU-07-A02")
@pytest.mark.parametrize("which", ["admission_id", "random"])
def test_read_with_wrong_id_is_404(admin, family, which):
    adm = family.c1
    target = adm.admission_id if which == "admission_id" else "00000000-0000-0000-0000-000000000001"
    response = admin.get(f"/students/admission/id/{target}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]["message"]


@pytest.mark.api
@pytest.mark.tc("TC-STU-07-A03")
def test_student_reads_only_own_record(family):
    assert family.c1_student.get(f"/students/admission/id/{family.c1.student_id}").status_code == 200
    assert family.c1_student.get(f"/students/admission/id/{family.other.student_id}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-07-A04")
def test_parent_reads_only_linked_children(family):
    assert family.parent.get(f"/students/admission/id/{family.c1.student_id}").status_code == 200
    assert family.parent.get(f"/students/admission/id/{family.c2.student_id}").status_code == 200
    assert family.parent.get(f"/students/admission/id/{family.other.student_id}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-07-A05")
@pytest.mark.parametrize("role", ["staff", "teacher"])
def test_staff_and_teacher_read_any_student(role_clients, family, role):
    assert role_clients[role].get(f"/students/admission/id/{family.c1.student_id}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STU-07-A06")
def test_read_malformed_id_is_422(admin):
    assert admin.get("/students/admission/id/abc").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-07-A07")
def test_read_requires_token(anon, family):
    assert anon.get(f"/students/admission/id/{family.c1.student_id}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-07-A08")
def test_read_tenant_isolation(admin, tenant_b, tenant_b_name, family):
    assert tenant_b.get(f"/students/admission/id/{family.c1.student_id}").status_code == 404
    response = admin.get(f"/students/admission/id/{family.c1.student_id}", headers={"cschema": tenant_b_name})
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-17-A01")
def test_student_my_admission(family):
    response = family.c1_student.get("/students/admission/my-admission")
    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == family.c1.student_id
    assert body["admission_number"] == family.c1.number


@pytest.mark.api
@pytest.mark.tc("TC-STU-17-A02")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher"])
def test_other_roles_cannot_read_my_admission(role_clients, role):
    assert role_clients[role].get("/students/admission/my-admission").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-17-A02")
def test_parent_cannot_read_my_admission(family):
    assert family.parent.get("/students/admission/my-admission").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-17-A03")
def test_parent_my_children_admissions(family):
    response = family.parent.get("/students/admission/my-children-admissions")
    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 2
    assert sorted(i["student_id"] for i in body["items"]) == sorted([family.c1.student_id, family.c2.student_id])
    other = family.other_parent.get("/students/admission/my-children-admissions").json()
    assert [i["student_id"] for i in other["items"]] == [family.other.student_id]


@pytest.mark.api
@pytest.mark.tc("TC-STU-17-A04")
def test_parent_without_children_gets_400(parent):
    response = parent.get("/students/admission/my-children-admissions")
    assert response.status_code == 400
    assert response.json()["detail"] == "Only parents with children can access this endpoint"


@pytest.mark.api
@pytest.mark.tc("TC-STU-17-A05")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher", "student"])
def test_other_roles_cannot_read_children_admissions(role_clients, role):
    assert role_clients[role].get("/students/admission/my-children-admissions").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-17-A06")
@pytest.mark.parametrize("limit", [0, 101])
def test_my_children_admissions_limit_bounds(family, limit):
    assert family.parent.get("/students/admission/my-children-admissions", params={"limit": limit}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-17-A07")
@pytest.mark.parametrize("path", ["/students/admission/my-admission", "/students/admission/my-children-admissions"])
def test_my_views_require_token(anon, path):
    assert anon.get(path).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-17-A08")
@pytest.mark.parametrize("path", ["/students/admission/my-admission", "/students/admission/my-children-admissions"])
def test_my_views_tenant_mismatch(family, tenant_b_name, path):
    assert family.c1_student.get(path, headers={"cschema": tenant_b_name}).status_code == 403
