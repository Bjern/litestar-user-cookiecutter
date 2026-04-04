# Auto-CRUD Plugin Design

## Context

This project is a Litestar cookiecutter with user auth via litestar-users. Adding new domain entities currently requires manually creating models, schemas, DTOs, services, and route files. The goal is a plugin that auto-generates CRUD API endpoints from model definitions alone — the developer creates a model file with a mixin, runs migrations, and routes appear in Swagger.

## Design

### CRUDMixin and CRUDMeta

A model opts into CRUD by inheriting `CRUDMixin` and defining an inner `CRUDMeta` class. All `CRUDMeta` attributes have defaults, but `operations` defaults to empty — nothing is generated unless explicitly requested.

```python
# app/domain/products/models.py
from advanced_alchemy.base import UUIDBase
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, Boolean

from app.lib.crud.mixin import CRUDMixin


class Product(UUIDBase, CRUDMixin):
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    class CRUDMeta:
        operations = {"create", "read", "list"}
        tags = ["Products"]
```

**CRUDMeta attributes and defaults:**

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `operations` | `set[str]` | `set()` | Which endpoints to generate: `create`, `read`, `list`, `update`, `delete` |
| `path` | `str \| None` | `None` | URL prefix. `None` auto-pluralizes the table name (e.g. `product` → `/products`) |
| `tags` | `list[str] \| None` | `None` | Swagger tags for grouping |
| `exclude_fields` | `set[str]` | `{"sa_orm_sentinel"}` | Fields excluded from all DTOs |
| `public_operations` | `set[str]` | `set()` | Operations that skip auth (`exclude_from_auth=True`). All others require auth via the app-level session middleware. |
| `filterable_fields` | `set[str]` | `set()` | Model columns exposed as query params on the list endpoint (exact match, AND-ed) |
| `service_class` | `type \| None` | `None` | Custom service class. `None` uses the default `CRUDService` |

### Model Discovery

A shared function that scans `app/domain/*/models.py` by convention, imports each module, and returns all `CRUDMixin` subclasses. Used by both the CRUD plugin and Alembic.

```python
# app/lib/crud/discovery.py

def discover_models(domain_path: str = "app/domain") -> list[type]:
    """Import all models.py under app/domain/*, return CRUDMixin subclasses."""
```

The function:
1. Globs for `app/domain/*/models.py`
2. Calls `importlib.import_module()` on each
3. Returns `[cls for cls in UUIDBase.__subclasses__() if issubclass(cls, CRUDMixin) and cls.CRUDMeta.operations]`

`CRUDMixin` provides a default `CRUDMeta` with empty `operations`, so inheriting the mixin without defining `CRUDMeta` is safe — the model is simply skipped (no operations = no routes).

Side effect: all models (including non-CRUD ones like `User`) register with `UUIDBase.metadata`, which Alembic needs.

Alembic's `env.py` replaces manual model imports with:
```python
from app.lib.crud.discovery import discover_models
discover_models()
```

### Generated Endpoints

Per model, based on `CRUDMeta.operations`:

| Operation | Method | Path | Description |
|-----------|--------|------|-------------|
| `list` | GET | `/{path}` | Paginated list with optional filters |
| `create` | POST | `/{path}` | Create one record |
| `read` | GET | `/{path}/{id:uuid}` | Get by ID |
| `update` | PATCH | `/{path}/{id:uuid}` | Partial update |
| `delete` | DELETE | `/{path}/{id:uuid}` | Delete by ID |

### DTOs

Auto-generated from the model at route registration time using `SQLAlchemyDTO`:

- **ReadDTO**: excludes `CRUDMeta.exclude_fields`
- **CreateDTO**: excludes `CRUDMeta.exclude_fields` + `{"id"}`
- **UpdateDTO**: excludes `CRUDMeta.exclude_fields` + `{"id"}`, `partial=True`

No manual schema files needed.

### Pagination

List endpoints return a paginated response:

```json
{
  "items": [...],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

Query params: `?limit=20&offset=0` (defaults: limit=20, offset=0).

### Filtering

When `filterable_fields` is set, those columns become optional query params on the list endpoint:

```python
class CRUDMeta:
    operations = {"list"}
    filterable_fields = {"is_available", "name"}

# GET /products?is_available=true&name=Widget
```

Filters are exact match, AND-ed together. Non-filterable columns are not exposed as query params.

### Auth

All generated routes require auth by default (enforced by the app-level litestar-users session middleware). Operations listed in `public_operations` are marked with `exclude_from_auth=True`:

```python
class CRUDMeta:
    operations = {"create", "read", "list"}
    public_operations = {"read", "list"}
