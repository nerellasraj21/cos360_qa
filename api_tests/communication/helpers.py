import random
import uuid

from api_tests.support import QA_TENANT, Api, login

TEMP_PASSWORD = "Welcome@123"


def phone_number() -> str:
    return "9" + "".join(random.choice("0123456789") for _ in range(9))


def email_address() -> str:
    return f"com_{uuid.uuid4().hex[:10]}@qa.example"


def granted(logins: dict, role: str, resource: str, action: str) -> bool:
    return action in (logins[role].get("permissions") or {}).get(resource, [])


def expected_status(logins: dict, role: str, resource: str, action: str, ok: int = 200) -> int:
    return ok if granted(logins, role, resource, action) else 403


def remove_staff(api: Api, staff: dict) -> None:
    api.delete(f"/staff/enrollment/{staff['id']}")
    api.patch(f"/admin/users/{staff['user_id']}", json={"is_active": False})


def login_as(username: str, password: str = TEMP_PASSWORD) -> Api:
    data = login(username, password, QA_TENANT)
    client = Api(token=data["access_token"])
    client.login_data = data
    return client


def template_body(name: str, channel: str = "sms", body: str = "Hello {{name}}, notice.", **extra) -> dict:
    data = {"name": name, "channel": channel, "body": body}
    data.update(extra)
    return data
