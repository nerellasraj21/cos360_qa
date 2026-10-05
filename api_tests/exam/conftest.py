import pytest

from api_tests.conftest import env
from api_tests.exam.helpers import bands
from api_tests.support import QA_TENANT, Api, Cleanup, login, unique

PASSWORD = "Exm@12345"


def _active_year_id():
    anon = Api(tenant_header=QA_TENANT)
    try:
        years = anon.get("/auth/academic-years").json()
    finally:
        anon.close()
    active = [y for y in years if y.get("is_active")]
    return (active or years)[0]["id"]


def _login_with_year(username, password, year_id):
    anon = Api(tenant_header=QA_TENANT)
    try:
        response = anon.post("/auth/login", json={"username": username, "password": password, "academic_year_id": year_id})
        response.raise_for_status()
        data = response.json()
        data["_academic_year_id"] = year_id
        return data
    finally:
        anon.close()


@pytest.fixture(scope="session")
def logins():
    year_id = _active_year_id()
    result = {}
    for role in ("admin", "staff", "teacher", "student", "parent"):
        result[role] = _login_with_year(env(f"QA_{role.upper()}_USER"), env(f"QA_{role.upper()}_PASSWORD"), year_id)
    return result


def first_login(username, default_password, year_id):
    anon = Api(tenant_header=QA_TENANT)
    try:
        response = anon.post("/auth/login", json={"username": username, "password": default_password, "academic_year_id": year_id})
        assert response.status_code == 200, response.text
        data = response.json()
        token = data.get("change_password_token")
        if token:
            done = anon.post(
                "/auth/staff/set-password",
                json={"change_password_token": token, "new_password": PASSWORD, "confirm_password": PASSWORD},
            )
            assert done.status_code == 200, done.text
            data = done.json()
        return data
    finally:
        anon.close()


class World:
    def __init__(self, admin, year_id):
        self.admin = admin
        self.year_id = year_id
        self.tag = unique("exm_")
        self.cleanup = Cleanup()
        self.sections = {}
        self.subjects = {}
        self.students = []
        self.mapping_ids = []
        self.admission_ids = []
        self.scheme_id = None
        self._clients = {}

    def build(self, student_count=3):
        admin = self.admin
        response = admin.post(
            "/masters/class_sections/",
            json={
                "name": self.tag,
                "short_code": self.tag[:10],
                "academic_year_id": self.year_id,
                "is_active": True,
                "sections": [{"name": "A", "is_active": True}, {"name": "B", "is_active": True}, {"name": "C", "is_active": True}],
            },
        )
        assert response.status_code == 201, response.text
        data = response.json()
        self.class_id = data["id"]
        for s in data["sections"]:
            self.sections[s["name"].lower()] = s["id"]
        self.cleanup.add(admin.delete, f"/masters/class_sections/{self.class_id}")

        cats = admin.get("/masters/subject_categories/categories").json()["items"]
        shared = next((c for c in cats if c["name"] == "exm_shared_category"), None)
        if shared is None:
            created = admin.post("/masters/subject_categories/categories", json={"name": "exm_shared_category"})
            assert created.status_code == 200, created.text
            shared = created.json()
        for key in ("math", "sci", "eng", "extra", "excl"):
            name = f"{self.tag}{key}"
            created = admin.post(
                "/masters/subjects/",
                json={"name": name, "short_code": name[-10:], "category_id": shared["id"], "academic_year_id": self.year_id, "is_active": True},
            )
            assert created.status_code == 200, created.text
            self.subjects[key] = created.json()["id"]
            self.cleanup.add(admin.delete, f"/masters/subjects/{created.json()['id']}")

        plan = {"a": ["math", "sci", "eng", "excl"], "b": ["math", "sci"], "c": ["math", "sci", "eng"]}
        for sec, subs in plan.items():
            body = {
                "class_id": self.class_id,
                "section_id": self.sections[sec],
                "academic_year_id": self.year_id,
                "subjects": [
                    {"subject_id": self.subjects[s], "order": i + 1, "exclude_marks": s == "excl", "is_active": True}
                    for i, s in enumerate(subs)
                ],
            }
            mapped = admin.post("/masters/class-subject-mappings/bulk", json=body)
            assert mapped.status_code == 201, mapped.text
            for m in mapped.json()["mappings"]:
                self.mapping_ids.append(m["id"])
                self.cleanup.add(admin.delete, f"/masters/class-subject-mappings/{m['id']}")

        scheme = admin.post(
            "/grade-schemes/exam",
            json={"name": f"{self.tag}_gs1", "description": "GS1", "is_default": False, "bands": bands()},
        )
        assert scheme.status_code == 201, scheme.text
        self.scheme_id = scheme.json()["id"]
        self.cleanup.add(admin.delete, f"/grade-schemes/exam/{self.scheme_id}")

        for i in range(student_count):
            self.students.append(self.add_student(i))
        return self

    def add_student(self, i, section="a", admission_date="2026-06-10"):
        name = f"{self.tag}s{i}"
        father = f"{name}.f@example.com"
        body = {
            "admission_date": admission_date,
            "admission_number": name,
            "admission_type": "regular",
            "academic_year_id": self.year_id,
            "admitted_academic_year_id": self.year_id,
            "admitted_class_id": self.class_id,
            "admitted_section_id": self.sections[section],
            "current_class_id": self.class_id,
            "current_section_id": self.sections[section],
            "address_line1": "1 Test Road",
            "city": "Hyderabad",
            "student": {
                "first_name": name,
                "last_name": "Exm",
                "date_of_birth": "2018-03-04",
                "gender": "Male",
                "father": {"name": f"Father {name}", "email": father, "phone": "9000112233", "gender": "Male", "relation_to_student": "Father"},
                "mother": {"name": f"Mother {name}", "email": f"{name}.m@example.com", "phone": "9000112244", "gender": "Female", "relation_to_student": "Mother"},
            },
        }
        response = self.admin.post("/students/admission/", json=body)
        assert response.status_code == 201, response.text
        data = response.json()
        self.cleanup.add(self.admin.delete, f"/students/admission/{data['id']}")
        return {
            "id": data["student"]["id"],
            "admission_id": data["id"],
            "admission_number": data["admission_number"],
            "name": f"{name} Exm",
            "father_email": father,
        }

    def student_api(self, i):
        key = ("s", i)
        if key not in self._clients:
            s = self.students[i]
            data = first_login(s["admission_number"], "student@123", self.year_id)
            self._clients[key] = Api(token=data["access_token"])
        return self._clients[key]

    def parent_api(self, i):
        key = ("p", i)
        if key not in self._clients:
            s = self.students[i]
            data = first_login(s["father_email"], "parent@123", self.year_id)
            self._clients[key] = Api(token=data["access_token"])
        return self._clients[key]

    def teardown(self):
        for client in self._clients.values():
            client.close()
        self.cleanup.run()


@pytest.fixture(scope="module")
def world(admin, logins):
    w = World(admin, logins["admin"]["_academic_year_id"])
    try:
        w.build()
        yield w
    finally:
        w.teardown()


@pytest.fixture
def foreign(logins):
    client = Api(token=logins["admin"]["access_token"], tenant_header="qa_school_b")
    yield client
    client.close()


@pytest.fixture
def ex1(admin, world, cleanup):
    from api_tests.exam.helpers import create_exam, get_configs

    exam_id = create_exam(admin, cleanup, world, dates=True)
    return {"id": exam_id, "configs": get_configs(admin, exam_id)}
