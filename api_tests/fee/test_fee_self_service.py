import uuid
from datetime import date

import pytest

from api_tests.fee import helpers as h
from api_tests.support import QA_TENANT, Api, Cleanup, items_of, unique

pytestmark = pytest.mark.api
C = "/fee/collection"
T = "/fee/transactions"
R = "/fee/receipts"

STUDENT_GRANTS = [("fee_receipts", "read_own"), ("fee_receipts", "list_own"), ("fee_transactions", "read_own"), ("fee_transactions", "list_own")]
PARENT_GRANTS = [("fee_transactions", "read_related"), ("fee_receipts", "read_related"), ("fee_collection", "read_related")]


def rid():
    return str(uuid.uuid4())


def set_grant(admin, role_id, resource, action, granted):
    r = admin.put(
        f"/admin/role-mgmt/roles/{role_id}/permissions",
        params={"resource": resource, "action": action, "is_granted": "true" if granted else "false"},
    )
    assert r.status_code == 200, r.text
    return r.json()["permission"]["old_value"]


def role_ids(admin):
    data = h.ok(admin.get("/admin/role-mgmt/roles/")).json()
    items = data["roles"] if isinstance(data, dict) else data
    return {r["name"]: r["id"] for r in items}


def login_new_user(username, default_password, year_id):
    anon = Api(tenant_header=QA_TENANT)
    try:
        first = h.ok(anon.post("/auth/login", json={"username": username, "password": default_password, "academic_year_id": year_id}))
        data = first.json()
        if data.get("requires_password_change"):
            new_password = "Fee@" + unique("pw")
            done = h.ok(
                anon.post(
                    "/auth/staff/set-password",
                    json={"change_password_token": data["change_password_token"], "new_password": new_password, "confirm_password": new_password},
                )
            )
            data = done.json()
        return Api(token=data["access_token"]), data
    finally:
        anon.close()


@pytest.fixture(scope="module")
def world(admin, year_id, fee_world):
    stack = Cleanup()
    t = fee_world["tuition"]["id"]
    cls = fee_world["class"]
    s1 = h.make_student(admin, stack, year_id, cls)
    s1b = h.make_student(admin, stack, year_id, cls, sibling_of=s1)
    s2 = h.make_student(admin, stack, year_id, cls)
    for s in (s1, s1b, s2):
        h.map_student(admin, stack, year_id, s, t, "12000.00")
    p1a = h.ok(h.pay(admin, s1, year_id, "1000.00", [(t, "1000.00")])).json()
    p1b = h.ok(h.pay(admin, s1, year_id, "2000.00", [(t, "2000.00")])).json()
    c1 = h.ok(
        h.pay(admin, s1, year_id, "500.00", [(t, "500.00")], method="cheque", cheque_number="CHQ-S", cheque_bank="Test Bank", cheque_date=date.today().isoformat())
    ).json()
    p1c = h.ok(h.pay(admin, s1b, year_id, "1500.00", [(t, "1500.00")])).json()
    p2 = h.ok(h.pay(admin, s2, year_id, "3000.00", [(t, "3000.00")])).json()
    student1, _ = login_new_user(s1["admission_number"], "student@123", year_id)
    student2, _ = login_new_user(s2["admission_number"], "student@123", year_id)
    parent1, _ = login_new_user(s1["father_email"], "parent@123", year_id)
    parent2, _ = login_new_user(s2["father_email"], "parent@123", year_id)
    yield {
        "s1": s1, "s1b": s1b, "s2": s2, "tuition": fee_world["tuition"], "p1a": p1a, "p1b": p1b, "c1": c1, "p1c": p1c, "p2": p2,
        "student1": student1, "student2": student2, "parent1": parent1, "parent2": parent2,
    }
    for client in (student1, student2, parent1, parent2):
        client.close()
    stack.run()


