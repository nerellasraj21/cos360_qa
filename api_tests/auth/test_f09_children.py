import pytest

from api_tests.auth.helpers import (
    MISSING_AUTH,
    TEMP_PARENT_PASSWORD,
    create_family,
    detail_text,
    fresh_login,
    set_password,
)
from api_tests.support import QA_B_TENANT

CHILD_FIELDS = {
    "id",
    "first_name",
    "last_name",
    "name",
    "is_active",
    "date_of_birth",
    "gender",
    "admission_number",
    "academic_year_id",
    "academic_year",
    "class_id",
    "class_name",
    "section_id",
    "section_name",
}


@pytest.fixture
def two_children(admin, cleanup, year_id, api_client):
    first = create_family(admin, cleanup, year_id)
    second = create_family(admin, cleanup, year_id, class_id=first.class_id, father_email=first.father_email)
    data = first.father_login()
    return first, second, data, api_client(token=data["access_token"])


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A01")
def test_parent_lists_both_children_ordered(two_children):
    first, second, _, parent = two_children
    response = parent.get("/student-parent-links/my-children")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 2
    assert [r["first_name"] for r in rows] == sorted(r["first_name"] for r in rows)
    assert {r["id"] for r in rows} == {first.student_id, second.student_id}
    for row in rows:
        assert set(row) == CHILD_FIELDS
        assert row["class_id"] == first.class_id
        assert row["admission_number"] in (first.admission_number, second.admission_number)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A02")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher", "student"])
def test_children_endpoint_parent_only(role_clients, role):
    response = role_clients[role].get("/student-parent-links/my-children")
    assert response.status_code == 403
    assert detail_text(response) == "Only parents can access this endpoint"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A03")
def test_parent_without_profile_404(parent):
    response = parent.get("/student-parent-links/my-children")
    assert response.status_code == 404
    assert detail_text(response) == "Parent profile not found"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A04")
@pytest.mark.skip(reason="blocked: no API creates a second admission for an existing student")
def test_child_with_two_admissions_uses_latest():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A05")
@pytest.mark.skip(reason="blocked: admission is mandatory at creation, so a child without admission cannot be produced")
def test_child_without_admission_has_null_class():
    pass


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A06")
def test_parent_reads_own_students(two_children):
    first, second, data, parent = two_children
    response = parent.get(f"/student-parent-links/parent/{data['entity_id']}/students")
    assert response.status_code == 200
    assert first.student_id in str(response.json()) and second.student_id in str(response.json())


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A07")
def test_parent_cannot_read_other_parents_children(two_children, admin, cleanup, year_id):
    _, _, _, parent = two_children
    other = create_family(admin, cleanup, year_id)
    other_data = other.father_login()
    response = parent.get(f"/student-parent-links/parent/{other_data['entity_id']}/students")
    assert response.status_code == 403
    assert detail_text(response) == "You can only view your own children"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A08")
@pytest.mark.parametrize("role,expected", [("admin", 200), ("teacher", 403), ("student", 403)])
def test_parent_students_path_for_other_roles(two_children, role_clients, role, expected):
    _, _, data, _ = two_children
    response = role_clients[role].get(f"/student-parent-links/parent/{data['entity_id']}/students")
    assert response.status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A09")
def test_children_of_other_tenant_never_returned(two_children, tenant_b, cleanup):
    _, _, _, parent = two_children
    other = create_family(tenant_b, cleanup, tenant_b.academic_year_id)
    first = fresh_login(
        other.father_email, TEMP_PARENT_PASSWORD, tenant_b.academic_year_id, tenant=QA_B_TENANT
    ).json()
    done = set_password(first["change_password_token"], "Password#11", tenant=QA_B_TENANT).json()
    response = parent.get(f"/student-parent-links/parent/{done['entity_id']}/students")
    assert other.student_id not in response.text
    assert response.status_code in (403, 404)


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A10")
@pytest.mark.parametrize("path", ["/student-parent-links/my-children"])
def test_children_requires_token(anon, path):
    response = anon.get(path)
    assert response.status_code == 401
    assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-09-A11")
def test_student_header_is_ignored(two_children, admin, cleanup, year_id):
    _, _, _, parent = two_children
    stranger = create_family(admin, cleanup, year_id)
    plain = parent.get("/student-parent-links/my-children").json()
    with_header = parent.get("/student-parent-links/my-children", headers={"X-Student-ID": stranger.student_id})
    assert with_header.status_code == 200
    assert with_header.json() == plain
