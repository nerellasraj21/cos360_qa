import pytest

from api_tests.students import helpers as h
from api_tests.support import Cleanup


@pytest.fixture(scope="session", autouse=True)
def self_service_grants(admin):
    added = h.apply_self_service_grants(admin)
    yield added
    h.revert_self_service_grants(admin, added)


@pytest.fixture(scope="module")
def klass(admin, academic_year_id):
    stack = Cleanup()
    created = h.make_class(admin, academic_year_id, stack)
    yield created
    stack.run()


@pytest.fixture
def make_admission(admin, academic_year_id, klass, cleanup):
    def factory(section="A", klass_override=None, **overrides):
        return h.create_admission(admin, academic_year_id, klass_override or klass, cleanup, section=section, **overrides)

    return factory


@pytest.fixture
def adm(make_admission):
    return make_admission()


class Family:
    pass


@pytest.fixture(scope="module")
def family(admin, academic_year_id, klass):
    stack = Cleanup()
    fam = Family()
    fam.klass = klass
    fam.c1 = h.create_admission(admin, academic_year_id, klass, stack, section="A")
    shared_father = {
        "name": "Shared Father",
        "email": fam.c1.father_email,
        "phone": "9000000101",
        "relation_to_student": "Father",
    }
    fam.c2 = h.create_admission(
        admin,
        academic_year_id,
        klass,
        stack,
        section="B",
        student={"father": shared_father},
    )
    fam.other = h.create_admission(admin, academic_year_id, klass, stack, section="A")
    fam.father_email = fam.c1.father_email
    fam.other_father_email = fam.other.father_email
    fam.c1_student = h.student_client(fam.c1, stack, academic_year_id)
    fam.other_student = h.student_client(fam.other, stack, academic_year_id)
    fam.parent = h.parent_client(fam.father_email, stack, academic_year_id)
    fam.other_parent = h.parent_client(fam.other_father_email, stack, academic_year_id)
    yield fam
    stack.run()


@pytest.fixture(scope="module")
def grid(admin, academic_year_id):
    stack = Cleanup()
    fam = Family()
    fam.klass = h.make_class(admin, academic_year_id, stack)
    guardian = {
        "name": "Grid Guardian",
        "email": f"{h.unique('stu_gg')}@example.com",
        "phone": "9123400000",
        "relation_to_student": "Guardian",
    }
    fam.a1 = h.create_admission(
        admin, academic_year_id, fam.klass, stack, section="A", admission_date=h.past_date(10), student={"guardian": guardian}
    )
    fam.a2 = h.create_admission(admin, academic_year_id, fam.klass, stack, section="A")
    fam.b1 = h.create_admission(admin, academic_year_id, fam.klass, stack, section="B")
    fam.i1 = h.create_admission(admin, academic_year_id, fam.klass, stack, section="A")
    assert admin.patch(f"/students/admission/{fam.i1.student_id}/toggle-active").status_code == 200
    yield fam
    stack.run()
