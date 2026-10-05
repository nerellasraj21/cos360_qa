import pytest

from api_tests.staff.helpers import (
    login_as,
    login_name,
    remove_staff,
    staff_payload,
)
from api_tests.support import Api, unique


@pytest.fixture
def make_staff(admin, cleanup):
    def factory(**overrides):
        body = staff_payload(**overrides)
        response = admin.post("/staff/enrollment", json=body)
        assert response.status_code == 200, response.text
        data = response.json()
        cleanup.add(remove_staff, admin, data)
        data["_login"] = login_name(body)
        data["_body"] = body
        return data

    return factory


@pytest.fixture
def make_designation(admin, cleanup):
    def factory(title=None):
        title = title or unique("stf_des_")
        response = admin.post("/staff/designations/", json={"title": title})
        assert response.status_code == 201, response.text
        data = response.json()
        cleanup.delete_later(admin, f"/staff/designations/{data['id']}")
        return data

    return factory


@pytest.fixture
def get_or_create_designation(admin, cleanup):
    def factory(title):
        response = admin.post("/staff/designations/", json={"title": title})
        if response.status_code == 201:
            data = response.json()
            cleanup.delete_later(admin, f"/staff/designations/{data['id']}")
            return data
        for item in admin.get("/staff/designations-legacy").json():
            if item["title"] == title:
                return item
        raise AssertionError(response.text)

    return factory


@pytest.fixture
def make_role(admin, cleanup):
    def factory(grants):
        name = unique("stf_role_")
        response = admin.post("/admin/role-mgmt/", json={"name": name, "description": "stf api test role"})
        assert response.status_code == 201, response.text
        role_id = response.json()["role"]["id"]
        cleanup.delete_later(admin, f"/admin/role-mgmt/{role_id}")
        for resource, action in grants:
            granted = admin.put(
                f"/admin/role-mgmt/roles/{role_id}/permissions",
                params={"resource": resource, "action": action, "is_granted": "true"},
            )
            assert granted.status_code == 200, granted.text
        return {"id": role_id, "name": name}

    return factory


@pytest.fixture
def role_client(admin, cleanup, logins, make_role, make_staff):
    staff_role_id = logins["staff"]["role"]["id"]

    def factory(grants, **staff_overrides):
        role = make_role(grants)
        email = staff_overrides.pop("email", None) or staff_payload()["first_name"] + "@qa.example"
        staff = make_staff(email=email, role_id=role["id"], **staff_overrides)
        cleanup.add(admin.put, f"/admin/users/{staff['user_id']}/role", json={"role_id": staff_role_id})
        client = login_as(staff["_login"])
        cleanup.add(client.close)
        client.staff = staff
        client.role = role
        return client

    return factory


@pytest.fixture
def b_header_client(admin):
    client = Api(token=admin.token, tenant_header="qa_school_b")
    yield client
    client.close()
