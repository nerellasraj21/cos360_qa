import os

import pytest

from api_tests.exam.helpers import ALL_ROLES, OTHER_ROLES, create_exam, new_uuid
from api_tests.support import items_of

BOARDS = ["CBSE", "ICSE", "BTech", "Custom"]
LEVELS = ["iit", "mtech", "diploma", "inter", "others", "secondary"]


def _worker_slot():
    name = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
    digits = "".join(ch for ch in name if ch.isdigit())
    return int(digits or 0) % 4


def free_combos(*clients, count=2):
    taken = set()
    for client in clients:
        for p in client.get("/board-patterns").json():
            taken.add((p["board"], p["level"]))
    slot = _worker_slot()
    pool = [(board, level) for level in LEVELS for board in BOARDS]
    mine = [combo for idx, combo in enumerate(pool) if idx % 4 == slot]
    return [combo for combo in mine if combo not in taken][:count]


def types(n=2):
    return [
        {"exam_type_name": f"FA{i}", "nature": "formative", "weightage_percent": 10, "count_per_year": 2, "sort_order": i}
        for i in range(1, n + 1)
    ]


def make_pattern(client, cleanup, board, level, n=2, **extra):
    body = {"board": board, "level": level, "is_active": True, "exam_types": types(n)}
    body.update(extra)
    response = client.post("/board-patterns", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(client, f"/board-patterns/{data['id']}")
    return data


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A01")
def test_create_pattern(admin, cleanup):
    board, level = free_combos(admin)[0]
    data = make_pattern(admin, cleanup, board, level)
    assert data["board"] == board and data["level"] == level
    assert data["is_active"] is True
    assert len(data["exam_types"]) == 2
    for t in data["exam_types"]:
        assert t["id"] and t["pattern_id"] == data["id"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A02")
def test_duplicate_board_level_conflicts(admin, cleanup):
    board, level = free_combos(admin)[0]
    make_pattern(admin, cleanup, board, level)
    response = admin.post("/board-patterns", json={"board": board, "level": level, "exam_types": types(1)})
    assert response.status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A03")
@pytest.mark.parametrize(
    "body",
    [
        {"board": "X", "level": "iit", "exam_types": []},
        {"board": "CBSE", "level": "kg", "exam_types": []},
        {"board": "CBSE", "level": "iit", "exam_types": [{"nature": "formative"}]},
        {"board": "CBSE", "level": "iit", "exam_types": [{"exam_type_name": "A", "nature": "daily"}]},
    ],
)
def test_create_validation(admin, body):
    assert admin.post("/board-patterns", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A04")
def test_exam_type_name_length(admin, cleanup):
    board, level = free_combos(admin)[0]
    too_long = [{"exam_type_name": "x" * 51, "nature": "formative"}]
    assert admin.post("/board-patterns", json={"board": board, "level": level, "exam_types": too_long}).status_code == 422
    ok = [{"exam_type_name": "x" * 50, "nature": "formative"}]
    response = admin.post("/board-patterns", json={"board": board, "level": level, "exam_types": ok})
    assert response.status_code == 201
    cleanup.delete_later(admin, f"/board-patterns/{response.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A05")
def test_list_patterns(admin, cleanup):
    (b1, l1), (b2, l2) = free_combos(admin, count=2)
    p1 = make_pattern(admin, cleanup, b1, l1)
    p2 = make_pattern(admin, cleanup, b2, l2, n=1)
    response = admin.get("/board-patterns")
    assert response.status_code == 200
    by_id = {p["id"]: p for p in items_of(response)}
    assert len(by_id[p1["id"]]["exam_types"]) == 2
    assert len(by_id[p2["id"]]["exam_types"]) == 1


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A06")
def test_get_pattern_and_unknown(admin, cleanup):
    board, level = free_combos(admin)[0]
    p = make_pattern(admin, cleanup, board, level)
    assert admin.get(f"/board-patterns/{p['id']}").json()["id"] == p["id"]
    assert admin.get(f"/board-patterns/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A07")
def test_update_is_active_only(admin, cleanup):
    board, level = free_combos(admin)[0]
    p = make_pattern(admin, cleanup, board, level)
    response = admin.put(f"/board-patterns/{p['id']}", json={"is_active": False})
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False
    assert {t["id"] for t in data["exam_types"]} == {t["id"] for t in p["exam_types"]}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A08")
def test_update_replaces_exam_types(admin, cleanup):
    board, level = free_combos(admin)[0]
    p = make_pattern(admin, cleanup, board, level)
    new = [{"exam_type_name": "SA1", "nature": "summative", "weightage_percent": 40, "count_per_year": 1, "sort_order": 1}]
    response = admin.put(f"/board-patterns/{p['id']}", json={"exam_types": new})
    assert response.status_code == 200
    data = admin.get(f"/board-patterns/{p['id']}").json()
    assert [t["exam_type_name"] for t in data["exam_types"]] == ["SA1"]
    old_ids = {t["id"] for t in p["exam_types"]}
    assert not old_ids & {t["id"] for t in data["exam_types"]}
    cleared = admin.put(f"/board-patterns/{p['id']}", json={"exam_types": []})
    assert cleared.status_code == 200
    assert admin.get(f"/board-patterns/{p['id']}").json()["exam_types"] == []


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A08")
@pytest.mark.xfail(strict=True, reason="DEF-EXM-1: PUT /board-patterns/{id} response returns the stale exam_types (old rows) instead of the replaced list")
def test_update_response_shows_replaced_exam_types(admin, cleanup):
    board, level = free_combos(admin)[0]
    p = make_pattern(admin, cleanup, board, level)
    new = [{"exam_type_name": "SA1", "nature": "summative", "weightage_percent": 40, "count_per_year": 1, "sort_order": 1}]
    response = admin.put(f"/board-patterns/{p['id']}", json={"exam_types": new})
    assert [t["exam_type_name"] for t in response.json()["exam_types"]] == ["SA1"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A09")
def test_update_to_existing_pair_conflicts(admin, cleanup):
    (b1, l1), (b2, l2) = free_combos(admin, count=2)
    make_pattern(admin, cleanup, b1, l1)
    p2 = make_pattern(admin, cleanup, b2, l2)
    response = admin.put(f"/board-patterns/{p2['id']}", json={"board": b1, "level": l1})
    assert response.status_code == 409


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A10")
def test_update_unknown(admin):
    assert admin.put(f"/board-patterns/{new_uuid()}", json={"is_active": False}).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A11")
def test_delete_unused_pattern(admin):
    board, level = free_combos(admin)[0]
    response = admin.post("/board-patterns", json={"board": board, "level": level, "exam_types": types(1)})
    pid = response.json()["id"]
    assert admin.delete(f"/board-patterns/{pid}").status_code == 204
    assert admin.get(f"/board-patterns/{pid}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A12")
def test_delete_pattern_in_use_by_exam(admin, world, cleanup):
    board, level = free_combos(admin)[0]
    p = make_pattern(admin, cleanup, board, level)
    create_exam(admin, cleanup, world, board=board, level=level)
    response = admin.delete(f"/board-patterns/{p['id']}")
    assert response.status_code == 409
    assert admin.get(f"/board-patterns/{p['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A13")
def test_delete_unknown(admin):
    assert admin.delete(f"/board-patterns/{new_uuid()}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A14")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_write_denied(role_clients, admin, cleanup, role):
    board, level = free_combos(admin)[0]
    p = make_pattern(admin, cleanup, board, level)
    client = role_clients[role]
    assert client.post("/board-patterns", json={"board": board, "level": "others", "exam_types": []}).status_code == 403
    assert client.put(f"/board-patterns/{p['id']}", json={"is_active": False}).status_code == 403
    assert client.delete(f"/board-patterns/{p['id']}").status_code == 403
    assert admin.get(f"/board-patterns/{p['id']}").json()["is_active"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A15")
@pytest.mark.parametrize("role", ALL_ROLES)
def test_read_all_roles(role_clients, admin, cleanup, role):
    board, level = free_combos(admin)[0]
    p = make_pattern(admin, cleanup, board, level)
    assert role_clients[role].get("/board-patterns").status_code == 200
    assert role_clients[role].get(f"/board-patterns/{p['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A16")
def test_unauthenticated(anon):
    pid = new_uuid()
    assert anon.get("/board-patterns").status_code == 401
    assert anon.get(f"/board-patterns/{pid}").status_code == 401
    assert anon.post("/board-patterns", json={"board": "CBSE", "level": "iit", "exam_types": []}).status_code == 401
    assert anon.put(f"/board-patterns/{pid}", json={"is_active": False}).status_code == 401
    assert anon.delete(f"/board-patterns/{pid}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A17")
def test_tenant_isolation(admin, tenant_b, cleanup):
    board, level = free_combos(admin, tenant_b)[0]
    p = make_pattern(admin, cleanup, board, level)
    assert p["id"] not in {x["id"] for x in items_of(tenant_b.get("/board-patterns"))}
    assert tenant_b.get(f"/board-patterns/{p['id']}").status_code == 404
    assert tenant_b.put(f"/board-patterns/{p['id']}", json={"is_active": False}).status_code == 404
    assert tenant_b.delete(f"/board-patterns/{p['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A18")
def test_same_pair_in_both_tenants(admin, tenant_b, cleanup):
    board, level = free_combos(admin, tenant_b)[0]
    make_pattern(admin, cleanup, board, level)
    make_pattern(tenant_b, cleanup, board, level)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-02-A19")
def test_cschema_mismatch(foreign):
    assert foreign.post("/board-patterns", json={"board": "CBSE", "level": "iit", "exam_types": []}).status_code == 403