@pytest.mark.tc("TC-FEE-16-A01")
def test_student_my_fees(world):
    data = h.ok(world["student1"].get(f"{T}/my-fees")).json()
    assert set(data) >= {"items", "student_id", "total_count", "has_next", "access_scope", "user_role"}
    assert data["access_scope"] == "own" and data["student_id"] == world["s1"]["id"]
    assert data["total_count"] == 3 and len(data["items"]) == 3
    ids = [i["id"] for i in data["items"]]
    assert set(ids) == {world["p1a"]["transaction_id"], world["p1b"]["transaction_id"], world["c1"]["transaction_id"]}
    created = [i["created_at"] for i in data["items"]]
    assert created == sorted(created, reverse=True)
    assert {i["status"] for i in data["items"]} == {"completed", "pending"}
    assert all(i["student_id"] == world["s1"]["id"] for i in data["items"])


@pytest.mark.tc("TC-FEE-16-A02")
def test_student_my_fees_pagination(world):
    data = h.ok(world["student1"].get(f"{T}/my-fees", params={"limit": 1, "skip": 1})).json()
    assert len(data["items"]) == 1 and data["total_count"] == 3 and data["has_next"] is True
    last = h.ok(world["student1"].get(f"{T}/my-fees", params={"limit": 1, "skip": 2})).json()
    assert last["has_next"] is False


@pytest.mark.tc("TC-FEE-16-A03")
def test_student_my_fees_limit_bound(world):
    assert world["student1"].get(f"{T}/my-fees", params={"limit": 101}).status_code == 422
    assert world["student1"].get(f"{T}/my-fees", params={"limit": 0}).status_code == 422
    assert world["student1"].get(f"{T}/my-fees", params={"skip": -1}).status_code == 422


@pytest.mark.tc("TC-FEE-16-A04")
def test_parent_children_fees(world):
    data = h.ok(world["parent1"].get(f"{T}/my-children-fees")).json()
    assert data["access_scope"] == "related"
    ids = {i["id"] for i in data["items"]}
    assert ids == {world["p1a"]["transaction_id"], world["p1b"]["transaction_id"], world["c1"]["transaction_id"], world["p1c"]["transaction_id"]}
    assert data["total_count"] == 4
    assert {i["student_id"] for i in data["items"]} == {world["s1"]["id"], world["s1b"]["id"]}


@pytest.mark.tc("TC-FEE-16-A05")
def test_parent_children_fees_filters(world, year_id):
    data = h.ok(world["parent1"].get(f"{T}/my-children-fees", params={"transaction_status": "completed", "academic_year_id": year_id})).json()
    assert data["total_count"] == 3 and all(i["status"] == "completed" for i in data["items"])
    applied = data["filters_applied"]
    assert applied["transaction_status"] == "completed"
    assert str(applied["academic_year_id"]) == year_id


@pytest.mark.tc("TC-FEE-16-A06")
def test_wrong_role_for_fee_lists(world):
    assert world["student1"].get(f"{T}/my-children-fees").status_code == 403
    assert world["parent1"].get(f"{T}/my-fees").status_code == 403


@pytest.mark.tc("TC-FEE-16-A07")
def test_admin_has_no_own_scope(admin):
    assert admin.get(f"{T}/my-fees").status_code == 403
    assert admin.get(f"{R}/my-receipts").status_code == 403


@pytest.mark.tc("TC-FEE-16-A08")
def test_student_my_outstanding_fees(world):
    data = h.ok(world["student1"].get(f"{T}/my-outstanding-fees")).json()
    assert data["student_id"] == world["s1"]["id"]
    assert data["student_admission_num"] == world["s1"]["admission_number"]
    assert data["total_outstanding"] == "9000.00"
    assert sorted(h.D(i["outstanding_amount"]) for i in data["outstanding_items"]) == [3000, 3000, 3000]


@pytest.mark.tc("TC-FEE-16-A09")
def test_parent_child_outstanding_fees(world):
    r = h.ok(world["parent1"].get(f"{T}/child-outstanding-fees/{world['s1']['id']}"))
    assert r.json()["student_id"] == world["s1"]["id"] and r.json()["total_outstanding"] == "9000.00"
    assert world["parent1"].get(f"{T}/child-outstanding-fees/{world['s2']['id']}").status_code == 404


