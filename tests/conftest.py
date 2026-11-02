from datetime import date

import pytest

from emporio.config import PROJECT_ROOT
from emporio.data import StoreData, load_store_data

REFERENCE_DATE = date(2026, 3, 25)


@pytest.fixture(scope="session")
def store() -> StoreData:
    return load_store_data(PROJECT_ROOT / "data")
