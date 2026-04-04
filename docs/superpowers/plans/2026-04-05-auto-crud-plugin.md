# Auto-CRUD Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Litestar plugin that auto-generates CRUD API endpoints from SQLAlchemy model definitions using a `CRUDMixin` + `CRUDMeta` pattern.

**Architecture:** A Litestar `InitPlugin` that discovers models under `app/domain/*/models.py` at startup, introspects their `CRUDMeta` configuration, auto-generates DTOs and route handlers, and registers them with the app. Uses Advanced Alchemy's `SQLAlchemyAsyncRepository` for database operations wrapped in a `CRUDService` with lifecycle hooks.

**Tech Stack:** Litestar 2.x, Advanced Alchemy (SQLAlchemyAsyncRepository, SQLAlchemyDTO), SQLAlchemy 2.0, Pydantic v2, pytest

**Spec:** `docs/superpowers/specs/2026-04-05-auto-crud-plugin-design.md`

---

## File Map

| File | Responsibility |
|------|----------------|
| Create: `app/lib/crud/__init__.py` | Package init, public exports |
| Create: `app/lib/crud/mixin.py` | `CRUDMixin` class with default `CRUDMeta` |
| Create: `app/lib/crud/discovery.py` | `discover_models()` — scans `app/domain/*/models.py` |
| Create: `app/lib/crud/service.py` | `CRUDService[T]` with before/after lifecycle hooks |
| Create: `app/lib/crud/pagination.py` | `PaginatedResponse` schema + query param parsing |
| Create: `app/lib/crud/routes.py` | Handler factory functions per CRUD operation |
| Create: `app/lib/crud/plugin.py` | `CRUDPlugin(InitPlugin)` — orchestrates discovery + route registration |
| Modify: `app/main.py` | Add `CRUDPlugin` to plugins list |
| Modify: `alembic/env.py` | Replace manual model import with `discover_models()` |
| Create: `tests/test_crud_mixin.py` | Tests for CRUDMixin defaults and config |
| Create: `tests/test_crud_discovery.py` | Tests for model discovery |
| Create: `tests/test_crud_routes.py` | Tests for generated CRUD endpoints |
| Create: `tests/test_crud_service.py` | Tests for service hooks |
| Create: `tests/test_crud_pagination.py` | Tests for pagination + filtering |

---

### Task 1: CRUDMixin and CRUDMeta defaults

**Files:**
- Create: `app/lib/crud/__init__.py`
- Create: `app/lib/crud/mixin.py`
- Create: `tests/test_crud_mixin.py`

- [ ] **Step 1: Write failing tests for CRUDMixin**

```python
# tests/test_crud_mixin.py
from advanced_alchemy.base import UUIDBase
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.crud.mixin import CRUDMixin


class MinimalModel(UUIDBase, CRUDMixin):
    name: Mapped[str] = mapped_column(String(100))


class ConfiguredModel(UUIDBase, CRUDMixin):
    name: Mapped[str] = mapped_column(String(100))

    class CRUDMeta:
        operations = {"create", "read", "list"}
        path = "/widgets"
        tags = ["Widgets"]
        exclude_fields = {"sa_orm_sentinel", "name"}
        public_operations = {"list"}
        filterable_fields = {"name"}


def test_default_meta_has_empty_operations() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.operations == set()


def test_default_meta_path_is_none() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.path is None


def test_default_meta_tags_is_none() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.tags is None


def test_default_meta_exclude_fields() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.exclude_fields == {"sa_orm_sentinel"}


def test_default_meta_public_operations_empty() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.public_operations == set()


def test_default_meta_filterable_fields_empty() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.filterable_fields == set()


def test_default_meta_service_class_is_none() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.service_class is None


def test_configured_meta_overrides() -> None:
    meta = ConfiguredModel.CRUDMeta
    assert meta.operations == {"create", "read", "list"}
    assert meta.path == "/widgets"
    assert meta.tags == ["Widgets"]
    assert meta.exclude_fields == {"sa_orm_sentinel", "name"}
    assert meta.public_operations == {"list"}
    assert meta.filterable_fields == {"name"}


def test_crud_mixin_is_subclass_check() -> None:
    assert issubclass(MinimalModel, CRUDMixin)
    assert not issubclass(UUIDBase, CRUDMixin)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_crud_mixin.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.lib.crud'`