# read and list are public, create requires auth
```

### Service Layer

A default `CRUDService` wraps Advanced Alchemy's `SQLAlchemyAsyncRepositoryService` with lifecycle hooks:

```python
class CRUDService(SQLAlchemyAsyncRepositoryService[T]):
    async def before_create(self, data: dict) -> dict:
        return data

    async def after_create(self, item: T) -> None:
        pass

    async def before_update(self, id, data: dict) -> dict:
        return data

    async def after_update(self, item: T) -> None:
        pass

    async def before_delete(self, id) -> None:
        pass

    async def after_delete(self, id) -> None:
        pass
```

When `CRUDMeta.service_class = None`, the plugin creates a `CRUDService[Model]` at registration time. To add custom logic, the developer creates a service class in their domain folder and points to it:

```python
# app/domain/products/services.py
from app.lib.crud.service import CRUDService
from app.domain.products.models import Product

class ProductService(CRUDService[Product]):
    async def before_create(self, data: dict) -> dict:
        data["name"] = data["name"].strip().title()
        return data
```

```python
# In model:
class CRUDMeta:
    service_class = ProductService
```

### Plugin

The CRUD plugin implements Litestar's `InitPluginProtocol`. On app init, it discovers models, generates routes, and appends them to the app config:

```python
class CRUDPlugin(InitPluginProtocol):
    def on_app_init(self, app_config):
        models = discover_models()
        for model in models:
            meta = model.CRUDMeta
            router = build_crud_router(model, meta)
            app_config.route_handlers.append(router)
        return app_config
```

Wired in `main.py`:

```python
from app.lib.crud.plugin import CRUDPlugin

crud_plugin = CRUDPlugin()

app = Litestar(
    route_handlers=[default_router],
    plugins=[db_plugin, crud_plugin, litestar_users],
)
```

### File Structure

```
app/lib/crud/
    __init__.py
    mixin.py          # CRUDMixin base class, CRUDMeta defaults
    discovery.py      # discover_models() — scans app/domain/*/models.py
    plugin.py         # CRUDPlugin — Litestar plugin, orchestrates everything
    routes.py         # Handler factory functions per operation
    service.py        # CRUDService[T] with before/after hooks
    pagination.py     # Pagination response schema + query param handling
```

### Developer Workflow

Adding a new CRUD domain:

1. `mkdir app/domain/products` + create `__init__.py`
2. Create `app/domain/products/models.py` with model + `CRUDMixin` + `CRUDMeta`
3. `uv run alembic revision --autogenerate -m "add products"`
4. `uv run alembic upgrade head`
5. Start app — routes appear in Swagger under configured tags

No routes.py, schemas.py, or service file needed unless custom logic is required.

## Testing Strategy

Tests use the same pattern as the existing test suite: in-memory SQLite with `create_all=True`.

**Test files:**

| File | Covers |
|------|--------|
| `test_crud_discovery.py` | `discover_models` finds CRUDMixin models, ignores non-CRUD models |
| `test_crud_routes.py` | Only specified operations generate endpoints; correct methods/paths |
| `test_crud_service.py` | Default service works; custom service hooks fire; before/after lifecycle |
| `test_crud_pagination.py` | Default pagination; custom limit/offset; response shape |
| `test_crud_filtering.py` | Filterable fields become query params; non-filterable rejected |

**Key test cases:**

- Model with no `CRUDMeta` → no routes generated
- Model with empty `operations` → no routes generated
- Only specified operations produce endpoints (e.g. `{"read", "list"}` → no POST/PATCH/DELETE)
- `public_operations` correctly sets `exclude_from_auth=True`
- `exclude_fields` not present in response body
- Custom `path` overrides auto-pluralization
- Custom `service_class` hooks called in correct order
- Pagination defaults (limit=20, offset=0) and custom values
- Filterable fields generate query params; non-filterable don't
- Auto-generated DTOs exclude `id` from create, support partial on update

## Verification

1. Run `uv run pytest tests/ -v` — all existing + new tests pass
2. Create a test model with `CRUDMixin` in `app/domain/`, verify routes appear in Swagger
3. Exercise each CRUD operation via Swagger or `httpx`
4. Verify auth enforcement: public operations accessible without session, others return 401
5. Run `uv run mypy app/` — no type errors
6. Run `uv run ruff check .` — no lint errors
