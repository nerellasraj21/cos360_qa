import pytest

from api_tests.certificates.helpers import CERT, UNKNOWN, iso, received, send_issued, today
from api_tests.support import unique

TYPES = f"{CERT}/types"


def make_type(client, cleanup=None, **body):
    body.setdefault("name", unique("cer_t"))
    response = client.post(f"{TYPES}/", json=body)
    if response.status_code == 201 and cleanup is not None:
        cleanup.delete_later(client, f"{TYPES}/{response.json()['id']}")
    return response


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A01")
def test_create_type(admin, cleanup):
    name = unique("cer_t")
    response = make_type(admin, cleanup, name=name, description="Birth records")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "name", "description"}
    assert body["name"] == name and body["description"] == "Birth records"


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A02")
def test_duplicate_name_and_other_tenant(admin, tenant_b, cleanup):
    name = unique("cer_t")
    assert make_type(admin, cleanup, name=name).status_code == 201
    duplicate = make_type(admin, name=name)
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == f"Certificate type name '{name}' already exists"
    in_b = make_type(tenant_b, cleanup=None, name=name)
    assert in_b.status_code == 201
    cleanup.delete_later(tenant_b, f"{TYPES}/{in_b.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A03")
def test_create_validation_and_length_limits(admin):
    assert admin.post(f"{TYPES}/", json={"description": "x"}).status_code == 422
    long_name = admin.post(f"{TYPES}/", json={"name": "n" * 101})
    assert long_name.status_code == 500
    assert long_name.json()["detail"].startswith("Error creating certificate type")
    long_description = admin.post(f"{TYPES}/", json={"name": unique("cer_t"), "description": "d" * 256})
    assert long_description.status_code == 500


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A04")
def test_empty_name_is_accepted(admin):
    response = admin.post(f"{TYPES}/", json={"name": ""})
    try:
        assert response.status_code == 201
        assert response.json()["name"] == ""
    finally:
        if response.status_code == 201:
            admin.delete(f"{TYPES}/{response.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A05")
def test_list_pagination_is_consistent(admin, cleanup):
    made = [make_type(admin, cleanup).json() for _ in range(3)]
    first = admin.get(f"{TYPES}/", params={"limit": 10, "skip": 0}).json()
    total = first["total_count"]
    assert set(first) == {"items", "total_count", "has_next"}
    assert len(first["items"]) == min(10, total)
    assert first["has_next"] is (total > 10)
    names = [i["name"] for i in first["items"]]
    assert names == sorted(names)
    beyond = admin.get(f"{TYPES}/", params={"limit": 10, "skip": total}).json()
    assert beyond["items"] == [] and beyond["has_next"] is False
    everything = admin.get(f"{TYPES}/", params={"limit": 100, "skip": 0}).json()
    if everything["total_count"] <= 100:
        assert {m["id"] for m in made} <= {i["id"] for i in everything["items"]}


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A06")
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"skip": -1}])
def test_list_bounds(admin, params):
    assert admin.get(f"{TYPES}/", params=params).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A06")
