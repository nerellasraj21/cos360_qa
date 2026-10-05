import uuid

import pytest

from api_tests.support import Api, login, unique

ADMIN_PASSWORD = "Adm1n#Pass9"
EDGE_ADMIN_PASSWORD = "abc"
TENANT_CAP = 3

_registry: dict = {}
_plans: list = []


def full_plan_id(superadmin) -> str:
    plans = superadmin.get("/super_admin/plans/").json()["plans"]
    return next(p["id"] for p in plans if p["name"] == "Full")


def tmp_tenant_rows(superadmin) -> list:
    rows = superadmin.get("/super_admin/system/tenants/?limit=500").json()["tenants"]
    return [r for r in rows if r["client_name"].startswith("qa_tmp_")]


def tenant_users(superadmin, tenant_id: str) -> list:
    response = superadmin.get(f"/super_admin/tenant-data/{tenant_id}/users/?limit=500")
    assert response.status_code == 200, response.text
    return response.json()["users"]


class TmpTenant:
    def __init__(self, superadmin, client_name, tenant_id, plan_id, response, admin_username, admin_password):
        self.superadmin = superadmin
        self.client_name = client_name
        self.tenant_id = tenant_id
        self.plan_id = plan_id
        self.response = response
        self.created = response.json().get("tenant", {}) if response is not None else {}
        self.admin_username = admin_username
        self.admin_password = admin_password
        self._admin = None
        self.year_id = None

    @property
    def fresh(self) -> bool:
        return self.response is not None

    def admin_login(self) -> dict:
        data = login(self.admin_username, self.admin_password, self.client_name)
        self.year_id = data["_academic_year_id"]
        return data

    @property
    def admin(self) -> Api:
        if self._admin is None:
            data = self.admin_login()
            self._admin = Api(token=data["access_token"])
        return self._admin

    def anon(self) -> Api:
        return Api(tenant_header=self.client_name)

    def set_active(self, active: bool) -> None:
        row = next(t for t in tmp_tenant_rows(self.superadmin) if t["id"] == self.tenant_id)
        if row["is_active"] != active:
            response = self.superadmin.put(f"/super_admin/system/tenants/{self.tenant_id}/activate")
            assert response.status_code == 200, response.text

    def retire(self) -> None:
        if self._admin is not None:
            self._admin.close()


def new_name(prefix: str = "qa_tmp_", length: int | None = None) -> str:
    base = prefix + uuid.uuid4().hex[:10]
    if length and len(base) < length:
        base = base + "x" * (length - len(base))
    return base


def _reuse_or_none(superadmin, predicate):
    for row in tmp_tenant_rows(superadmin):
        users = tenant_users(superadmin, row["id"])
        if predicate(row, users):
            return row, users
    return None, None


def _activate(superadmin, row):
    if not row["is_active"]:
        response = superadmin.put(f"/super_admin/system/tenants/{row['id']}/activate")
        assert response.status_code == 200, response.text


def _create(superadmin, name, plan, body):
    kwargs = {"params": {"client_name": name, "plan_id": plan}}
    if body is not None:
        kwargs["json"] = body
    response = superadmin.post("/super_admin/system/tenants/", **kwargs)
    assert response.status_code == 201, response.text
    return response


def _capped(superadmin) -> bool:
    return len(tmp_tenant_rows(superadmin)) >= TENANT_CAP


def main_tenant(superadmin) -> TmpTenant:
    if "main" in _registry:
        return _registry["main"]
    plan = full_plan_id(superadmin)
    row, users = _reuse_or_none(
        superadmin,
        lambda r, u: len(r["client_name"]) != 63 and any(x["username"].startswith("tmpadm_") for x in u),
    )
    if row is not None:
        _activate(superadmin, row)
        username = next(x["username"] for x in users if x["username"].startswith("tmpadm_"))
        tenant = TmpTenant(superadmin, row["client_name"], row["id"], plan, None, username, ADMIN_PASSWORD)
    else:
        if _capped(superadmin):
            pytest.skip("tenant cap of 3 qa_tmp tenants reached and none has a known admin")
        name = new_name()
        username = unique("tmpadm_")
        response = _create(
            superadmin, name, plan, {"username": username, "email": f"{username}@example.com", "password": ADMIN_PASSWORD}
        )
        tenant = TmpTenant(
            superadmin, name, response.json()["tenant"]["tenant_id"], plan, response, username, ADMIN_PASSWORD
        )
    _registry["main"] = tenant
    return tenant


def edge_tenant(superadmin) -> TmpTenant:
    if "edge" in _registry:
        return _registry["edge"]
    plan = full_plan_id(superadmin)
    row, users = _reuse_or_none(superadmin, lambda r, u: len(r["client_name"]) == 63)
    if row is not None:
        _activate(superadmin, row)
        username = users[0]["username"] if users else ""
        tenant = TmpTenant(superadmin, row["client_name"], row["id"], plan, None, username, EDGE_ADMIN_PASSWORD)
    else:
        if _capped(superadmin):
            pytest.skip("tenant cap of 3 qa_tmp tenants reached")
        name = "  " + new_name(prefix="QA_TMP_", length=63).upper() + " "
        username = unique("edgeadm_")
        response = _create(superadmin, name, plan, {"username": username, "email": "not-an-email", "password": "abc"})
        tenant = TmpTenant(
            superadmin,
            name.strip().lower(),
            response.json()["tenant"]["tenant_id"],
            plan,
            response,
            username,
            EDGE_ADMIN_PASSWORD,
        )
    _registry["edge"] = tenant
    return tenant


def empty_tenant(superadmin) -> TmpTenant:
    if "empty" in _registry:
        return _registry["empty"]
    plan = full_plan_id(superadmin)
    row, users = _reuse_or_none(superadmin, lambda r, u: len(r["client_name"]) != 63 and len(u) == 0)
    if row is not None:
        _activate(superadmin, row)
        tenant = TmpTenant(superadmin, row["client_name"], row["id"], plan, None, "", "")
    else:
        if _capped(superadmin):
            pytest.skip("tenant cap of 3 qa_tmp tenants reached")
        name = new_name()
        response = _create(superadmin, name, plan, {"username": "", "email": "", "password": ""})
        tenant = TmpTenant(superadmin, name, response.json()["tenant"]["tenant_id"], plan, response, "", "")
    _registry["empty"] = tenant
    return tenant


def make_plan(superadmin, resources: dict | None = None, name: str | None = None) -> dict:
    name = name or new_name()
    response = superadmin.post("/super_admin/plans/", params={"name": name, "description": "qa tmp plan"})
    assert response.status_code == 201, response.text
    plan_id = response.json()["plan"]["id"]
    _plans.append((superadmin, plan_id))
    for resource, actions in (resources or {}).items():
        for action in actions:
            added = superadmin.post(
                f"/super_admin/plans/{plan_id}/resources", params={"resource_name": resource, "action_name": action}
            )
            assert added.status_code == 201, added.text
    return {"id": plan_id, "name": name}


def retire_all() -> None:
    for tenant in list(_registry.values()):
        tenant.retire()
    _registry.clear()
    for superadmin, plan_id in _plans:
        try:
            superadmin.put(f"/super_admin/plans/{plan_id}", params={"is_active": "false"})
        except Exception:
            pass
    _plans.clear()
