from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from advanced_alchemy.repository._async import SQLAlchemyAsyncRepository

ModelT = TypeVar("ModelT")


class CRUDService(Generic[ModelT]):
    """Default CRUD service with lifecycle hooks.

    Override before_*/after_* methods for custom business logic.
    """

    def __init__(
        self, session: Any, repository: SQLAlchemyAsyncRepository[Any]
    ) -> None:
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
