import pytest

from api_tests.masters.helpers import get_pool


@pytest.fixture(scope="session")
def pool(admin):
    return get_pool(admin)