- [ ] **Step 3: Implement CRUDMixin**

```python
# app/lib/crud/__init__.py
from app.lib.crud.mixin import CRUDMixin

__all__ = ["CRUDMixin"]
```

```python
# app/lib/crud/mixin.py


class CRUDMeta:
    """Default CRUDMeta configuration. Models override this via inner class."""

    operations: set[str] = set()
    path: str | None = None
    tags: list[str] | None = None
    exclude_fields: set[str] = {"sa_orm_sentinel"}
    public_operations: set[str] = set()
    filterable_fields: set[str] = set()
    service_class: type | None = None


class CRUDMixin:
    """Mixin that marks a model for auto-CRUD route generation.

    Define an inner CRUDMeta class to configure which operations to generate.
    Without CRUDMeta (or with empty operations), no routes are generated.
    """

    CRUDMeta: type = CRUDMeta
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_crud_mixin.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/lib/crud/__init__.py app/lib/crud/mixin.py tests/test_crud_mixin.py
git commit -m "feat(crud): add CRUDMixin with CRUDMeta defaults"
```

---

### Task 2: Model Discovery

**Files:**
- Create: `app/lib/crud/discovery.py`
- Create: `tests/test_crud_discovery.py`

- [ ] **Step 1: Write failing tests for discover_models**

```python
# tests/test_crud_discovery.py
from app.lib.crud.discovery import discover_models
from app.lib.crud.mixin import CRUDMixin


def test_discover_finds_no_crud_models_when_none_have_operations() -> None:
    """User model has no CRUDMixin, default domain has no model."""
    models = discover_models()
    assert all(issubclass(m, CRUDMixin) for m in models)
    # All discovered models must have non-empty operations
    assert all(m.CRUDMeta.operations for m in models)


def test_discover_imports_all_domain_models() -> None:
    """Calling discover_models imports all models.py files.
    After calling, UUIDBase.__subclasses__() should include User."""
    from advanced_alchemy.base import UUIDBase

    discover_models()
    subclass_names = {cls.__name__ for cls in UUIDBase.__subclasses__()}
    assert "User" in subclass_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_crud_discovery.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.lib.crud.discovery'`

- [ ] **Step 3: Implement discover_models**

```python
# app/lib/crud/discovery.py
from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from advanced_alchemy.base import UUIDBase

from app.lib.crud.mixin import CRUDMixin

if TYPE_CHECKING:
    pass


def discover_models(domain_path: str = "app/domain") -> list[type]:
    """Import all models.py under app/domain/*, return CRUDMixin models with operations."""
    domain_root = Path(domain_path)
    for subdir in sorted(domain_root.iterdir()):
        if subdir.is_dir() and (subdir / "models.py").exists():
            module_name = f"app.domain.{subdir.name}.models"
            importlib.import_module(module_name)

    return [
        cls
        for cls in UUIDBase.__subclasses__()
        if issubclass(cls, CRUDMixin) and cls.CRUDMeta.operations
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_crud_discovery.py -v`
Expected: All PASS

- [ ] **Step 5: Update alembic/env.py to use discover_models**

Replace the manual model import in `alembic/env.py`:

```python
# alembic/env.py — change this:
# from app.domain.users.models import User  # noqa: F401
# to this:
from app.lib.crud.discovery import discover_models  # noqa: F401

discover_models()
```

- [ ] **Step 6: Verify alembic still works**

Run: `uv run alembic current`
Expected: Shows current migration head, no errors

- [ ] **Step 7: Commit**

```bash
git add app/lib/crud/discovery.py tests/test_crud_discovery.py alembic/env.py
git commit -m "feat(crud): add model discovery and update alembic env"
```

---

### Task 3: CRUDService with lifecycle hooks

**Files:**
- Create: `app/lib/crud/service.py`
- Create: `tests/test_crud_service.py`

- [ ] **Step 1: Write failing tests for CRUDService**

