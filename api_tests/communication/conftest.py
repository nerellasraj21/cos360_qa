import pytest

from api_tests.communication.helpers import (
    email_address,
    login_as,
    phone_number,
    remove_staff,
    template_body,
)
from api_tests.support import Api, unique

NOBODY = {"target_type": "role_based", "target_ref": {"role": "com_nobody_has_this_role"}}


@pytest.fixture
def make_template(admin, cleanup):
    def factory(channel="sms", body="Hello {{name}}, notice.", name=None, **extra):
        data = template_body(name or unique("com_tpl_"), channel, body, **extra)
        response = admin.post("/communication/templates", json=data)
        assert response.status_code == 201, response.text
        created = response.json()
        cleanup.add(admin.delete, f"/communication/templates/{created['id']}")
        return created

    return factory


@pytest.fixture
def make_staff(admin, cleanup):
    def factory(**overrides):
        body = {"first_name": unique("com_stf_"), "phone": phone_number(), "address": "12 MG Road"}
        body.update(overrides)
        response = admin.post("/staff/enrollment", json=body)
        assert response.status_code == 200, response.text
        data = response.json()
        cleanup.add(remove_staff, admin, data)
        data["_login"] = body.get("email") or body["phone"]
        data["_body"] = body
        return data

    return factory


@pytest.fixture
def make_parent(admin, cleanup):
    def factory(phone="auto", email="auto", **overrides):
        body = {
            "name": unique("com_par_"),
            "relation_to_student": "Father",
            "phone": phone_number() if phone == "auto" else phone,
            "email": email_address() if email == "auto" else email,
        }
        body = {k: v for k, v in body.items() if v is not None}
        body.update(overrides)
        response = admin.post("/parents/", json=body)
        assert response.status_code == 201, response.text
        data = response.json()
        cleanup.delete_later(admin, f"/parents/{data['id']}")
        return data

    return factory


@pytest.fixture
def make_role(admin, cleanup):
    def factory(grants):
        name = unique("com_role_")
        response = admin.post("/admin/role-mgmt/", json={"name": name, "description": "com api test role"})
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
        staff = make_staff(email=email_address(), role_id=role["id"], **staff_overrides)
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


@pytest.fixture(scope="session")
def failed_log(admin):
    from api_tests.communication.helpers import email_address as _email

    staff_body = {"first_name": unique("com_log_"), "phone": phone_number(), "address": "12 MG Road", "email": _email()}
    staff = admin.post("/staff/enrollment", json=staff_body)
    assert staff.status_code == 200, staff.text
    staff = staff.json()
    template = admin.post(
        "/communication/templates",
        json={"name": unique("com_bad_"), "channel": "sms", "body": "Hi {% if %}"},
    )
    assert template.status_code == 201, template.text
    template = template.json()
    sent = admin.post(
        "/communication/send",
        json={
            "template_id": template["id"],
            "target_type": "individual_staff",
            "target_ref": {"staff_id": staff["id"]},
            "variables": {},
        },
    )
    assert sent.status_code == 200 and sent.json() == {"queued_count": 0}, sent.text
    found = None
    listing = admin.get(
        "/communication/logs", params={"target_type": "individual_staff", "status": "failed", "page_size": 100}
    )
    for item in listing.json()["items"]:
        if item["recipient_name"] == staff["first_name"]:
            found = item
    assert found is not None
    yield {"log": found, "staff": staff, "template": template}
    remove_staff(admin, staff)
    admin.delete(f"/communication/templates/{template['id']}")
