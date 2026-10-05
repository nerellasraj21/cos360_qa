import httpx
import pytest

from api_tests.certificates.helpers import ISSUE, UNKNOWN
from api_tests.support import API_URL, unique

TPL = f"{ISSUE}/templates/"
KEYS = {"id", "name", "html_template", "color_theme", "variables_used", "is_active", "created_at", "updated_at"}


def make_template(client, cleanup=None, **body):
    body.setdefault("name", unique("cer_tpl"))
    body.setdefault("html_template", "<p>{{student_name}} {{dob}}</p>")
    response = client.post(TPL, json=body)
    if response.status_code == 201 and cleanup is not None:
        cleanup.delete_later(client, f"{TPL}{response.json()['id']}/")
    return response


def variables(row):
    return set((row["variables_used"] or "").split(",")) - {""}


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A01")
def test_create_template_extracts_variables(admin, cleanup):
    response = make_template(admin, cleanup, html_template="<p>{{student_name}} {{dob}} {{student_name}} {{ spaced }}</p>")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == KEYS
    assert variables(body) == {"student_name", "dob"}
    assert body["is_active"] == "True"
    assert body["color_theme"] == "blue"


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A02")
@pytest.mark.parametrize(
    "body",
    [
        {"name": ""},
        {"html_template": ""},
        {"name": "n" * 256},
    ],
)
def test_create_validation(admin, body):
    assert make_template(admin, **body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A03")
def test_color_theme_is_not_validated(admin, cleanup):
    response = make_template(admin, cleanup, color_theme="purple")
    assert response.status_code == 201
    assert response.json()["color_theme"] == "purple"


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A04")
def test_list_returns_active_templates_only(admin, cleanup):
    keep = make_template(admin, cleanup).json()
    drop = make_template(admin, cleanup).json()
    assert admin.delete(f"{TPL}{drop['id']}/").status_code == 204
    listed = admin.get(TPL)
    assert listed.status_code == 200
    ids = [t["id"] for t in listed.json()]
    assert keep["id"] in ids and drop["id"] not in ids


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A05")
def test_get_template_including_inactive(admin, cleanup):
    active = make_template(admin, cleanup).json()
    inactive = make_template(admin, cleanup).json()
    admin.delete(f"{TPL}{inactive['id']}/")
    assert admin.get(f"{TPL}{active['id']}/").status_code == 200
    soft = admin.get(f"{TPL}{inactive['id']}/")
    assert soft.status_code == 200 and soft.json()["is_active"] == "False"
    missing = admin.get(f"{TPL}{UNKNOWN}/")
    assert missing.status_code == 404 and missing.json()["detail"] == "Template not found"


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A06")
def test_put_html_recomputes_variables(admin, cleanup):
    created = make_template(admin, cleanup, html_template="<p>{{a}} {{b}}</p>", color_theme="green").json()
    response = admin.put(f"{TPL}{created['id']}/", json={"html_template": "<p>{{c}}</p>"})
    assert response.status_code == 200
    body = response.json()
    assert variables(body) == {"c"}
    assert body["name"] == created["name"] and body["color_theme"] == "green"


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A07")
def test_put_name_and_theme_keep_variables(admin, cleanup):
    created = make_template(admin, cleanup, html_template="<p>{{a}} {{b}}</p>").json()
    renamed = unique("cer_tpl")
    by_name = admin.put(f"{TPL}{created['id']}/", json={"name": renamed})
    assert by_name.status_code == 200 and by_name.json()["name"] == renamed
    assert variables(by_name.json()) == {"a", "b"}
    by_theme = admin.put(f"{TPL}{created['id']}/", json={"color_theme": "red"})
    assert by_theme.json()["color_theme"] == "red"
    assert variables(by_theme.json()) == {"a", "b"}


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A08")
@pytest.mark.xfail(strict=True, reason="CER-BUG-1: PUT /issuable-certificates/templates/{id}/ with is_active true/false returns 500 (boolean bound to a string column)")
def test_put_is_active_false_hides_template(admin, cleanup):
    created = make_template(admin, cleanup).json()
    response = admin.put(f"{TPL}{created['id']}/", json={"is_active": False})
    assert response.status_code == 200, response.text
    assert created["id"] not in [t["id"] for t in admin.get(TPL).json()]


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A09")
def test_put_and_delete_unknown_template(admin):
    put = admin.put(f"{TPL}{UNKNOWN}/", json={"name": "x"})
    assert put.status_code == 404 and put.json()["detail"] == "Template not found"
    deleted = admin.delete(f"{TPL}{UNKNOWN}/")
    assert deleted.status_code == 404 and deleted.json()["detail"] == "Template not found"


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A10")
def test_delete_is_a_soft_delete(admin, cleanup):
    created = make_template(admin, cleanup).json()
    assert admin.delete(f"{TPL}{created['id']}/").status_code == 204
    assert admin.delete(f"{TPL}{created['id']}/").status_code == 204
    assert admin.get(f"{TPL}{created['id']}/").json()["is_active"] == "False"


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A11")
@pytest.mark.parametrize(
    "role,status", [("admin", 201), ("staff", 403), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_write_permission_matrix(role_clients, admin, cleanup, role, status):
    client = role_clients[role]
    created = client.post(TPL, json={"name": unique("cer_tpl"), "html_template": "<p>x</p>"})
    assert created.status_code == status
    if status == 403:
        assert created.json()["detail"] == "Only Admin can create certificate templates"
    else:
        cleanup.delete_later(admin, f"{TPL}{created.json()['id']}/")
    target = make_template(admin, cleanup).json()
    updated = client.put(f"{TPL}{target['id']}/", json={"name": unique("cer_tpl")})
    assert updated.status_code == (200 if status == 201 else 403)
    if status == 403:
        assert updated.json()["detail"] == "Only Admin can update certificate templates"
    victim = make_template(admin, cleanup).json()
    removed = client.delete(f"{TPL}{victim['id']}/")
    assert removed.status_code == (204 if status == 201 else 403)
    if status == 403:
        assert removed.json()["detail"] == "Only Admin can delete certificate templates"


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A12")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 403), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_read_permission_matrix(role_clients, admin, cleanup, role, status):
    created = make_template(admin, cleanup).json()
    assert role_clients[role].get(TPL).status_code == status
    assert role_clients[role].get(f"{TPL}{created['id']}/").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A13")
@pytest.mark.skip(reason="blocked: needs a custom role named admin and a user in it; role and user management mutate shared tenant data")
def test_lowercase_admin_role_is_refused():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A14")
def test_templates_require_token(anon):
    assert anon.get(TPL).status_code == 401
    assert anon.get(f"{TPL}{UNKNOWN}/").status_code == 401
    assert anon.post(TPL, json={"name": "x", "html_template": "y"}).status_code == 401
    assert anon.put(f"{TPL}{UNKNOWN}/", json={"name": "x"}).status_code == 401
    assert anon.delete(f"{TPL}{UNKNOWN}/").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A15")
def test_templates_tenant_isolation(admin, tenant_b, tenant_b_name, cleanup):
    created = make_template(admin, cleanup).json()
    listed = tenant_b.get(TPL)
    assert listed.status_code == 200
    assert created["id"] not in [t["id"] for t in listed.json()]
    assert tenant_b.get(f"{TPL}{created['id']}/").status_code == 404
    header = {"cschema": tenant_b_name}
    assert admin.get(TPL, headers=header).status_code == 403
    assert admin.post(TPL, json={"name": "x", "html_template": "y"}, headers=header).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-02-A16")
def test_slashless_path_redirects(admin):
    response = httpx.get(
        f"{API_URL}/issuable-certificates/templates",
        headers={"Authorization": f"Bearer {admin.token}"},
        follow_redirects=False,
        timeout=30,
    )
    assert response.status_code == 307
    assert response.headers["location"].rstrip("?").endswith("/issuable-certificates/templates/")
    assert admin.get("/issuable-certificates/templates/").status_code == 200
