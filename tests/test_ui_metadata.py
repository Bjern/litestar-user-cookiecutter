import os

os.environ.setdefault("ENCODING_SECRET", "test-secret-key-32-characters!!!")
os.environ.setdefault("AUTO_VERIFY_USERS", "true")

import pytest
from advanced_alchemy.base import UUIDBase
from advanced_alchemy.extensions.litestar import (
    SQLAlchemyAsyncConfig,
    SQLAlchemyInitPlugin,
)
from litestar import Litestar
from litestar.testing import TestClient
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.crud import CRUDMixin, CRUDPlugin
from app.lib.security import litestar_users


class MetaModel(UUIDBase, CRUDMixin):
    """Test model with full UI metadata."""

    __tablename__ = "test_meta_model"
    name: Mapped[str] = mapped_column(String(100))

    class CRUDMeta:
        operations = {"list"}
        public_operations = {"list"}
        icon = "building"
        label = "Meta Models"
        field_order = ["name"]
        list_columns = ["name"]
        searchable_fields = ["name"]
        field_overrides = {"name": {"widget": "text", "group": "basic"}}


class PlainModel(UUIDBase, CRUDMixin):
    """Test model with no UI metadata."""

    __tablename__ = "test_plain_model"
    value: Mapped[str] = mapped_column(String(100))

    class CRUDMeta:
        operations = {"list"}
        public_operations = {"list"}


@pytest.fixture()
def meta_client():
    db_config = SQLAlchemyAsyncConfig(
        connection_string="sqlite+aiosqlite://",
        session_dependency_key="session",
        before_send_handler="autocommit",
        create_all=True,
        metadata=UUIDBase.metadata,
    )
    db_plugin = SQLAlchemyInitPlugin(config=db_config)
    crud_plugin = CRUDPlugin(models=[MetaModel, PlainModel])

    app = Litestar(
        route_handlers=[],
        plugins=[db_plugin, crud_plugin, litestar_users],
    )

    with TestClient(app=app) as tc:
        yield tc


def test_ui_metadata_returns_200(meta_client: TestClient) -> None:
    resp = meta_client.get("/schema/ui-metadata")
    assert resp.status_code == 200


def test_ui_metadata_is_public(meta_client: TestClient) -> None:
    """Endpoint is accessible without authentication."""
    resp = meta_client.get("/schema/ui-metadata")
    assert resp.status_code == 200


def test_ui_metadata_contains_model_with_metadata(meta_client: TestClient) -> None:
    data = meta_client.get("/schema/ui-metadata").json()
    assert "MetaModel" in data
    meta = data["MetaModel"]
    assert meta["icon"] == "building"
    assert meta["label"] == "Meta Models"
    assert meta["fieldOrder"] == ["name"]
    assert meta["listColumns"] == ["name"]
    assert meta["searchableFields"] == ["name"]
    assert meta["fieldOverrides"] == {"name": {"widget": "text", "group": "basic"}}


def test_ui_metadata_excludes_models_without_metadata(meta_client: TestClient) -> None:
    data = meta_client.get("/schema/ui-metadata").json()
    assert "PlainModel" not in data


def test_ui_metadata_camel_case_keys(meta_client: TestClient) -> None:
    data = meta_client.get("/schema/ui-metadata").json()
    meta = data["MetaModel"]
    assert "fieldOrder" in meta
    assert "listColumns" in meta
    assert "searchableFields" in meta
    assert "fieldOverrides" in meta
    # Ensure snake_case keys are NOT present
    assert "field_order" not in meta
    assert "list_columns" not in meta
    assert "searchable_fields" not in meta
    assert "field_overrides" not in meta
