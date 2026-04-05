from typing import Any
from uuid import UUID

from advanced_alchemy.extensions.litestar import SQLAlchemyDTO, SQLAlchemyDTOConfig
from advanced_alchemy.filters import LimitOffset
from advanced_alchemy.repository._async import SQLAlchemyAsyncRepository
from litestar import Router, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.lib.crud.mixin import CRUDMeta as DefaultCRUDMeta
from app.lib.crud.pagination import PaginatedResponse
from app.lib.crud.service import CRUDService


def _pluralize(name: str) -> str:
    """Convert a snake_case table name to a kebab-case plural path segment."""
    kebab = name.replace("_", "-")
    if kebab.endswith("s"):
        return kebab + "es"
    if kebab.endswith("y"):
        return kebab[:-1] + "ies"
    return kebab + "s"


def _get_meta_attr(meta: type, attr: str, default: Any) -> Any:
    """Get attribute from CRUDMeta, falling back to default."""
    return getattr(meta, attr, getattr(DefaultCRUDMeta, attr, default))


def _build_dtos(
    model: type, exclude_fields: set[str]
) -> tuple[type, type, type]:
    """Build Read, Create, and Update DTOs for a model."""
    base = SQLAlchemyDTO[model]  # type: ignore[valid-type]

    read_dto = type(
        f"{model.__name__}ReadDTO",
        (base,),
        {"config": SQLAlchemyDTOConfig(exclude=exclude_fields)},
    )
    create_dto = type(
        f"{model.__name__}CreateDTO",
        (base,),
        {"config": SQLAlchemyDTOConfig(exclude=exclude_fields | {"id"})},
    )
    update_dto = type(
        f"{model.__name__}UpdateDTO",
        (base,),
        {"config": SQLAlchemyDTOConfig(exclude=exclude_fields | {"id"}, partial=True)},
    )
    return read_dto, create_dto, update_dto


def _make_repository(model: type, session: AsyncSession) -> SQLAlchemyAsyncRepository:  # type: ignore[type-arg]
    """Create a repository instance for the given model and session."""

    class _Repo(SQLAlchemyAsyncRepository):  # type: ignore[type-arg]
        model_type = model

    return _Repo(session=session)


def _make_service_provider(
    model: type, service_class: type[CRUDService] | None  # type: ignore[type-arg]
) -> Any:
    """Create a dependency provider for the CRUD service."""
    svc_cls = service_class or CRUDService

    async def provide_crud_service(session: AsyncSession) -> CRUDService:  # type: ignore[type-arg]
        repository = _make_repository(model, session)
        return svc_cls(session=session, repository=repository)

    return provide_crud_service


def _model_to_dict(instance: Any, exclude_fields: set[str]) -> dict[str, Any]:
    """Convert a SQLAlchemy model instance to a plain dict, excluding specified fields."""
    return {
        c.key: getattr(instance, c.key)
        for c in instance.__table__.columns
        if c.key not in exclude_fields and hasattr(instance, c.key)
    }


def _make_list_handler(
    model: type,
    read_dto: type,
    exclude_fields: set[str],
    filterable_fields: set[str],
    dependencies: dict[str, Any],
    public: bool,
    tags: list[str] | None,
) -> Any:
    """Factory for list handler with pagination and optional filtering."""
    # Capture filterable_fields in closure for the handler
    _filterable = filterable_fields
    _model = model
    _exclude = exclude_fields

    @get(
        path="/",
        dependencies=dependencies,
        exclude_from_auth=public,
        tags=tags,
    )
    async def list_handler(
        service: CRUDService,  # type: ignore[type-arg]
        limit: int = Parameter(default=20, ge=1, le=100, query="limit"),
        offset: int = Parameter(default=0, ge=0, query="offset"),
        **kwargs: Any,
    ) -> PaginatedResponse:  # type: ignore[type-arg]
        filters_list: list[Any] = [LimitOffset(limit=limit, offset=offset)]
        for field_name in _filterable:
            value = kwargs.get(field_name)
            if value is not None:
                # Convert string booleans from query params
                col = getattr(_model, field_name)
                if str(value).lower() in ("true", "false"):
                    value = str(value).lower() == "true"
                filters_list.append(col == value)
        items, total = await service.repository.list_and_count(*filters_list)
        serialized = [_model_to_dict(item, _exclude) for item in items]
        return PaginatedResponse(items=serialized, total=total, limit=limit, offset=offset)

    # Add filterable fields to handler signature so Litestar exposes them as query params
    if _filterable:
        import inspect
        from litestar.params import Parameter as LitestarParam

        fn = list_handler.fn  # type: ignore[union-attr]
        sig = inspect.signature(fn)
        new_params = [p for p in sig.parameters.values() if p.kind != inspect.Parameter.VAR_KEYWORD]
        for field_name in sorted(_filterable):
            new_params.append(
                inspect.Parameter(
                    field_name,
                    inspect.Parameter.KEYWORD_ONLY,
                    default=LitestarParam(default=None, query=field_name, required=False),
                    annotation=str | None,
                )
            )
            fn.__annotations__[field_name] = str | None  # type: ignore[union-attr]
        fn.__signature__ = sig.replace(parameters=new_params)  # type: ignore[attr-defined]

    return list_handler