```python
# tests/test_crud_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.lib.crud.service import CRUDService


@pytest.fixture()
def mock_repository() -> MagicMock:
    repo = MagicMock()
    repo.add = AsyncMock()
    repo.get = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_before_create_returns_data_unchanged(mock_repository: MagicMock) -> None:
    service = CRUDService(session=MagicMock(), repository=mock_repository)
    data = {"name": "Widget"}
    result = await service.before_create(data)
    assert result == {"name": "Widget"}


@pytest.mark.asyncio
async def test_after_create_is_noop(mock_repository: MagicMock) -> None:
    service = CRUDService(session=MagicMock(), repository=mock_repository)
    await service.after_create(MagicMock())  # should not raise


@pytest.mark.asyncio
async def test_before_update_returns_data_unchanged(mock_repository: MagicMock) -> None:
    service = CRUDService(session=MagicMock(), repository=mock_repository)
    data = {"name": "Updated"}
    result = await service.before_update(uuid4(), data)
    assert result == {"name": "Updated"}


@pytest.mark.asyncio
async def test_after_update_is_noop(mock_repository: MagicMock) -> None:
    service = CRUDService(session=MagicMock(), repository=mock_repository)
    await service.after_update(MagicMock())  # should not raise


@pytest.mark.asyncio
async def test_before_delete_is_noop(mock_repository: MagicMock) -> None:
    service = CRUDService(session=MagicMock(), repository=mock_repository)
    await service.before_delete(uuid4())  # should not raise


@pytest.mark.asyncio
async def test_after_delete_is_noop(mock_repository: MagicMock) -> None:
    service = CRUDService(session=MagicMock(), repository=mock_repository)
    await service.after_delete(uuid4())  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_crud_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.lib.crud.service'`

- [ ] **Step 3: Implement CRUDService**

```python
# app/lib/crud/service.py
from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from advanced_alchemy.repository._async import SQLAlchemyAsyncRepository

ModelT = TypeVar("ModelT")


class CRUDService(Generic[ModelT]):
    """Default CRUD service with lifecycle hooks.

    Override before_*/after_* methods for custom business logic.
    """

    def __init__(self, session: Any, repository: SQLAlchemyAsyncRepository[Any]) -> None:
        self.session = session
        self.repository = repository

    async def before_create(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    async def after_create(self, item: ModelT) -> None:
        pass

    async def before_update(self, id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        return data

    async def after_update(self, item: ModelT) -> None:
        pass

    async def before_delete(self, id: UUID) -> None:
        pass

    async def after_delete(self, id: UUID) -> None:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_crud_service.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/lib/crud/service.py tests/test_crud_service.py
git commit -m "feat(crud): add CRUDService with lifecycle hooks"
```

---

### Task 4: Pagination schema

**Files:**
- Create: `app/lib/crud/pagination.py`
- Create: `tests/test_crud_pagination.py`

- [ ] **Step 1: Write failing tests for pagination**

```python
# tests/test_crud_pagination.py
from app.lib.crud.pagination import PaginatedResponse


def test_paginated_response_schema() -> None:
    resp = PaginatedResponse[dict](
        items=[{"name": "a"}, {"name": "b"}],
        total=10,
        limit=20,
        offset=0,
    )
    assert resp.items == [{"name": "a"}, {"name": "b"}]
    assert resp.total == 10
    assert resp.limit == 20
    assert resp.offset == 0


def test_paginated_response_defaults() -> None:
    resp = PaginatedResponse[dict](items=[], total=0)
    assert resp.limit == 20
    assert resp.offset == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_crud_pagination.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement PaginatedResponse**

```python
# app/lib/crud/pagination.py
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    items: list[T]
    total: int
    limit: int = 20
    offset: int = 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_crud_pagination.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/lib/crud/pagination.py tests/test_crud_pagination.py
git commit -m "feat(crud): add PaginatedResponse schema"
```

---

### Task 5: Route handler factories

**Files:**
- Create: `app/lib/crud/routes.py`

This is the core of the plugin. Handler factories that produce Litestar route handlers from a model and its CRUDMeta. Testing is done via integration tests in Task 7.

- [ ] **Step 1: Implement route handler factories**

```python
# app/lib/crud/routes.py
from __future__ import annotations

from typing import Any
from uuid import UUID

from advanced_alchemy.extensions.litestar import SQLAlchemyDTO, SQLAlchemyDTOConfig
from advanced_alchemy.repository._async import SQLAlchemyAsyncRepository
from litestar import Router, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.lib.crud.mixin import CRUDMeta as DefaultCRUDMeta
from app.lib.crud.pagination import PaginatedResponse
from app.lib.crud.service import CRUDService


