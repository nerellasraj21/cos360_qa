import uuid

import pytest

from api_tests.support import Cleanup
from api_tests.transport.helpers import (
    make_assignment,
    make_chain,
    make_student,
    other_tenant_header,
    parent_client,
    student_client,
)

BASE = "/students/student-transport/student/"


@pytest.fixture(scope="module")
def world(admin, academic_year_id):
    stack = Cleanup()
    try:
        chain = make_chain(admin, stack, fees=1500)
        with_transport = make_student(admin, stack, academic_year_id)
        without_transport = make_student(admin, stack, academic_year_id)
        assignment = make_assignment(
            admin, stack, with_transport["student_id"], chain["trip"]["id"], chain["stop"]["id"], fee_per_term=1500
        )
        yield {
            "chain": chain,
            "with": with_transport,
            "without": without_transport,
            "assignment": assignment,
            "student_api": student_client(with_transport),
            "student_empty_api": student_client(without_transport),
            "parent_api": parent_client(with_transport),
        }
    finally:
        stack.run()


@pytest.mark.api
@pytest.mark.tc("TC-TRN-10-A01")
def test_student_reads_own_transport(world):
    response = world["student_api"].get(f"{BASE}{world['with']['student_id']}")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["id"] for row in rows] == [world["assignment"]["id"]]
    assert rows[0]["trip"]["route"]["id"] == world["chain"]["route"]["id"]
    assert rows[0]["trip"]["vehicle"]["id"] == world["chain"]["vehicle"]["id"]
    assert rows[0]["stop"]["id"] == world["chain"]["stop"]["id"]
    assert rows[0]["fee_per_term"] == 1500.0


@pytest.mark.api
@pytest.mark.tc("TC-TRN-10-A02")
def test_student_cannot_read_other_student(world, student):
    other = world["student_empty_api"].get(f"{BASE}{world['with']['student_id']}")
    assert other.status_code == 403
    assert "own transport" in other.text
    assert student.get(f"{BASE}{world['with']['student_id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TRN-10-A03")
def test_student_without_assignment(world):
    response = world["student_empty_api"].get(f"{BASE}{world['without']['student_id']}")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.api
@pytest.mark.tc("TC-TRN-10-A04")
def test_parent_reads_linked_child(world):
    response = world["parent_api"].get(f"{BASE}{world['with']['student_id']}")
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [world["assignment"]["id"]]


@pytest.mark.api
@pytest.mark.tc("TC-TRN-10-A05")
def test_parent_cannot_read_unlinked_student(world, parent):
    unlinked = world["parent_api"].get(f"{BASE}{world['without']['student_id']}")
    assert unlinked.status_code == 403
    assert "own children" in unlinked.text
    assert parent.get(f"{BASE}{world['with']['student_id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TRN-10-A06")
@pytest.mark.parametrize("role", ["admin", "staff"])
def test_staff_roles_read_any_student(role_clients, world, role):
    response = role_clients[role].get(f"{BASE}{world['with']['student_id']}")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.api
@pytest.mark.tc("TC-TRN-10-A07")
def test_teacher_denied(teacher, world):
    assert teacher.get(f"{BASE}{world['with']['student_id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-TRN-10-A08")
def test_unknown_student(admin):
    response = admin.get(f"{BASE}{uuid.uuid4()}")
    assert response.status_code == 404
    assert "Student not found" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-TRN-10-A09")
def test_no_token(anon, world):
    assert anon.get(f"{BASE}{world['with']['student_id']}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-TRN-10-A10")
def test_tenant_isolation(admin, tenant_b, world):
    response = tenant_b.get(f"{BASE}{world['with']['student_id']}")
    assert response.status_code == 404
    assert "Student not found" in response.text
    assert other_tenant_header(admin).get(f"{BASE}{world['with']['student_id']}").status_code == 403