def test_slashless_list_path_is_parsed_as_certificate_id(admin):
    response = admin.get(TYPES)
    assert response.status_code == 422
    assert any(err["loc"][-1] == "certificate_id" for err in response.json()["detail"])


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A07")
def test_search(admin, cleanup):
    created = make_type(admin, cleanup).json()
    hit = admin.get(f"{TYPES}/search", params={"q": created["name"][:8].upper()})
    assert hit.status_code == 200
    assert created["id"] in [t["id"] for t in hit.json()]
    names = [t["name"] for t in hit.json()]
    assert names == sorted(names)
    assert admin.get(f"{TYPES}/search", params={"q": ""}).status_code == 200
    assert admin.get(f"{TYPES}/search", params={"limit": 100}).status_code == 200
    assert admin.get(f"{TYPES}/search", params={"limit": 101}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A08")
def test_dropdown_sees_new_type_immediately(admin, cleanup):
    admin.get(f"{TYPES}/dropdown")
    created = make_type(admin, cleanup).json()
    rows = admin.get(f"{TYPES}/dropdown").json()
    assert {"id": created["id"], "name": created["name"]} in rows
    renamed = unique("cer_t")
    assert admin.put(f"{TYPES}/{created['id']}", json={"name": renamed}).status_code == 200
    assert {"id": created["id"], "name": renamed} in admin.get(f"{TYPES}/dropdown").json()


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A09")
def test_get_one(admin, cleanup):
    created = make_type(admin, cleanup, description="d").json()
    assert admin.get(f"{TYPES}/{created['id']}").json() == created
    missing = admin.get(f"{TYPES}/{UNKNOWN}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == f"Certificate type with id {UNKNOWN} not found"
    assert admin.get(f"{TYPES}/abc").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A10")
def test_update_rules(admin, cleanup):
    first = make_type(admin, cleanup).json()
    second = make_type(admin, cleanup, description="old").json()
    clash = admin.put(f"{TYPES}/{second['id']}", json={"name": first["name"]})
    assert clash.status_code == 400
    free = unique("cer_t")
    renamed = admin.put(f"{TYPES}/{second['id']}", json={"name": free})
    assert renamed.status_code == 200 and renamed.json()["name"] == free
    described = admin.put(f"{TYPES}/{second['id']}", json={"description": "new"})
    assert described.status_code == 200
    assert described.json()["name"] == free and described.json()["description"] == "new"
    assert admin.put(f"{TYPES}/{second['id']}", json={"name": free}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A11")
def test_delete_unused_and_used_types(admin, cfam, cleanup):
    unused = make_type(admin).json()
    done = admin.delete(f"{TYPES}/{unused['id']}")
    assert done.status_code == 200
    assert done.json() == {"message": "Certificate type deleted successfully"}
    assert admin.get(f"{TYPES}/{unused['id']}").status_code == 404
    used = make_type(admin, cleanup).json()
    received(admin, cleanup, cfam.s1.student_id, used["id"])
    blocked = admin.delete(f"{TYPES}/{used['id']}")
    assert blocked.status_code == 400
    assert f"Cannot delete certificate type '{used['name']}' because it is being used by 1 student certificate(s)" in blocked.json()["detail"]


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A12")
@pytest.mark.parametrize(
    "role,status", [("admin", 201), ("staff", 403), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_write_permission_matrix(role_clients, admin, cleanup, role, status):
    created = role_clients[role].post(f"{TYPES}/", json={"name": unique("cer_t")})
    assert created.status_code == status
    target = make_type(admin, cleanup).json()
    renamed = role_clients[role].put(f"{TYPES}/{target['id']}", json={"description": "x"})
    assert renamed.status_code == (200 if status == 201 else 403)
    victim = make_type(admin, cleanup).json()
    deleted = role_clients[role].delete(f"{TYPES}/{victim['id']}")
    assert deleted.status_code == (200 if status == 201 else 403)
    if created.status_code == 201:
        cleanup.delete_later(admin, f"{TYPES}/{created.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A13")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 200), ("parent", 403)]
)
def test_read_permission_matrix(role_clients, admin, cleanup, role, status):
    created = make_type(admin, cleanup).json()
    client = role_clients[role]
    assert client.get(f"{TYPES}/").status_code == status
    assert client.get(f"{TYPES}/dropdown").status_code == status
    assert client.get(f"{TYPES}/{created['id']}").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A14")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 403), ("parent", 403)]
)
def test_search_permission_matrix(role_clients, role, status):
    assert role_clients[role].get(f"{TYPES}/search").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A15")
def test_types_require_token(anon):
    assert anon.post(f"{TYPES}/", json={"name": "x"}).status_code == 401
    for path in (f"{TYPES}/", f"{TYPES}/search", f"{TYPES}/dropdown", f"{TYPES}/{UNKNOWN}"):
        assert anon.get(path).status_code == 401
    assert anon.put(f"{TYPES}/{UNKNOWN}", json={"name": "x"}).status_code == 401
    assert anon.delete(f"{TYPES}/{UNKNOWN}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A16")
def test_types_tenant_isolation(admin, tenant_b, tenant_b_name, cleanup):
    created = make_type(admin, cleanup).json()
    assert created["id"] not in [t["id"] for t in tenant_b.get(f"{TYPES}/dropdown").json()]
    assert created["name"] not in [t["name"] for t in tenant_b.get(f"{TYPES}/search", params={"q": created["name"]}).json()]
    assert tenant_b.get(f"{TYPES}/{created['id']}").status_code == 404
    header = {"cschema": tenant_b_name}
    assert admin.get(f"{TYPES}/", headers=header).status_code == 403
    assert admin.post(f"{TYPES}/", json={"name": unique("cer_t")}, headers=header).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-01-A17")
@pytest.mark.skip(reason="skipped: needs the rate limiter, which is disabled in the QA API")
def test_create_rate_limit():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-CER-09-A05")
def test_type_can_be_deleted_after_its_only_certificate_is_deleted(admin, cfam, ctype):
    created = send_issued(admin, cfam.s1.student_id, ctype["id"], iso(today()))
    assert created.status_code == 201, created.text
    cert = created.json()
    assert admin.delete(f"{TYPES}/{ctype['id']}").status_code == 400
    assert admin.delete(f"{CERT}/{cert['id']}").status_code == 204
    assert admin.delete(f"{TYPES}/{ctype['id']}").status_code == 200