def _pluralize(name: str) -> str:
    """Naive pluralization for table names."""
    if name.endswith("s"):
        return name + "es"
    if name.endswith("y"):
        return name[:-1] + "ies"
    return name + "s"


def _get_meta_attr(meta: type, attr: str, default: Any) -> Any:
    """Get attribute from CRUDMeta, falling back to default."""
    return getattr(meta, attr, getattr(DefaultCRUDMeta, attr, default))


def _build_dtos(
    model: type, exclude_fields: set[str]
) -> tuple[type[SQLAlchemyDTO], type[SQLAlchemyDTO], type[SQLAlchemyDTO]]:  # type: ignore[type-arg]
    """Build Read, Create, and Update DTOs for a model."""
    read_dto = type(
        f"{model.__name__}ReadDTO",
        (SQLAlchemyDTO[model],),  # type: ignore[valid-type]
        {"config": SQLAlchemyDTOConfig(exclude=exclude_fields)},
    )
    create_dto = type(
        f"{model.__name__}CreateDTO",
        (SQLAlchemyDTO[model],),  # type: ignore[valid-type]
        {"config": SQLAlchemyDTOConfig(exclude=exclude_fields | {"id"})},
    )
    update_dto = type(
        f"{model.__name__}UpdateDTO",
        (SQLAlchemyDTO[model],),  # type: ignore[valid-type]
        {"config": SQLAlchemyDTOConfig(exclude=exclude_fields | {"id"}, partial=True)},
    )
    return read_dto, create_dto, update_dto


def _make_service_provider(
    model: type, service_class: type[CRUDService] | None  # type: ignore[type-arg]
) -> Any:
    """Create a dependency provider for the CRUD service."""
    svc_cls = service_class or CRUDService

    async def provide_crud_service(session: AsyncSession) -> CRUDService:  # type: ignore[type-arg]
        repository = SQLAlchemyAsyncRepository[model](  # type: ignore[valid-type]
            session=session,
            model_type=model,
        )
        return svc_cls(session=session, repository=repository)

    return provide_crud_service


