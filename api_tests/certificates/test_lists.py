import pytest

from api_tests.certificates import helpers as c
from api_tests.support import Cleanup, unique


class Data:
    pass


@pytest.fixture(scope="module")
def lst(admin, cfam):
    stack = Cleanup()
    data = Data()
    data.fam = cfam
    created = admin.post("/certificates/types/", json={"name": unique("cer_t")})
    assert created.status_code == 201
    data.type = created.json()
    stack.delete_later(admin, f"/certificates/types/{data.type['id']}")
    sid = cfam.s1.student_id
    data.r1 = c.received(admin, stack, sid, data.type["id"], remarks="first")
    data.r2 = c.received(admin, stack, sid, data.type["id"], remarks="second")
    data.i1 = c.issued(admin, stack, sid, data.type["id"], issue_date="2026-10-02")
    data.s2_r = c.received(admin, stack, cfam.s2.student_id, data.type["id"])
    data.s1_ids = {data.r1["id"], data.r2["id"], data.i1["id"]}
    yield data
    stack.run()


def listing(client, path, **params):
    response = client.get(path, params=params)
    return response


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A01")
def test_by_student_lists_everything(admin, lst):
    response = listing(admin, f"{c.CERT}/by-student/{lst.fam.s1.student_id}")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "has_next"}
    assert body["total"] == 3 and body["has_next"] is False
    assert {i["id"] for i in body["items"]} == lst.s1_ids
    assert all(i["certificate_category"] is None for i in body["items"])
    stamps = [i["created_at"] for i in body["items"]]
    assert stamps == sorted(stamps, reverse=True)


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A02")
def test_received_and_issued_lists_are_unfiltered(admin, lst):
    for suffix in ("received", "issued"):
        response = listing(admin, f"{c.CERT}/{suffix}", student_id=lst.fam.s1.student_id)
        assert response.status_code == 200
        assert {i["id"] for i in response.json()["items"]} == lst.s1_ids


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A03")
def test_plain_list_filters(admin, lst):
    by_student = listing(admin, f"{c.CERT}/", student_id=lst.fam.s2.student_id)
    assert [i["id"] for i in by_student.json()["items"]] == [lst.s2_r["id"]]
    by_type = listing(admin, f"{c.CERT}/", certificate_type_id=lst.type["id"], limit=100)
    assert {i["id"] for i in by_type.json()["items"]} == lst.s1_ids | {lst.s2_r["id"]}
    both = listing(admin, f"{c.CERT}/", student_id=lst.fam.s1.student_id, certificate_type_id=lst.type["id"])
    assert {i["id"] for i in both.json()["items"]} == lst.s1_ids


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A04")
def test_pagination(admin, lst):
    sid = lst.fam.s1.student_id
    first = listing(admin, f"{c.CERT}/by-student/{sid}", limit=2, skip=0).json()
    second = listing(admin, f"{c.CERT}/by-student/{sid}", limit=2, skip=2).json()
    assert len(first["items"]) == 2 and first["has_next"] is True and first["total"] == 3
    assert len(second["items"]) == 1 and second["has_next"] is False
    assert {i["id"] for i in first["items"] + second["items"]} == lst.s1_ids


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A05")
def test_unvalidated_paging_bounds(admin, lst):
    negative = listing(admin, f"{c.CERT}/by-student/{lst.fam.s1.student_id}", skip=-1)
    assert negative.status_code == 500
    assert negative.json()["detail"].startswith("Error listing certificates")
    zero = listing(admin, f"{c.CERT}/by-student/{lst.fam.s1.student_id}", limit=0)
    assert zero.status_code == 200 and zero.json()["items"] == []


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A06")
def test_by_student_unknown_student_is_empty(admin):
    response = listing(admin, f"{c.CERT}/by-student/{c.UNKNOWN}")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "has_next": False}


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A07")
def test_get_one_certificate(admin, lst):
    response = admin.get(f"{c.CERT}/{lst.r1['id']}")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == c.CERT_KEYS
    assert body["remarks"] == "first" and body["type_name"] == lst.type["name"]
    missing = admin.get(f"{c.CERT}/{c.UNKNOWN}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == f"Certificate with id {c.UNKNOWN} not found"
    assert admin.get(f"{c.CERT}/abc").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A08")
def test_student_cannot_read_another_students_certificate(lst):
    assert lst.fam.s2_client.get(f"{c.CERT}/{lst.r1['id']}").status_code == 403
    assert lst.fam.s1_client.get(f"{c.CERT}/{lst.r1['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A09")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 403), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_admin_lists_permission_matrix(role_clients, lst, role, status):
    sid = lst.fam.s1.student_id
    client = role_clients[role]
    assert client.get(f"{c.CERT}/received").status_code == status
    assert client.get(f"{c.CERT}/issued").status_code == status
    denied = client.get(f"{c.CERT}/by-student/{sid}")
    assert denied.status_code == status
    if status == 403:
        assert denied.json()["detail"] == "Only Admin can access this endpoint"


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A10")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 403), ("parent", 403)]
)
def test_plain_list_permission_matrix(role_clients, lst, role, status):
    assert role_clients[role].get(f"{c.CERT}/", params={"student_id": lst.fam.s1.student_id}).status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A11")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 200), ("parent", 403)]
)
def test_get_one_permission_matrix(role_clients, lst, role, status):
    response = role_clients[role].get(f"{c.CERT}/{lst.r1['id']}")
    expected = 403 if role == "student" else status
    assert response.status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A12")
