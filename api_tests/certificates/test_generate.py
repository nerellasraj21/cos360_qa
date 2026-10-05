import pytest

from api_tests.certificates.helpers import CERT, ISSUE, UNKNOWN
from api_tests.support import unique

GEN = f"{ISSUE}/generate/"
ISSUED = f"{ISSUE}/issued/"
TPL = f"{ISSUE}/templates/"
GEN_KEYS = {
    "id",
    "student_id",
    "template_id",
    "html_content",
    "issued_date",
    "issued_by",
    "remarks",
    "is_active",
    "created_at",
    "updated_at",
}


@pytest.fixture
def tpl(admin, cleanup):
    response = admin.post(TPL, json={"name": unique("cer_tpl"), "html_template": "<p>{{student_name}}</p>"})
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{TPL}{response.json()['id']}/")
    return response.json()


def generate(client, student_id, template_id, html="<p>Certified {{student_name}}</p>", **extra):
    return client.post(GEN, json={"student_id": student_id, "template_id": template_id, "edited_html": html, **extra})


def generated(admin, cleanup, student_id, template_id, **kwargs):
    response = generate(admin, student_id, template_id, **kwargs)
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{ISSUED}{response.json()['id']}/")
    return response.json()


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A01")
def test_admin_generates_certificate(admin, logins, cfam, tpl, cleanup):
    html = "<p>Certified {{student_name}} &amp; kept verbatim</p>"
    body = generated(admin, cleanup, cfam.s1.student_id, tpl["id"], html=html, remarks="first copy")
    assert set(body) == GEN_KEYS
    assert body["html_content"] == html
    assert body["is_active"] == "True"
    assert body["issued_by"] == logins["admin"]["user"]["id"]
    assert body["student_id"] == cfam.s1.student_id and body["template_id"] == tpl["id"]
    assert body["remarks"] == "first copy"


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A02")
def test_generate_validation(admin, cfam, tpl, cleanup):
    assert generate(admin, cfam.s1.student_id, tpl["id"], html="").status_code == 422
    assert generated(admin, cleanup, cfam.s1.student_id, tpl["id"], remarks="r" * 500)["remarks"] == "r" * 500
    assert generate(admin, cfam.s1.student_id, tpl["id"], remarks="r" * 501).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A03")
def test_generate_unknown_template_and_malformed_ids(admin, cfam, tpl):
    missing = generate(admin, cfam.s1.student_id, UNKNOWN)
    assert missing.status_code == 404 and missing.json()["detail"] == "Template not found"
    assert generate(admin, "abc", tpl["id"]).status_code == 422
    assert generate(admin, cfam.s1.student_id, "abc").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A04")
def test_generate_unknown_student(admin, tpl):
    response = generate(admin, UNKNOWN, tpl["id"])
    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A05")
def test_generate_with_inactive_template(admin, cfam, tpl):
    assert admin.delete(f"{TPL}{tpl['id']}/").status_code == 204
    response = generate(admin, cfam.s1.student_id, tpl["id"])
    assert response.status_code == 400
    assert response.json()["detail"] == "Template is inactive"


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A06")
def test_list_generated_after_delete(admin, cfam, tpl, cleanup):
    keep = generated(admin, cleanup, cfam.s2.student_id, tpl["id"])
    drop = generated(admin, cleanup, cfam.s2.student_id, tpl["id"])
    assert admin.delete(f"{ISSUED}{drop['id']}/").status_code == 204
    response = admin.get(ISSUED, params={"student_id": cfam.s2.student_id})
    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert keep["id"] in ids and drop["id"] not in ids


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A07")
def test_get_generated_and_argument_errors(admin, cfam, tpl, cleanup):
    created = generated(admin, cleanup, cfam.s1.student_id, tpl["id"])
    assert admin.get(ISSUED).status_code == 422
    assert admin.get(f"{ISSUED}{created['id']}/").json() == created
    missing = admin.get(f"{ISSUED}{UNKNOWN}/")
    assert missing.status_code == 404 and missing.json()["detail"] == "Certificate not found"


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A08")
def test_delete_generated_is_soft(admin, cfam, tpl, cleanup):
    created = generated(admin, cleanup, cfam.s1.student_id, tpl["id"])
    assert admin.delete(f"{ISSUED}{created['id']}/").status_code == 204
    after = admin.get(f"{ISSUED}{created['id']}/")
    assert after.status_code == 200 and after.json()["is_active"] == "False"
    assert created["id"] not in [r["id"] for r in admin.get(ISSUED, params={"student_id": cfam.s1.student_id}).json()]


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A09")
def test_generated_certificates_are_invisible_elsewhere(admin, cfam, tpl, cleanup):
    created = generated(admin, cleanup, cfam.s1.student_id, tpl["id"])
    by_student = admin.get(f"{CERT}/by-student/{cfam.s1.student_id}")
    assert created["id"] not in [i["id"] for i in by_student.json()["items"]]
    mine = cfam.s1_client.get(f"{CERT}/my")
    assert mine.status_code == 200
    assert created["id"] not in [i["id"] for i in mine.json()["items"]]
    docs = admin.get("/students/documents/all", params={"student_id": cfam.s1.student_id})
    assert created["id"] not in [i["id"] for i in docs.json()]


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A10")
@pytest.mark.parametrize(
    "role,status", [("admin", 201), ("staff", 403), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_generate_permission_matrix(role_clients, admin, cfam, tpl, cleanup, role, status):
    response = generate(role_clients[role], cfam.s1.student_id, tpl["id"])
    assert response.status_code == status
    if status == 201:
        cleanup.delete_later(admin, f"{ISSUED}{response.json()['id']}/")
    else:
        assert response.json()["detail"] == "Only Admin can generate certificates"


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A11")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 403), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_read_generated_permission_matrix(role_clients, admin, cfam, tpl, cleanup, role, status):
    created = generated(admin, cleanup, cfam.s1.student_id, tpl["id"])
    assert role_clients[role].get(ISSUED, params={"student_id": cfam.s1.student_id}).status_code == status
    assert role_clients[role].get(f"{ISSUED}{created['id']}/").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A12")
@pytest.mark.parametrize(
    "role,status", [("admin", 204), ("staff", 403), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_delete_generated_permission_matrix(role_clients, admin, cfam, tpl, cleanup, role, status):
    created = generated(admin, cleanup, cfam.s1.student_id, tpl["id"])
    assert role_clients[role].delete(f"{ISSUED}{created['id']}/").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A13")
def test_generate_requires_token(anon, cfam):
    assert anon.post(GEN, json={"student_id": cfam.s1.student_id, "template_id": UNKNOWN, "edited_html": "x"}).status_code == 401
    assert anon.get(ISSUED, params={"student_id": cfam.s1.student_id}).status_code == 401
    assert anon.get(f"{ISSUED}{UNKNOWN}/").status_code == 401
    assert anon.delete(f"{ISSUED}{UNKNOWN}/").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-06-A14")
def test_generate_tenant_isolation(admin, tenant_b, tenant_b_name, cfam, tpl):
    in_b = generate(tenant_b, cfam.s1.student_id, tpl["id"])
    assert in_b.status_code == 404 and in_b.json()["detail"] == "Template not found"
    header = {"cschema": tenant_b_name}
    body = {"student_id": cfam.s1.student_id, "template_id": tpl["id"], "edited_html": "x"}
    assert admin.post(GEN, json=body, headers=header).status_code == 403
    assert admin.get(ISSUED, params={"student_id": cfam.s1.student_id}, headers=header).status_code == 403