def build_crud_router(model: type, meta: type) -> Router:
    """Build a Litestar Router with CRUD handlers for the given model."""
    operations: set[str] = _get_meta_attr(meta, "operations", set())
    path: str | None = _get_meta_attr(meta, "path", None)
    tags: list[str] | None = _get_meta_attr(meta, "tags", None)
    exclude_fields: set[str] = _get_meta_attr(meta, "exclude_fields", {"sa_orm_sentinel"})
    public_operations: set[str] = _get_meta_attr(meta, "public_operations", set())
    filterable_fields: set[str] = _get_meta_attr(meta, "filterable_fields", set())
    service_class: type | None = _get_meta_attr(meta, "service_class", None)

    if path is None:
        path = "/" + _pluralize(model.__tablename__)

    read_dto, create_dto, update_dto = _build_dtos(model, exclude_fields)
    service_provider = _make_service_provider(model, service_class)
    dependencies = {"service": Provide(service_provider, sync_to_thread=False)}

    handlers: list[Any] = []

    if "list" in operations:

        @get(
            path="/",
            return_dto=read_dto,
            dependencies=dependencies,
            exclude_from_auth="list" in public_operations,
            tags=tags,
        )
        async def list_handler(
            service: CRUDService,  # type: ignore[type-arg]
            limit: int = Parameter(default=20, ge=1, le=100, query="limit"),
            offset: int = Parameter(default=0, ge=0, query="offset"),
            **kwargs: Any,
        ) -> PaginatedResponse:  # type: ignore[type-arg]
            # Build filters from filterable fields
            filters = {k: v for k, v in kwargs.items() if k in filterable_fields and v is not None}
            if filters:
                items, total = await service.repository.list_and_count(
                    *[
                        getattr(model, field) == value
                        for field, value in filters.items()
                    ],
                    limit=limit,
                    offset=offset,
                )
            else:
                items, total = await service.repository.list_and_count(
                    limit=limit, offset=offset
                )
            return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

        # Inject filterable fields as optional query params
        if filterable_fields:
            from litestar.params import Parameter as LitestarParam
            import inspect

            sig = inspect.signature(list_handler.fn)  # type: ignore[union-attr]
            new_params = list(sig.parameters.values())
            # Remove **kwargs
            new_params = [p for p in new_params if p.kind != inspect.Parameter.VAR_KEYWORD]
            for field_name in sorted(filterable_fields):
                new_params.append(
                    inspect.Parameter(
                        field_name,
                        inspect.Parameter.KEYWORD_ONLY,
                        default=LitestarParam(default=None, query=field_name, required=False),
                        annotation=str | None,
                    )
                )
            list_handler.fn.__signature__ = sig.replace(parameters=new_params)  # type: ignore[union-attr]

        handlers.append(list_handler)

    if "create" in operations:

        @post(
            path="/",
            dto=create_dto,
            return_dto=read_dto,
            dependencies=dependencies,
            exclude_from_auth="create" in public_operations,
            tags=tags,
        )
        async def create_handler(
            data: model,  # type: ignore[valid-type]
            service: CRUDService,  # type: ignore[type-arg]
        ) -> model:  # type: ignore[valid-type]
            processed = await service.before_create(
                {c.key: getattr(data, c.key) for c in data.__table__.columns if hasattr(data, c.key)}  # type: ignore[union-attr]
            )
            for key, value in processed.items():
                setattr(data, key, value)
            item = await service.repository.add(data)
            await service.session.flush()
            await service.after_create(item)
            return item

        handlers.append(create_handler)

    if "read" in operations:

        @get(
            path="/{item_id:uuid}",
            return_dto=read_dto,
            dependencies=dependencies,
            exclude_from_auth="read" in public_operations,
            tags=tags,
        )
        async def read_handler(
            item_id: UUID,
            service: CRUDService,  # type: ignore[type-arg]
        ) -> model:  # type: ignore[valid-type]
            return await service.repository.get(item_id)

        handlers.append(read_handler)

    if "update" in operations:

        @patch(
            path="/{item_id:uuid}",
            dto=update_dto,
            return_dto=read_dto,
            dependencies=dependencies,
            exclude_from_auth="update" in public_operations,
            tags=tags,
        )
        async def update_handler(
            item_id: UUID,
            data: model,  # type: ignore[valid-type]
            service: CRUDService,  # type: ignore[type-arg]
        ) -> model:  # type: ignore[valid-type]
            update_data = {
                c.key: getattr(data, c.key)
                for c in data.__table__.columns  # type: ignore[union-attr]
                if hasattr(data, c.key) and getattr(data, c.key) is not None
            }
            processed = await service.before_update(item_id, update_data)
            existing = await service.repository.get(item_id)
            for key, value in processed.items():
                setattr(existing, key, value)
            updated = await service.repository.update(existing)
            await service.session.flush()
            await service.after_update(updated)
            return updated

        handlers.append(update_handler)

    if "delete" in operations:

        @delete(
            path="/{item_id:uuid}",
            dependencies=dependencies,
            exclude_from_auth="delete" in public_operations,
            tags=tags,
        )
        async def delete_handler(
            item_id: UUID,
            service: CRUDService,  # type: ignore[type-arg]
        ) -> None:
            await service.before_delete(item_id)
            await service.repository.delete(item_id)
            await service.session.flush()
            await service.after_delete(item_id)

        handlers.append(delete_handler)

    return Router(path=path, route_handlers=handlers)
```

- [ ] **Step 2: Commit**

```bash
git add app/lib/crud/routes.py
git commit -m "feat(crud): add route handler factories"
```

---

### Task 6: CRUDPlugin

**Files:**
- Create: `app/lib/crud/plugin.py`
- Modify: `app/lib/crud/__init__.py`

- [ ] **Step 1: Implement CRUDPlugin**

```python
# app/lib/crud/plugin.py
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from litestar.plugins import InitPlugin

from app.lib.crud.discovery import discover_models
from app.lib.crud.routes import build_crud_router

if TYPE_CHECKING:
    from litestar.config.app import AppConfig


