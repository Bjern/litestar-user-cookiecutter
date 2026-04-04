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
            filters = {k: v for k, v in kwargs.items() if k in filterable_fields and v is not None}
            if filters:
                items, total = await service.repository.list_and_count(
                    *[getattr(model, field) == value for field, value in filters.items()],
                    limit=limit,
                    offset=offset,
                )
            else:
                items, total = await service.repository.list_and_count(limit=limit, offset=offset)
            return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

        if filterable_fields:
            import inspect
            from litestar.params import Parameter as LitestarParam

            sig = inspect.signature(list_handler.fn)  # type: ignore[union-attr]
            new_params = [p for p in sig.parameters.values() if p.kind != inspect.Parameter.VAR_KEYWORD]
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