def _make_create_handler(
    model: type,
    create_dto: type,
    read_dto: type,
    dependencies: dict[str, Any],
    public: bool,
    tags: list[str] | None,
) -> Any:
    """Factory for create handler."""

    @post(
        path="/",
        dto=create_dto,
        return_dto=read_dto,
        dependencies=dependencies,
        exclude_from_auth=public,
        tags=tags,
    )
    async def create_handler(
        data: model,  # type: ignore[valid-type]
        service: CRUDService,  # type: ignore[type-arg]
    ) -> model:  # type: ignore[valid-type]
        processed = await service.before_create(
            {c.key: getattr(data, c.key) for c in data.__table__.columns if hasattr(data, c.key)}  # type: ignore[union-attr, attr-defined]
        )
        for key, value in processed.items():
            setattr(data, key, value)
        item = await service.repository.add(data)
        await service.after_create(item)
        return item

    fn = create_handler.fn  # type: ignore[union-attr]
    fn.__annotations__ = {"data": model, "service": CRUDService, "return": model}
    return create_handler


def _make_read_handler(
    model: type,
    read_dto: type,
    dependencies: dict[str, Any],
    public: bool,
    tags: list[str] | None,
) -> Any:
    """Factory for read handler."""

    @get(
        path="/{item_id:uuid}",
        return_dto=read_dto,
        dependencies=dependencies,
        exclude_from_auth=public,
        tags=tags,
    )
    async def read_handler(
        item_id: UUID,
        service: CRUDService,  # type: ignore[type-arg]
    ) -> model:  # type: ignore[valid-type]
        return await service.repository.get(item_id)

    fn = read_handler.fn  # type: ignore[union-attr]
    fn.__annotations__ = {"item_id": UUID, "service": CRUDService, "return": model}
    return read_handler


def _make_update_handler(
    model: type,
    update_dto: type,
    read_dto: type,
    dependencies: dict[str, Any],
    public: bool,
    tags: list[str] | None,
) -> Any:
    """Factory for update handler."""

    @patch(
        path="/{item_id:uuid}",
        dto=update_dto,
        return_dto=read_dto,
        dependencies=dependencies,
        exclude_from_auth=public,
        tags=tags,
    )
    async def update_handler(
        item_id: UUID,
        data: model,  # type: ignore[valid-type]
        service: CRUDService,  # type: ignore[type-arg]
    ) -> model:  # type: ignore[valid-type]
        # The partial DTO sets unset fields to None. Filter them out, but
        # allow explicit null for nullable columns.
        update_data = {
            c.key: getattr(data, c.key)
            for c in data.__table__.columns  # type: ignore[union-attr, attr-defined]
            if c.key != "id" and hasattr(data, c.key) and getattr(data, c.key) is not None
        }
        processed = await service.before_update(item_id, update_data)
        existing = await service.repository.get(item_id)
        for key, value in processed.items():
            setattr(existing, key, value)
        updated = await service.repository.update(existing)
        await service.session.flush()
        await service.after_update(updated)
        return updated

    fn = update_handler.fn  # type: ignore[union-attr]
    fn.__annotations__ = {"item_id": UUID, "data": model, "service": CRUDService, "return": model}
    return update_handler


def _make_delete_handler(
    model: type,
    dependencies: dict[str, Any],
    public: bool,
    tags: list[str] | None,
) -> Any:
    """Factory for delete handler."""

    @delete(
        path="/{item_id:uuid}",
        dependencies=dependencies,
        exclude_from_auth=public,
        tags=tags,
    )
    async def delete_handler(
        item_id: UUID,
        service: CRUDService,  # type: ignore[type-arg]
    ) -> None:
        await service.before_delete(item_id)
        await service.repository.delete(item_id)
        await service.after_delete(item_id)

    return delete_handler


def build_crud_router(model: type, meta: type) -> Router:
    """Build a Litestar Router with CRUD handlers for the given model."""
    operations: set[str] = set(_get_meta_attr(meta, "operations", set()))
    path: str | None = _get_meta_attr(meta, "path", None)
    tags: list[str] | None = _get_meta_attr(meta, "tags", None)
    exclude_fields: set[str] = set(_get_meta_attr(meta, "exclude_fields", {"sa_orm_sentinel"}))
    public_operations: set[str] = set(_get_meta_attr(meta, "public_operations", set()))
    filterable_fields: set[str] = set(_get_meta_attr(meta, "filterable_fields", set()))
    service_class: type | None = _get_meta_attr(meta, "service_class", None)

    # Always exclude sa_orm_sentinel even if the model overrides exclude_fields
    exclude_fields.add("sa_orm_sentinel")

    if path is None:
        path = "/" + _pluralize(model.__tablename__)  # type: ignore[attr-defined]

    read_dto, create_dto, update_dto = _build_dtos(model, exclude_fields)
    service_provider = _make_service_provider(model, service_class)
    dependencies: dict[str, Any] = {"service": Provide(service_provider)}

    handlers: list[Any] = []

    if "list" in operations:
        handlers.append(_make_list_handler(model, read_dto, exclude_fields, filterable_fields, dependencies, "list" in public_operations, tags))

    if "create" in operations:
        handlers.append(_make_create_handler(model, create_dto, read_dto, dependencies, "create" in public_operations, tags))

    if "read" in operations:
        handlers.append(_make_read_handler(model, read_dto, dependencies, "read" in public_operations, tags))

    if "update" in operations:
        handlers.append(_make_update_handler(model, update_dto, read_dto, dependencies, "update" in public_operations, tags))

    if "delete" in operations:
        handlers.append(_make_delete_handler(model, dependencies, "delete" in public_operations, tags))

    return Router(path=path, route_handlers=handlers)