@pytest.mark.tc("TC-FEE-16-A09")
def test_parent_child_outstanding_fees_unrelated(world):
    assert world["parent1"].get(f"{T}/child-outstanding-fees/{world['s2']['id']}").status_code == 404


@pytest.mark.tc("TC-FEE-16-A10")
def test_student_my_receipts(world):
    rows = h.ok(world["student1"].get(f"{R}/my-receipts")).json()
    assert [r["id"] for r in rows] == [world["p1b"]["receipt_id"], world["p1a"]["receipt_id"]]
    assert world["p2"]["receipt_id"] not in {r["id"] for r in rows}
    page = h.ok(world["student1"].get(f"{R}/my-receipts", params={"limit": 1, "offset": 1})).json()
    assert [r["id"] for r in page] == [world["p1a"]["receipt_id"]]


@pytest.mark.tc("TC-FEE-16-A11")
def test_parent_children_receipts(world):
    rows = h.ok(world["parent1"].get(f"{R}/my-children-receipts")).json()
    assert {r["id"] for r in rows} == {world["p1a"]["receipt_id"], world["p1b"]["receipt_id"], world["p1c"]["receipt_id"]}
    assert world["p2"]["receipt_id"] not in {r["id"] for r in rows}


@pytest.mark.tc("TC-FEE-16-A12")
def test_wrong_role_for_receipt_lists(world):
    assert world["parent1"].get(f"{R}/my-receipts").status_code == 403
    assert world["student1"].get(f"{R}/my-children-receipts").status_code == 403


@pytest.mark.tc("TC-FEE-16-A13")
def test_parent_without_children(parent):
    for path in (f"{R}/my-children-receipts", f"{T}/my-children-fees"):
        r = parent.get(path)
        assert r.status_code in (400, 403)
        if r.status_code == 400:
            assert "Only parents with children can access this endpoint" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-16-A14")
def test_student_my_summary_denied_by_default_seed(world, year_id):
    r = world["student1"].get(f"{C}/my-summary", params={"academic_year_id": year_id})
    assert r.status_code == 403
    assert world["student1"].get(f"{C}/my-history", params={"academic_year_id": year_id}).status_code == 403


@pytest.mark.tc("TC-FEE-16-A14")
@pytest.mark.skip(reason="needs a temporary fee_collection:read grant on the shared Student role, which would race with other workers and is not permitted in the QA tenant")
def test_student_my_summary_with_grant():
    pass


@pytest.mark.tc("TC-FEE-16-A15")
def test_student_my_summary_requires_year(world):
    assert world["student1"].get(f"{C}/my-summary").status_code == 422


@pytest.mark.tc("TC-FEE-16-A16")
def test_admin_my_summary(admin, year_id):
    r = admin.get(f"{C}/my-summary", params={"academic_year_id": year_id})
    assert r.status_code == 400
    assert "Only students can access this endpoint" in h.detail_text(r)


@pytest.mark.tc("TC-FEE-16-A17")
def test_parent_child_summary(admin, world, year_id):
    mine = h.ok(world["parent1"].get(f"{C}/child-summary/{world['s1']['id']}", params={"academic_year_id": year_id})).json()
    assert mine == h.ok(h.summary(admin, world["s1"], year_id)).json()
    sibling = h.ok(world["parent1"].get(f"{C}/child-summary/{world['s1b']['id']}", params={"academic_year_id": year_id})).json()
    assert sibling["grand_total_paid"] == "1500.00"


@pytest.mark.tc("TC-FEE-16-A18")
def test_parent_child_summary_unrelated(world, year_id):
    r = world["parent1"].get(f"{C}/child-summary/{world['s2']['id']}", params={"academic_year_id": year_id})
    assert r.status_code == 404


@pytest.mark.tc("TC-FEE-16-A19")
def test_student_child_summary_denied(world, year_id):
    r = world["student1"].get(f"{C}/child-summary/{world['s1']['id']}", params={"academic_year_id": year_id})
    assert r.status_code in (400, 403)


