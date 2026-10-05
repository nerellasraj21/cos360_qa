import os
import random
import time

from jose import jwt

from api_tests.support import QA_TENANT, Api, unique

TEMP_STAFF_PASSWORD = "Welcome@123"
TEMP_STUDENT_PASSWORD = "student@123"
TEMP_PARENT_PASSWORD = "parent@123"
STRONG_PASSWORD = "Str0ng#Pass26"

PERMISSION_DENIED_PREFIX = "Permission not found in database"
MISSING_AUTH = "Authorization header missing or invalid"


def claims_of(token: str) -> dict:
    return jwt.get_unverified_claims(token)


def mint(payload: dict, token_type: str = "access", expires_in: int = 3600, secret: str | None = None) -> str:
    data = dict(payload)
    data["exp"] = int(time.time()) + expires_in
    data["token_type"] = token_type
    return jwt.encode(
        data, secret or os.environ["JWT_SECRET_KEY"], algorithm=os.environ.get("JWT_ALGORITHM", "HS256")
    )


def detail_text(response) -> str:
    try:
        body = response.json()
    except Exception:
        return response.text
    detail = body.get("detail", body) if isinstance(body, dict) else body
    return detail if isinstance(detail, str) else str(detail)


def rand_phone() -> str:
    return "9" + "".join(random.choice("0123456789") for _ in range(9))


def post_login(client: Api, username: str, password: str, year_id: str, **extra):
    body = {"username": username, "password": password, "academic_year_id": year_id}
    body.update(extra)
    return client.post("/auth/login", json=body)


def fresh_login(username: str, password: str, year_id: str, tenant: str = QA_TENANT, **extra):
    anon = Api(tenant_header=tenant)
    try:
        return post_login(anon, username, password, year_id, **extra)
    finally:
        anon.close()


def set_password(token: str, new_password: str, confirm: str | None = None, tenant: str = QA_TENANT):
    anon = Api(tenant_header=tenant)
    try:
        return anon.post(
            "/auth/staff/set-password",
            json={
                "change_password_token": token,
                "new_password": new_password,
                "confirm_password": confirm if confirm is not None else new_password,
            },
        )
    finally:
        anon.close()


def role_id_map(admin) -> dict:
    roles = admin.get("/admin/role-mgmt/roles/").json()["roles"]
    return {r["name"]: r["id"] for r in roles}


class TmpUser:
    def __init__(self, admin, year_id, user_id, staff_id, username, password, role_name):
        self.admin = admin
        self.year_id = year_id
        self.user_id = user_id
        self.staff_id = staff_id
        self.username = username
        self.password = password
        self.role_name = role_name
        self.email = username
        self.phone = None

    def login_response(self, password: str | None = None):
        return fresh_login(self.username, password or self.password, self.year_id)

    def challenge(self) -> str:
        body = self.login_response().json()
        assert body.get("requires_password_change") is True, body
        return body["change_password_token"]

    def activate(self, new_password: str = STRONG_PASSWORD) -> dict:
        body = self.login_response().json()
        if body.get("requires_password_change"):
            done = set_password(body["change_password_token"], new_password)
            assert done.status_code == 200, done.text
            self.password = new_password
            return done.json()
        return body

    def login_data(self) -> dict:
        response = self.login_response()
        assert response.status_code == 200, response.text
        data = response.json()
        if data.get("requires_password_change"):
            return self.activate()
        return data

    def client(self) -> Api:
        return Api(token=self.login_data()["access_token"])

    def deactivate(self):
        self.admin.patch(f"/admin/users/{self.user_id}", json={"is_active": False})


def create_staff_user(admin, cleanup, year_id: str, role_name: str = "Staff", role_id: str | None = None) -> TmpUser:
    system_roles = role_id_map(admin)
    custom_role_used = role_id is not None and role_id not in system_roles.values()
    if role_id is None:
        role_id = system_roles[role_name]
    tag = unique("auth_")
    email = f"{tag}@example.com"
    phone = rand_phone()
    response = admin.post(
        "/staff/enrollment",
        json={
            "first_name": f"Auth{tag}",
            "last_name": "Tmp",
            "email": email,
            "phone": phone,
            "address": "QA lane",
            "role_id": role_id,
        },
    )
    assert response.status_code in (200, 201), response.text
    data = response.json()
    user = TmpUser(admin, year_id, data["user_id"], data["id"], email, TEMP_STAFF_PASSWORD, role_name)
    user.phone = phone
    cleanup.add(user.deactivate)
    cleanup.add(admin.delete, f"/staff/enrollment/{data['id']}")
    if custom_role_used:
        cleanup.add(admin.put, f"/admin/users/{data['user_id']}/role", json={"role_id": system_roles["Staff"]})
    return user


