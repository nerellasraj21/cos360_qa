import httpx
import pytest

from api_tests.auth.helpers import detail_text
from api_tests.support import API_URL
from api_tests.tenants_admin.conftest import MISSING_AUTH, ROLES, SA_REQUIRED

ROOT = API_URL[: -len("/api/v1")] if API_URL.endswith("/api/v1") else API_URL
HEALTH_PATHS = ["/super_admin/system/health", "/super_admin/auth/health", "/super_admin/system/usage-stats"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-11-A01")
def test_public_health_without_header():
    response = httpx.get(f"{ROOT}/health", timeout=30)
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.api
@pytest.mark.tc("TC-TEN-11-A02")
def test_system_health(superadmin):
    response = superadmin.get("/super_admin/system/health")
    assert response.status_code == 200
    body = response.json()
    assert body["total_tenants"] >= 2
    assert body["active_tenants"] <= body["total_tenants"]
    assert body["database_status"] == "connected"
    assert body["status"] == "healthy"
    assert body["system_version"] == "1.0.0"
    assert body["timestamp"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-11-A03")
def test_deactivating_a_tenant_lowers_active_count(superadmin, tmp_main):
    tmp_main.set_active(True)
    before = superadmin.get("/super_admin/system/health").json()
    tmp_main.set_active(False)
    try:
        after = superadmin.get("/super_admin/system/health").json()
    finally:
        tmp_main.set_active(True)
    assert after["active_tenants"] == before["active_tenants"] - 1
    assert after["total_tenants"] == before["total_tenants"]


@pytest.mark.api
@pytest.mark.tc("TC-TEN-11-A04")
def test_auth_health_same_shape(superadmin):
    response = superadmin.get("/super_admin/auth/health")
    assert response.status_code == 200
    assert set(response.json()) == set(superadmin.get("/super_admin/system/health").json())


@pytest.mark.api
@pytest.mark.tc("TC-TEN-11-A05")
@pytest.mark.xfail(strict=True, reason="TEN-USAGE-STATS: GET /super_admin/system/usage-stats answers 500 because the payload holds a SQL func.now() object that cannot be JSON-encoded")
def test_usage_stats(superadmin):
    response = superadmin.get("/super_admin/system/usage-stats")
    assert response.status_code == 200
    body = response.json()
    tenants = superadmin.get("/super_admin/system/tenants/?limit=500").json()["tenants"]
    assert body["system_overview"]["total_tenants"] == len(tenants)
    assert body["system_overview"]["active_tenants"] == len([t for t in tenants if t["is_active"]])
    assert {"total_super_admins", "actions_last_24h", "actions_last_7d"} <= set(body["super_admin_activity"])


@pytest.mark.api
@pytest.mark.tc("TC-TEN-11-A06")
@pytest.mark.parametrize("path", ["/health/status", "/health/metrics", "/health/metrics/summary", "/health/metrics/health"])
def test_unmounted_health_routes_404(anon, path):
    assert anon.get(path).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TEN-11-A07")
def test_alert_configuration_route_404(anon):
    response = anon.post("/health/metrics/alerts/configure", json={"threshold": 1})
    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-TEN-11-A08")
@pytest.mark.parametrize("role", ROLES)
def test_super_admin_monitoring_denied_to_tenant_roles(role_clients, role):
    for path in HEALTH_PATHS:
        response = role_clients[role].get(path)
        assert response.status_code == 403
        assert detail_text(response) == SA_REQUIRED


@pytest.mark.api
@pytest.mark.tc("TC-TEN-11-A09")
def test_super_admin_monitoring_requires_token(bare):
    for path in HEALTH_PATHS:
        response = bare.get(path)
        assert response.status_code == 401
        assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-11-A10")
def test_tenant_admin_monitoring_permission_has_no_effect(admin):
    for path in ("/health/status", "/health/metrics"):
        assert admin.get(path).status_code == 404