def test_lists_require_token(anon, lst):
    sid = lst.fam.s1.student_id
    for path in (
        f"{c.CERT}/",
        f"{c.CERT}/received",
        f"{c.CERT}/issued",
        f"{c.CERT}/by-student/{sid}",
        f"{c.CERT}/{lst.r1['id']}",
    ):
        assert anon.get(path).status_code == 401, path


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A13")
def test_lists_tenant_isolation(admin, tenant_b, tenant_b_name, lst):
    sid = lst.fam.s1.student_id
    assert tenant_b.get(f"{c.CERT}/by-student/{sid}").json()["items"] == []
    assert tenant_b.get(f"{c.CERT}/", params={"student_id": sid}).json()["items"] == []
    assert tenant_b.get(f"{c.CERT}/{lst.r1['id']}").status_code == 404
    header = {"cschema": tenant_b_name}
    assert admin.get(f"{c.CERT}/by-student/{sid}", headers=header).status_code == 403
    assert admin.get(f"{c.CERT}/", headers=header).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-07-A14")
def test_fixed_routes_are_not_parsed_as_ids(admin):
    for path in (f"{c.CERT}/my", f"{c.CERT}/received", f"{c.CERT}/selector/classes"):
        response = admin.get(path)
        assert response.status_code != 422, path
        if response.status_code == 422:
            raise AssertionError(response.text)


@pytest.mark.api
@pytest.mark.tc("TC-CER-11-A01")
def test_student_my_certificates(lst):
    response = lst.fam.s1_client.get(f"{c.CERT}/my")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert {i["id"] for i in body["items"]} == lst.s1_ids
    assert {i["student_id"] for i in body["items"]} == {lst.fam.s1.student_id}


@pytest.mark.api
@pytest.mark.tc("TC-CER-11-A02")
def test_each_student_sees_only_their_own(lst):
    other = lst.fam.s2_client.get(f"{c.CERT}/my").json()
    assert [i["id"] for i in other["items"]] == [lst.s2_r["id"]]


@pytest.mark.api
@pytest.mark.tc("TC-CER-11-A03")
def test_my_certificates_pagination(lst):
    first = lst.fam.s1_client.get(f"{c.CERT}/my", params={"limit": 1, "skip": 0}).json()
    last = lst.fam.s1_client.get(f"{c.CERT}/my", params={"limit": 1, "skip": 2}).json()
    assert len(first["items"]) == 1 and first["has_next"] is True
    assert len(last["items"]) == 1 and last["has_next"] is False