class Family:
    def __init__(self, admin, year_id, tag, admission_id, student_id, class_id, admission_number, father_email):
        self.admin = admin
        self.year_id = year_id
        self.tag = tag
        self.admission_id = admission_id
        self.student_id = student_id
        self.class_id = class_id
        self.admission_number = admission_number
        self.father_email = father_email
        self.mother_username = f"{admission_number}.mother"

    def student_login(self) -> dict:
        return activate_account(self.admission_number, TEMP_STUDENT_PASSWORD, self.year_id)

    def father_login(self) -> dict:
        return activate_account(self.father_email, TEMP_PARENT_PASSWORD, self.year_id)

    def mother_login(self) -> dict:
        return activate_account(self.mother_username, TEMP_PARENT_PASSWORD, self.year_id)


def create_class(admin, cleanup, year_id: str) -> str:
    tag = unique("auth_")
    made = admin.post(
        "/masters/class_sections/",
        json={"name": tag, "short_code": tag[:10], "academic_year_id": year_id, "sections": [{"name": "A"}]},
    )
    assert made.status_code == 201, made.text
    class_id = made.json()["id"]
    cleanup.add(admin.delete, f"/masters/class_sections/{class_id}")
    return class_id


def first_section(admin, class_id: str) -> str:
    sections = admin.get(f"/masters/class_sections/by_class_id/{class_id}/sections")
    assert sections.status_code == 200, sections.text
    return sections.json()[0]["id"]


def create_family(
    admin, cleanup, year_id: str, class_id: str | None = None, father_email: str | None = None
) -> Family:
    tag = unique("auth_")
    if class_id is None:
        class_id = create_class(admin, cleanup, year_id)
    admission_number = f"A{tag}"
    father_email = father_email or f"{tag}.dad@example.com"
    body = {
        "academic_year_id": year_id,
        "admitted_class_id": class_id,
        "current_class_id": class_id,
        "current_section_id": first_section(admin, class_id),
        "address_line1": "QA street",
        "admission_number": admission_number,
        "student": {
            "first_name": f"Kid{tag}",
            "last_name": "Tmp",
            "date_of_birth": "2015-01-01",
            "gender": "Male",
            "father": {
                "name": f"Dad {tag}",
                "phone": rand_phone(),
                "email": father_email,
                "relation_to_student": "Father",
            },
            "mother": {"name": f"Mom {tag}", "phone": rand_phone(), "relation_to_student": "Mother"},
        },
    }
    response = admin.post("/students/admission/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.add(admin.delete, f"/students/admission/{data['id']}")
    return Family(admin, year_id, tag, data["id"], data["student"]["id"], class_id, admission_number, father_email)


def activate_account(username: str, password: str, year_id: str, new_password: str = STRONG_PASSWORD) -> dict:
    response = fresh_login(username, password, year_id)
    assert response.status_code == 200, response.text
    body = response.json()
    if body.get("requires_password_change"):
        done = set_password(body["change_password_token"], new_password)
        assert done.status_code == 200, done.text
        return done.json()
    return body


def grant_permission(admin, cleanup, role_id: str, resource: str, action: str, granted: bool = True) -> None:
    flag = "true" if granted else "false"
    response = admin.put(
        f"/admin/role-mgmt/roles/{role_id}/permissions",
        params={"resource": resource, "action": action, "is_granted": flag},
    )
    assert response.status_code == 200, response.text
    old_value = response.json()["permission"].get("old_value")
    if old_value is None:
        cleanup.add(delete_permission_row, admin, role_id, resource, action)
    else:
        cleanup.add(
            admin.put,
            f"/admin/role-mgmt/roles/{role_id}/permissions",
            params={"resource": resource, "action": action, "is_granted": "true" if old_value else "false"},
        )


def delete_permission_row(admin, role_id: str, resource: str, action: str) -> None:
    rows = admin.get(f"/auth/resource-permissions/role/{role_id}").json()
    for row in rows:
        if row["resource"] == resource and row["action"] == action:
            admin.delete(f"/auth/resource-permissions/{row['id']}")
            return