class CRUDPlugin(InitPlugin):
    """Litestar plugin that auto-generates CRUD routes from CRUDMixin models."""

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        models = discover_models()
        for model in models:
            router = build_crud_router(model, model.CRUDMeta)
            app_config.route_handlers.append(router)
            logger.info(
                "crud.registered | model={model} path={path} operations={ops}",
                model=model.__name__,
                path=router.path,
                ops=model.CRUDMeta.operations,
            )
        return app_config
```

- [ ] **Step 2: Update __init__.py exports**

```python
# app/lib/crud/__init__.py
from app.lib.crud.mixin import CRUDMixin
from app.lib.crud.plugin import CRUDPlugin
from app.lib.crud.service import CRUDService

__all__ = ["CRUDMixin", "CRUDPlugin", "CRUDService"]
```

- [ ] **Step 3: Commit**

```bash
git add app/lib/crud/plugin.py app/lib/crud/__init__.py
git commit -m "feat(crud): add CRUDPlugin"
```

---

### Task 7: Wire plugin into app and integration tests

**Files:**
- Modify: `app/main.py`
- Create: `tests/test_crud_routes.py`

- [ ] **Step 1: Add CRUDPlugin to main.py**

In `app/main.py`, add the import and plugin:

```python
# Add import:
from app.lib.crud.plugin import CRUDPlugin

# Add to plugins list:
crud_plugin = CRUDPlugin()

app = Litestar(
    route_handlers=[default_router],
    openapi_config=openapi_config,
    plugins=[db_plugin, crud_plugin, litestar_users],
)
```

- [ ] **Step 2: Write integration tests with a test model**

```python
# tests/test_crud_routes.py
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
from app.lib.security import litestar_users


class Item(UUIDBase, CRUDMixin):
    """Test model for CRUD integration tests."""

    __tablename__ = "test_item"

    name: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    class CRUDMeta:
        operations = {"create", "read", "list", "update", "delete"}
        tags = ["Test Items"]
        filterable_fields = {"active"}
        public_operations = {"list", "read"}


class ReadOnlyItem(UUIDBase, CRUDMixin):
    """Test model with read-only config."""

    __tablename__ = "test_readonly_item"

    label: Mapped[str] = mapped_column(String(100))

    class CRUDMeta:
        operations = {"read", "list"}
        path = "/readonly"
        tags = ["Read Only"]


class NoCrudModel(UUIDBase, CRUDMixin):
    """Test model with no operations — should generate no routes."""

    __tablename__ = "test_no_crud"

    value: Mapped[str] = mapped_column(String(100))


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


# --- List ---


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
    assert resp.status_code == 200  # no auth needed


# --- Create ---


def test_create_item_requires_auth(crud_client: TestClient) -> None:
    resp = crud_client.post("/test-items", json={"name": "Widget", "active": True})
    assert resp.status_code == 401


def test_create_item(authenticated_crud_client: TestClient) -> None:
    resp = authenticated_crud_client.post("/test-items", json={"name": "Widget", "active": True})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Widget"
    assert data["active"] is True
    assert "id" in data


# --- Read ---


