import pytest

from api_tests.certificates.helpers import CERT, UNKNOWN
from api_tests.students import helpers as h

SEL = f"{CERT}/selector"


@pytest.fixture(scope="module")
def sel(admin, academic_year_id):
    from api_tests.support import Cleanup

    stack = Cleanup()
    holder = type("Sel", (), {})()
    holder.klass = h.make_class(admin, academic_year_id, stack, prefix="cer_")
    holder.empty = h.make_class(admin, academic_year_id, stack, prefix="cer_")
    holder.a = h.create_admission(admin, academic_year_id, holder.klass, stack, section="A")
    holder.b = h.create_admission(admin, academic_year_id, holder.klass, stack, section="B")
    holder.inactive = h.create_admission(admin, academic_year_id, holder.klass, stack, section="A")
    assert admin.patch(f"/students/admission/{holder.inactive.student_id}/toggle-active").status_code == 200
    yield holder
    stack.run()


def student_ids(response):
    return [row["student_id"] for row in response.json()]


@pytest.mark.api
@pytest.mark.tc("TC-CER-03-A01")
def test_selector_classes(admin, sel):
    response = admin.get(f"{SEL}/classes")
    assert response.status_code == 200
    rows = response.json()
    assert all(set(r) == {"id", "name"} for r in rows)
    names = [r["name"] for r in rows]
    assert names == sorted(names)
    assert {"id": sel.klass["id"], "name": sel.klass["name"]} in rows


@pytest.mark.api
@pytest.mark.tc("TC-CER-03-A02")
def test_selector_sections(admin, sel):
    response = admin.get(f"{SEL}/sections", params={"class_id": sel.klass["id"]})
    assert response.status_code == 200
    assert response.json() == [
        {"id": sel.klass["sections"]["A"], "name": "A"},
        {"id": sel.klass["sections"]["B"], "name": "B"},
    ]
    assert admin.get(f"{SEL}/sections").status_code == 422
    assert admin.get(f"{SEL}/sections", params={"class_id": "abc"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-03-A03")
def test_selector_students_by_class_and_section(admin, sel):
    whole = admin.get(f"{SEL}/students", params={"class_id": sel.klass["id"]})
    assert whole.status_code == 200
    assert sorted(student_ids(whole)) == sorted([sel.a.student_id, sel.b.student_id, sel.inactive.student_id])
    row = next(r for r in whole.json() if r["student_id"] == sel.a.student_id)
    assert set(row) == {"student_id", "full_name", "admission_no"}
    assert row["admission_no"] == sel.a.number
    only_b = admin.get(f"{SEL}/students", params={"class_id": sel.klass["id"], "section_id": sel.klass["sections"]["B"]})
    assert student_ids(only_b) == [sel.b.student_id]


@pytest.mark.api
@pytest.mark.tc("TC-CER-03-A04")
def test_selector_class_without_students(admin, sel):
    response = admin.get(f"{SEL}/students", params={"class_id": sel.empty["id"]})
    assert response.status_code == 200 and response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-CER-03-A05")
def test_selector_includes_deactivated_students(admin, sel):
    response = admin.get(f"{SEL}/students", params={"class_id": sel.klass["id"]})
    assert sel.inactive.student_id in student_ids(response)


@pytest.mark.api
@pytest.mark.tc("TC-CER-03-A06")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 403), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_selector_permission_matrix(role_clients, sel, role, status):
    client = role_clients[role]
    assert client.get(f"{SEL}/classes").status_code == status
    assert client.get(f"{SEL}/sections", params={"class_id": sel.klass["id"]}).status_code == status
    denied = client.get(f"{SEL}/students", params={"class_id": sel.klass["id"]})
    assert denied.status_code == status
    if status == 403:
        assert denied.json()["detail"] == "Only Admin can access the student selector"


@pytest.mark.api
@pytest.mark.tc("TC-CER-03-A07")
def test_selector_requires_token(anon):
    assert anon.get(f"{SEL}/classes").status_code == 401
    assert anon.get(f"{SEL}/sections", params={"class_id": UNKNOWN}).status_code == 401
    assert anon.get(f"{SEL}/students", params={"class_id": UNKNOWN}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-03-A08")
def test_selector_tenant_isolation(admin, tenant_b, tenant_b_name, sel):
    assert sel.klass["id"] not in [c["id"] for c in tenant_b.get(f"{SEL}/classes").json()]
    assert tenant_b.get(f"{SEL}/students", params={"class_id": sel.klass["id"]}).json() == []
    assert tenant_b.get(f"{SEL}/sections", params={"class_id": sel.klass["id"]}).json() == []
    header = {"cschema": tenant_b_name}
    assert admin.get(f"{SEL}/classes", headers=header).status_code == 403
    assert admin.get(f"{SEL}/students", params={"class_id": sel.klass["id"]}, headers=header).status_code == 403