@pytest.mark.api
@pytest.mark.tc("TC-CER-11-A04")
def test_student_without_student_record_gets_empty_page(student):
    response = student.get(f"{c.CERT}/my")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "has_next": False}


@pytest.mark.api
@pytest.mark.tc("TC-CER-11-A05")
@pytest.mark.parametrize(
    "role,status", [("admin", 403), ("staff", 403), ("teacher", 403), ("student", 200), ("parent", 403)]
)
def test_my_permission_matrix(role_clients, role, status):
    assert role_clients[role].get(f"{c.CERT}/my").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-CER-11-A06")
def test_my_requires_token(anon):
    assert anon.get(f"{c.CERT}/my").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-11-A07")
def test_my_tenant_mismatch(lst, tenant_b_name):
    assert lst.fam.s1_client.get(f"{c.CERT}/my", headers={"cschema": tenant_b_name}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-11-A08")
def test_generated_certificate_not_in_my(admin, lst, cleanup):
    template = admin.post(f"{c.ISSUE}/templates/", json={"name": unique("cer_tpl"), "html_template": "<p>x</p>"}).json()
    cleanup.delete_later(admin, f"{c.ISSUE}/templates/{template['id']}/")
    made = admin.post(
        f"{c.ISSUE}/generate/",
        json={"student_id": lst.fam.s1.student_id, "template_id": template["id"], "edited_html": "<p>y</p>"},
    ).json()
    cleanup.delete_later(admin, f"{c.ISSUE}/issued/{made['id']}/")
    mine = lst.fam.s1_client.get(f"{c.CERT}/my").json()
    assert made["id"] not in [i["id"] for i in mine["items"]]
    assert mine["total"] == 3


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A01")
def test_parent_reads_linked_child(lst):
    response = lst.fam.p1_client.get(f"{c.CERT}/my-child/{lst.fam.s1.student_id}")
    assert response.status_code == 200
    assert {i["id"] for i in response.json()["items"]} == lst.s1_ids


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A02")
def test_parent_cannot_read_unlinked_child(lst):
    response = lst.fam.p1_client.get(f"{c.CERT}/my-child/{lst.fam.s2.student_id}")
    assert response.status_code == 403
    assert response.json()["detail"] == "You are not the parent of this student"


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A03")
def test_parent_received_and_issued_return_same_mix(lst):
    sid = lst.fam.s1.student_id
    for suffix in ("received", "issued"):
        response = lst.fam.p1_client.get(f"{c.CERT}/my-child/{sid}/{suffix}")
        assert response.status_code == 200
        assert {i["id"] for i in response.json()["items"]} == lst.s1_ids


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A04")
def test_parent_without_parent_row(parent, lst):
    response = parent.get(f"{c.CERT}/my-child/{lst.fam.s1.student_id}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Parent profile not found"


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A05")
def test_each_parent_sees_only_own_child(lst):
    other = lst.fam.p2_client.get(f"{c.CERT}/my-child/{lst.fam.s2.student_id}")
    assert other.status_code == 200
    assert [i["id"] for i in other.json()["items"]] == [lst.s2_r["id"]]
    assert lst.fam.p2_client.get(f"{c.CERT}/my-child/{lst.fam.s1.student_id}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A06")
def test_student_issued_view_is_own_only(lst):
    own = lst.fam.s1_client.get(f"{c.CERT}/my-child/{lst.fam.s1.student_id}/issued")
    assert own.status_code == 200
    other = lst.fam.s1_client.get(f"{c.CERT}/my-child/{lst.fam.s2.student_id}/issued")
    assert other.status_code == 403
    assert other.json()["detail"] == "You can only view your own certificates"


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A07")
def test_student_cannot_use_my_child_for_another_student(lst):
    assert lst.fam.s1_client.get(f"{c.CERT}/my-child/{lst.fam.s2.student_id}").status_code == 403
    assert lst.fam.s1_client.get(f"{c.CERT}/my-child/{lst.fam.s2.student_id}/received").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A08")
@pytest.mark.parametrize("role", ["admin", "staff", "teacher"])
def test_staff_roles_use_my_child_for_any_student(role_clients, lst, role):
    response = role_clients[role].get(f"{c.CERT}/my-child/{lst.fam.s2.student_id}")
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A09")
def test_parent_cannot_write(lst, cfam):
    parent = lst.fam.p1_client
    assert c.send_received(parent, cfam.s1.student_id, lst.type["id"]).status_code == 403
    assert c.send_issued(parent, cfam.s1.student_id, lst.type["id"], c.iso(c.today())).status_code == 403
    assert parent.patch(f"{c.CERT}/{lst.r1['id']}", data={"remarks": "x"}).status_code == 403
    assert parent.delete(f"{c.CERT}/{lst.r1['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A10")
def test_my_child_requires_token(anon, lst):
    sid = lst.fam.s1.student_id
    for suffix in ("", "/received", "/issued"):
        assert anon.get(f"{c.CERT}/my-child/{sid}{suffix}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-12-A11")
def test_my_child_tenant_isolation(lst, tenant_b, tenant_b_name):
    sid = lst.fam.s1.student_id
    assert lst.fam.p1_client.get(f"{c.CERT}/my-child/{sid}", headers={"cschema": tenant_b_name}).status_code == 403
    assert tenant_b.get(f"{c.CERT}/my-child/{sid}").json()["items"] == []


@pytest.mark.api
@pytest.mark.tc("TC-CER-13-A01")
def test_teacher_lists_any_students_certificates(teacher, lst):
    response = teacher.get(f"{c.CERT}/", params={"student_id": lst.fam.s1.student_id})
    assert response.status_code == 200
    assert {i["id"] for i in response.json()["items"]} == lst.s1_ids


@pytest.mark.api
@pytest.mark.tc("TC-CER-13-A02")
def test_teacher_reads_and_downloads(teacher, lst):
    assert teacher.get(f"{c.CERT}/{lst.r1['id']}").status_code == 200
    assert teacher.get(f"{c.CERT}/{lst.r1['id']}/download").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-CER-13-A03")
def test_teacher_cannot_use_admin_lists(teacher, lst):
    for path in (
        f"{c.CERT}/selector/classes",
        f"{c.CERT}/received",
        f"{c.CERT}/issued",
        f"{c.CERT}/by-student/{lst.fam.s1.student_id}",
    ):
        assert teacher.get(path).status_code == 403, path


@pytest.mark.api
@pytest.mark.tc("TC-CER-13-A04")
def test_teacher_cannot_write(teacher, lst):
    sid, tid = lst.fam.s1.student_id, lst.type["id"]
    assert c.send_received(teacher, sid, tid).status_code == 403
    assert c.send_issued(teacher, sid, tid, c.iso(c.today())).status_code == 403
    assert c.send_legacy(teacher, sid, tid).status_code == 403
    assert teacher.patch(f"{c.CERT}/{lst.r1['id']}", data={"remarks": "x"}).status_code == 403
    assert teacher.delete(f"{c.CERT}/{lst.r1['id']}").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-13-A05")
def test_teacher_type_search(teacher, lst):
    response = teacher.get(f"{c.CERT}/types/search", params={"q": lst.type["name"][:8]})
    assert response.status_code == 200
    assert lst.type["id"] in [t["id"] for t in response.json()]


@pytest.mark.api
@pytest.mark.tc("TC-CER-13-A06")
def test_teacher_views_require_token(anon, lst):
    assert anon.get(f"{c.CERT}/", params={"student_id": lst.fam.s1.student_id}).status_code == 401
    assert anon.get(f"{c.CERT}/types/search").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-13-A07")
def test_teacher_tenant_mismatch(teacher, lst, tenant_b_name):
    header = {"cschema": tenant_b_name}
    assert teacher.get(f"{c.CERT}/", params={"student_id": lst.fam.s1.student_id}, headers=header).status_code == 403
