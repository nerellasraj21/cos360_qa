import pytest

from api_tests.students import helpers as h
from api_tests.support import Cleanup, unique


@pytest.fixture(scope="session", autouse=True)
def self_service_grants(admin):
    added = h.apply_self_service_grants(admin, only={"student_certificates"})
    yield added
    h.revert_self_service_grants(admin, added)


class Fam:
    pass


@pytest.fixture(scope="module")
def cfam(admin, academic_year_id):
    stack = Cleanup()
    fam = Fam()
    fam.klass = h.make_class(admin, academic_year_id, stack, prefix="cer_")
    fam.s1 = h.create_admission(admin, academic_year_id, fam.klass, stack, section="A")
    fam.s2 = h.create_admission(admin, academic_year_id, fam.klass, stack, section="B")
    fam.s1_client = h.student_client(fam.s1, stack, academic_year_id)
    fam.s2_client = h.student_client(fam.s2, stack, academic_year_id)
    fam.p1_client = h.parent_client(fam.s1.father_email, stack, academic_year_id)
    fam.p2_client = h.parent_client(fam.s2.father_email, stack, academic_year_id)
    yield fam
    stack.run()


@pytest.fixture
def ctype(admin, cleanup):
    response = admin.post("/certificates/types/", json={"name": unique("cer_t"), "description": "qa type"})
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"/certificates/types/{response.json()['id']}")
    return response.json()