def test_read_nonexistent(crud_client: TestClient) -> None:
    resp = crud_client.get("/test-items/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# --- Update ---


def test_update_item_requires_auth(crud_client: TestClient) -> None:
    resp = crud_client.patch(
        "/test-items/00000000-0000-0000-0000-000000000000",
        json={"name": "Updated"},
    )
    assert resp.status_code == 401


# --- Delete ---


def test_delete_item_requires_auth(crud_client: TestClient) -> None:
    resp = crud_client.delete("/test-items/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401


# --- Custom path ---


def test_readonly_custom_path(crud_client: TestClient) -> None:
    resp = crud_client.get("/readonly")
    assert resp.status_code == 200


def test_readonly_no_create(crud_client: TestClient) -> None:
    resp = crud_client.post("/readonly", json={"label": "test"})
    assert resp.status_code == 405  # Method Not Allowed


def test_readonly_no_delete(crud_client: TestClient) -> None:
    resp = crud_client.delete("/readonly/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 405


# --- No CRUD model ---


def test_no_crud_model_has_no_routes(crud_client: TestClient) -> None:
    resp = crud_client.get("/test-no-cruds")
    assert resp.status_code == 404


# --- Pagination ---


def test_list_pagination_params(crud_client: TestClient) -> None:
    resp = crud_client.get("/test-items?limit=5&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 5
    assert data["offset"] == 0


# --- Filtering ---


def test_list_filter_by_active(crud_client: TestClient) -> None:
    resp = crud_client.get("/test-items?active=true")
    assert resp.status_code == 200
```

- [ ] **Step 3: Add authenticated_crud_client fixture**

Add to `tests/test_crud_routes.py` after the `crud_client` fixture:

```python
from tests.conftest import USER_EMAIL, USER_PASSWORD


@pytest.fixture()
def authenticated_crud_client(crud_client: TestClient) -> TestClient:
    """Register and login a user for auth-required CRUD operations."""
    crud_client.post("/register", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    crud_client.post("/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    return crud_client
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_crud_routes.py -v`
Expected: All PASS (some tests may need adjustment based on actual handler behavior)

- [ ] **Step 5: Fix any failing tests**

Iterate on the route factories (`app/lib/crud/routes.py`) and tests until all pass. Common issues:
- DTO class creation syntax for dynamic models
- Repository initialization parameters
- Session flush/commit timing with autocommit handler

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS (existing 19 + new CRUD tests)

- [ ] **Step 7: Run linters**

Run: `uv run ruff check . && uv run mypy app/`
Expected: No errors

- [ ] **Step 8: Commit**

```bash
git add app/main.py tests/test_crud_routes.py
git commit -m "feat(crud): wire plugin into app with integration tests"
```

---

### Task 8: Full CRUD flow end-to-end test

**Files:**
- Modify: `tests/test_crud_routes.py`

- [ ] **Step 1: Add complete CRUD lifecycle test**

Add to `tests/test_crud_routes.py`:

```python
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
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_crud_routes.py::test_full_crud_lifecycle -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_crud_routes.py
git commit -m "test(crud): add full CRUD lifecycle integration test"
```

---

### Task 9: Custom service hook test

**Files:**
- Modify: `tests/test_crud_routes.py`

- [ ] **Step 1: Add a test model with custom service**

Add to `tests/test_crud_routes.py`:

```python
from app.lib.crud.service import CRUDService


class TitleCaseService(CRUDService):  # type: ignore[type-arg]
    """Test service that title-cases the name field on create."""

    async def before_create(self, data: dict) -> dict:
        if "name" in data:
            data["name"] = data["name"].title()
        return data


class HookedItem(UUIDBase, CRUDMixin):
    """Test model with a custom service."""

    __tablename__ = "test_hooked_item"

    name: Mapped[str] = mapped_column(String(100))

    class CRUDMeta:
        operations = {"create", "read"}
        service_class = TitleCaseService
        public_operations = {"create", "read"}
```

- [ ] **Step 2: Add the test**

```python
def test_custom_service_hook_transforms_data(crud_client: TestClient) -> None:
    resp = crud_client.post("/test-hooked-items", json={"name": "hello world"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Hello World"
```

- [ ] **Step 3: Run the test**

Run: `uv run pytest tests/test_crud_routes.py::test_custom_service_hook_transforms_data -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_crud_routes.py
git commit -m "test(crud): add custom service hook test"
```

---

### Task 10: Final verification and cleanup

**Files:**
- Modify: `app/lib/crud/__init__.py` (if needed)

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run linters**

Run: `uv run ruff check .`
Expected: No errors

- [ ] **Step 3: Run type checker**

Run: `uv run mypy app/`
Expected: No errors

- [ ] **Step 4: Verify Alembic still works**

Run: `uv run alembic current`
Expected: Shows current head, no errors

- [ ] **Step 5: Manual smoke test (optional)**

Create a quick test model to verify Swagger shows routes:

```bash
# Create a temporary products domain
mkdir -p app/domain/products
touch app/domain/products/__init__.py
```

Create `app/domain/products/models.py`:
```python
from advanced_alchemy.base import UUIDBase
from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.crud.mixin import CRUDMixin


class Product(UUIDBase, CRUDMixin):
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)

    class CRUDMeta:
        operations = {"create", "read", "list", "update", "delete"}
        tags = ["Products"]
```

Then:
```bash
uv run alembic revision --autogenerate -m "add products"
uv run alembic upgrade head
uv run litestar run --reload
# Check http://localhost:8000/schema/swagger for Products endpoints
```

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat(crud): complete auto-CRUD plugin implementation"
```
