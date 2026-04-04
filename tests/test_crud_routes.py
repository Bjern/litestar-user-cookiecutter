import os

os.environ.setdefault("ENCODING_SECRET", "test-secret-key-32-characters!!!")
os.environ.setdefault("AUTO_VERIFY_USERS", "true")

import pytest
from advanced_alchemy.base import UUIDBase
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig, SQLAlchemyInitPlugin
from litestar import Litestar
from litestar.testing import TestClient
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.crud import CRUDMixin, CRUDPlugin
from app.lib.crud.service import CRUDService
from app.lib.security import litestar_users
from tests.conftest import USER_EMAIL, USER_PASSWORD


class TitleCaseService(CRUDService):  # type: ignore[type-arg]
    """Test service that title-cases the name field on create."""

    async def before_create(self, data: dict) -> dict:
        if "name" in data:
            data["name"] = data["name"].title()
        return data


class Item(UUIDBase, CRUDMixin):
    __tablename__ = "test_item"
    name: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    class CRUDMeta:
        operations = {"create", "read", "list", "update", "delete"}
        tags = ["Test Items"]
        filterable_fields = {"active"}
        public_operations = {"list", "read"}


class ReadOnlyItem(UUIDBase, CRUDMixin):
    __tablename__ = "test_readonly_item"
    label: Mapped[str] = mapped_column(String(100))

    class CRUDMeta:
        operations = {"read", "list"}
        path = "/readonly"
        tags = ["Read Only"]
        public_operations = {"read", "list"}


class NoCrudModel(UUIDBase, CRUDMixin):
    __tablename__ = "test_no_crud"
    value: Mapped[str] = mapped_column(String(100))


class HookedItem(UUIDBase, CRUDMixin):
    """Test model with a custom service."""

    __tablename__ = "test_hooked_item"

    name: Mapped[str] = mapped_column(String(100))

    class CRUDMeta:
        operations = {"create", "read"}
        service_class = TitleCaseService
        public_operations = {"create", "read"}


@pytest.fixture()
def crud_client():
    db_config = SQLAlchemyAsyncConfig(
        connection_string="sqlite+aiosqlite://",
        session_dependency_key="session",
        before_send_handler="autocommit",
        create_all=True,
        metadata=UUIDBase.metadata,
    )
    db_plugin = SQLAlchemyInitPlugin(config=db_config)
    crud_plugin = CRUDPlugin()

    app = Litestar(
        route_handlers=[],
        plugins=[db_plugin, crud_plugin, litestar_users],
    )

    with TestClient(app=app) as tc:
        yield tc


@pytest.fixture()
def authenticated_crud_client(crud_client: TestClient) -> TestClient:
    crud_client.post("/register", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    crud_client.post("/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    return crud_client


def test_list_items_empty(crud_client: TestClient) -> None:
    resp = crud_client.get("/test-items")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


def test_list_is_public(crud_client: TestClient) -> None:
    resp = crud_client.get("/test-items")
    assert resp.status_code == 200


def test_create_item_requires_auth(crud_client: TestClient) -> None:
    resp = crud_client.post("/test-items", json={"name": "test", "active": True})
    assert resp.status_code == 401


def test_create_item(authenticated_crud_client: TestClient) -> None:
    resp = authenticated_crud_client.post("/test-items", json={"name": "test", "active": True})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test"
    assert data["active"] is True
    assert "id" in data


def test_read_nonexistent(crud_client: TestClient) -> None:
    resp = crud_client.get("/test-items/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_update_item_requires_auth(crud_client: TestClient) -> None:
    resp = crud_client.patch(
        "/test-items/00000000-0000-0000-0000-000000000000",
        json={"name": "updated"},
    )
    assert resp.status_code == 401


def test_delete_item_requires_auth(crud_client: TestClient) -> None:
    resp = crud_client.delete("/test-items/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401


def test_readonly_custom_path(crud_client: TestClient) -> None:
    resp = crud_client.get("/readonly")
    assert resp.status_code == 200


def test_readonly_no_create(crud_client: TestClient) -> None:
    resp = crud_client.post("/readonly", json={"label": "test"})
    assert resp.status_code == 405


def test_readonly_no_delete(crud_client: TestClient) -> None:
    resp = crud_client.delete("/readonly/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 405


def test_no_crud_model_has_no_routes(crud_client: TestClient) -> None:
    resp = crud_client.get("/test-no-cruds")
    assert resp.status_code == 404


def test_list_pagination_params(crud_client: TestClient) -> None:
    resp = crud_client.get("/test-items?limit=5&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 5
    assert data["offset"] == 0


def test_full_crud_lifecycle(authenticated_crud_client: TestClient) -> None:
    """Test create → read → update → list → delete → confirm gone."""
    client = authenticated_crud_client

    # Create
    resp = client.post("/test-items", json={"name": "Lifecycle Item", "active": True})
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    # Read
    resp = client.get(f"/test-items/{item_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Lifecycle Item"

    # Update
    resp = client.patch(f"/test-items/{item_id}", json={"name": "Updated Item"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Item"

    # List (should contain the item)
    resp = client.get("/test-items")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Delete
    resp = client.delete(f"/test-items/{item_id}")
    assert resp.status_code == 204

    # Confirm gone
    resp = client.get(f"/test-items/{item_id}")
    assert resp.status_code == 404


def test_custom_service_hook_transforms_data(crud_client: TestClient) -> None:
    resp = crud_client.post("/test-hooked-items", json={"name": "hello world"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Hello World"
