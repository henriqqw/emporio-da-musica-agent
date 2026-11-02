import pytest

from emporio.catalog import Catalog
from emporio.complaints import ComplaintStore
from emporio.config import PROJECT_ROOT, Settings
from emporio.data import StoreData, load_store_data
from emporio.orders import OrderService
from emporio.tools import Toolbox
from tests.constants import REFERENCE_DATE


@pytest.fixture(scope="session")
def store() -> StoreData:
    return load_store_data(PROJECT_ROOT / "data")


@pytest.fixture
def complaints_path(tmp_path):
    return tmp_path / "complaints.jsonl"


@pytest.fixture
def toolbox(store, complaints_path) -> Toolbox:
    return Toolbox(Catalog(store), OrderService(store), ComplaintStore(complaints_path))


@pytest.fixture
def settings(complaints_path) -> Settings:
    """Settings for the whole app, with the LLM replaced by a fake in each test."""
    return Settings(
        model="fake-model",
        reference_date=REFERENCE_DATE,
        session_ttl_minutes=30,
        data_dir=PROJECT_ROOT / "data",
        complaints_path=complaints_path,
    )
