import uuid
from datetime import date, timedelta

from api_tests.support import QA_B_TENANT, Api, unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]
NO_ACCESS = ["teacher", "student", "parent"]


def role_status(allowed):
    return {role: (None if role in allowed else 403) for role in ROLES}


def forbidden_roles(allowed):
    return [role for role in ROLES if role not in allowed]


def fresh_year():
    return 2100 + int(uuid.uuid4().hex[:6], 16) % 6900


class Window:
    def __init__(self):
        self.year = fresh_year()

    def day(self, month, day):
        return date(self.year, month, day).isoformat()

    @property
    def start(self):
        return date(self.year, 1, 1).isoformat()

    @property
    def end(self):
        return date(self.year, 12, 31).isoformat()

    @property
    def params(self):
        return {"start_date": self.start, "end_date": self.end}


def other_tenant_header(client):
    return Api(token=client.token, tenant_header=QA_B_TENANT)


def make_category(admin, cleanup, **over):
    body = {"name": unique("exp_cat_"), "description": "qa category"}
    body.update(over)
    response = admin.post("/expense/categories/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/expense/categories/{data['id']}")
    return data


def make_type(admin, cleanup, category_id, **over):
    body = {"name": unique("exp_typ_"), "category_id": category_id, "description": "qa type"}
    body.update(over)
    response = admin.post("/expense/types/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/expense/types/{data['id']}")
    return data


def make_department(admin, cleanup, **over):
    body = {"name": unique("exp_dep_"), "description": "qa department"}
    body.update(over)
    response = admin.post("/expense/departments/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/expense/departments/{data['id']}")
    return data


def _settle(admin, transaction_id):
    current = admin.get(f"/expense/transactions/{transaction_id}")
    if current.status_code != 200:
        return
    data = current.json()
    if data["status"] == "pending" and data["requires_approval"]:
        admin.post(
            f"/expense/transactions/{transaction_id}/approval",
            json={"action": "reject", "approval_comment": "qa cleanup"},
        )


def txn_body(type_id, amount="500.00", txn_date=None, **over):
    body = {
        "expense_type_id": type_id,
        "amount": amount,
        "transaction_date": txn_date or date.today().isoformat(),
        "description": "qa expense",
        "payment_method": "cash",
        "vendor_name": "qa vendor",
        "idempotency_key": unique("exp_idem_"),
    }
    body.update(over)
    return body


def make_txn(admin, cleanup, type_id, amount="500.00", txn_date=None, **over):
    response = admin.post("/expense/transactions/", json=txn_body(type_id, amount, txn_date, **over))
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.add(_settle, admin, data["id"])
    return data


def approve_body(action="approve", comment="qa comment"):
    return {"action": action, "approval_comment": comment}


def tiny_file(name="qa.txt", size=1024):
    return {"file": (name, b"x" * size, "text/plain")}


def yesterday():
    return (date.today() - timedelta(days=1)).isoformat()