@pytest.mark.tc("TC-FEE-16-A20")
def test_parent_child_history(world, year_id):
    hist = h.ok(world["parent1"].get(f"{C}/child-history/{world['s1']['id']}", params={"academic_year_id": year_id})).json()
    assert {i["transaction_id"] for i in hist["items"]} == {world["p1a"]["transaction_id"], world["p1b"]["transaction_id"]}
    assert hist["total_paid"] == "3000.00"


@pytest.mark.tc("TC-FEE-11-A25")
@pytest.mark.tc("TC-FEE-16-A21")
def test_student_receipt_pdf(world):
    r = h.ok(world["student1"].get(f"{C}/receipts/{world['p1a']['receipt_id']}/pdf"))
    assert r.headers["content-type"].startswith("application/pdf") and r.content.startswith(b"%PDF")
    other = world["student1"].get(f"{C}/receipts/{world['p2']['receipt_id']}/pdf")
    assert other.status_code == 404
    assert "Receipt not found" in h.detail_text(other)


@pytest.mark.tc("TC-FEE-11-A26")
@pytest.mark.tc("TC-FEE-16-A22")
def test_parent_receipt_pdf(world):
    for key in ("p1a", "p1c"):
        r = h.ok(world["parent1"].get(f"{C}/receipts/{world[key]['receipt_id']}/pdf"))
        assert r.content.startswith(b"%PDF")
    other = world["parent1"].get(f"{C}/receipts/{world['p2']['receipt_id']}/pdf")
    assert other.status_code == 404
    assert "Receipt not found" in h.detail_text(other)


@pytest.mark.tc("TC-FEE-16-A23")
def test_cross_family_child_endpoints(world, year_id):
    p1, other = world["parent1"], world["s2"]["id"]
    params = {"academic_year_id": year_id, "as_of_date": "2026-10-02"}
    assert p1.get(f"{C}/child-summary/{other}", params=params).status_code == 404
    assert p1.get(f"{C}/child-history/{other}", params={"academic_year_id": year_id}).status_code == 404
    assert p1.get(f"{T}/child-outstanding-fees/{other}").status_code == 404
    assert world["parent2"].get(f"{C}/child-summary/{world['s1']['id']}", params=params).status_code == 404
    mine = h.ok(world["parent2"].get(f"{T}/my-children-fees")).json()
    assert {i["student_id"] for i in mine["items"]} == {other}


@pytest.mark.tc("TC-FEE-16-A24")
def test_self_service_header_mismatch_and_own_data_only(world, tenant_b_name):
    own = Api(token=world["student1"].token, tenant_header=tenant_b_name)
    try:
        assert own.get(f"{T}/my-fees").status_code == 403
    finally:
        own.close()
    data = h.ok(world["student2"].get(f"{T}/my-fees")).json()
    assert {i["id"] for i in data["items"]} == {world["p2"]["transaction_id"]}


def all_self_paths(world, year_id):
    s1 = world["s1"]["id"]
    return [
        ("GET", f"{T}/my-fees", {}),
        ("GET", f"{T}/my-children-fees", {}),
        ("GET", f"{T}/my-outstanding-fees", {}),
        ("GET", f"{T}/child-outstanding-fees/{s1}", {}),
        ("GET", f"{R}/my-receipts", {}),
        ("GET", f"{R}/my-children-receipts", {}),
        ("GET", f"{C}/my-summary", {"academic_year_id": year_id}),
        ("GET", f"{C}/my-history", {"academic_year_id": year_id}),
        ("GET", f"{C}/child-summary/{s1}", {"academic_year_id": year_id}),
        ("GET", f"{C}/child-history/{s1}", {"academic_year_id": year_id}),
        ("GET", f"{C}/receipts/{world['p1a']['receipt_id']}/pdf", {}),
    ]


@pytest.mark.tc("TC-FEE-16-A25")
def test_self_service_without_token(anon, world, year_id):
    for method, path, params in all_self_paths(world, year_id):
        assert anon.request(method, path, params=params).status_code == 401, path


@pytest.mark.tc("TC-FEE-16-A26")
def test_self_service_teacher_denied(teacher, world, year_id):
    for method, path, params in all_self_paths(world, year_id):
        assert teacher.request(method, path, params=params).status_code == 403, path
