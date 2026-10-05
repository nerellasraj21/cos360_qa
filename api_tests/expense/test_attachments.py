import uuid

import pytest

from api_tests.expense.helpers import (
    ROLES,
    approve_body,
    forbidden_roles,
    make_category,
    make_txn,
    make_type,
    other_tenant_header,
    tiny_file,
)

BASE = "/expense/attachments/"


@pytest.fixture
def txn(admin, cleanup):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    return make_txn(admin, cleanup, expense_type["id"])


def upload(client, transaction_id, name="qa.txt", size=1024, document_type="invoice"):
    return client.post(
        f"{BASE}transactions/{transaction_id}/upload",
        params={"document_type": document_type},
        files=tiny_file(name, size),
    )


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A01")
def test_upload_attachment(admin, txn):
    response = upload(admin, txn["id"], "qa.txt", 1024)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["file_size"] == 1024
    assert data["file_path"] == "/temp/path"
    assert data["mime_type"] == "application/octet-stream"
    assert data["virus_scan_status"] == "pending"
    assert data["is_verified"] is False
    assert data["original_filename"] == "qa.txt"
    assert data["document_type"] == "invoice"
    assert data["stored_filename"].endswith("_qa.txt")


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A02")
def test_upload_without_document_type(admin, txn):
    response = admin.post(f"{BASE}transactions/{txn['id']}/upload", files=tiny_file())
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A03")
def test_upload_empty_file(admin, txn):
    response = upload(admin, txn["id"], size=0)
    assert response.status_code == 400
    assert "Empty file uploaded" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A04")
def test_upload_size_limit(admin, txn):
    limit = 10485760
    assert upload(admin, txn["id"], size=limit).status_code == 201
    over = upload(admin, txn["id"], size=limit + 1)
    assert over.status_code == 413
    assert "10MB" in over.text


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A05")
def test_upload_unknown_transaction(admin):
    response = upload(admin, uuid.uuid4())
    assert response.status_code == 404
    assert "Expense transaction not found" in response.text


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A06")
def test_upload_to_approved_transaction(admin, cleanup):
    category = make_category(admin, cleanup)
    expense_type = make_type(admin, cleanup, category["id"])
    data = make_txn(admin, cleanup, expense_type["id"], "1500.00")
    admin.post(f"/expense/transactions/{data['id']}/approval", json=approve_body())
    assert upload(admin, data["id"]).status_code == 201


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A07")
def test_list_attachments(admin, txn):
    first = upload(admin, txn["id"], "first.txt").json()
    second = upload(admin, txn["id"], "second.txt").json()
    response = admin.get(f"{BASE}transactions/{txn['id']}/list")
    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert ids == [second["id"], first["id"]]
    assert admin.get(f"{BASE}transactions/{uuid.uuid4()}/list").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A08")
def test_get_attachment(admin, txn):
    created = upload(admin, txn["id"]).json()
    fetched = admin.get(f"{BASE}{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]
    assert admin.get(f"{BASE}{uuid.uuid4()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A09")
def test_download_attachment(admin, txn):
    created = upload(admin, txn["id"], "bill.txt").json()
    response = admin.get(f"{BASE}{created['id']}/download")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "bill.txt" in response.headers["content-disposition"]
    assert response.text == "Mock file content for bill.txt"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A10")
def test_update_attachment_metadata(admin, txn):
    created = upload(admin, txn["id"]).json()
    response = admin.put(f"{BASE}{created['id']}", json={"is_verified": True, "verification_notes": "ok"})
    assert response.status_code == 200, response.text
    assert response.json()["is_verified"] is True
    assert response.json()["verification_notes"] == "ok"


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A11")
def test_delete_archives_attachment(admin, txn):
    created = upload(admin, txn["id"]).json()
    response = admin.delete(f"{BASE}{created['id']}")
    assert response.status_code == 200
    assert response.json()["is_archived"] is True
    listed = admin.get(f"{BASE}transactions/{txn['id']}/list").json()
    assert created["id"] in [row["id"] for row in listed]


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A12")
@pytest.mark.parametrize("role", ROLES)
def test_role_matrix_upload_and_reads(role_clients, admin, txn, role):
    existing = upload(admin, txn["id"]).json()
    client = role_clients[role]
    allowed = role in ("admin", "staff")
    assert upload(client, txn["id"]).status_code == (201 if allowed else 403)
    expected = 200 if allowed else 403
    assert client.get(f"{BASE}transactions/{txn['id']}/list").status_code == expected
    assert client.get(f"{BASE}{existing['id']}").status_code == expected
    assert client.get(f"{BASE}{existing['id']}/download").status_code == expected


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A12")
@pytest.mark.parametrize("role", forbidden_roles(["admin"]))
def test_role_matrix_update_delete_denied(role_clients, admin, txn, role):
    existing = upload(admin, txn["id"]).json()
    client = role_clients[role]
    assert client.put(f"{BASE}{existing['id']}", json={"is_verified": True}).status_code == 403
    assert client.delete(f"{BASE}{existing['id']}").status_code == 403
    assert admin.get(f"{BASE}{existing['id']}").json()["is_archived"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A12")
def test_upload_unauthenticated(anon, txn):
    assert upload(anon, txn["id"]).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXP-10-A13")
def test_tenant_isolation(admin, tenant_b, txn):
    created = upload(admin, txn["id"]).json()
    assert tenant_b.get(f"{BASE}{created['id']}").status_code == 404
    assert tenant_b.get(f"{BASE}{created['id']}/download").status_code == 404
    assert tenant_b.get(f"{BASE}transactions/{txn['id']}/list").status_code == 404
    assert upload(tenant_b, txn["id"]).status_code == 404
    assert other_tenant_header(admin).get(f"{BASE}{created['id']}").status_code == 403
