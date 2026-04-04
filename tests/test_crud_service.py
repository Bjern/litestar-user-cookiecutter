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
    await service.after_create(MagicMock())


@pytest.mark.asyncio
async def test_before_update_returns_data_unchanged(mock_repository: MagicMock) -> None:
    service = CRUDService(session=MagicMock(), repository=mock_repository)
    data = {"name": "Updated"}
    result = await service.before_update(uuid4(), data)
    assert result == {"name": "Updated"}


@pytest.mark.asyncio
async def test_after_update_is_noop(mock_repository: MagicMock) -> None:
    service = CRUDService(session=MagicMock(), repository=mock_repository)
    await service.after_update(MagicMock())


@pytest.mark.asyncio
async def test_before_delete_is_noop(mock_repository: MagicMock) -> None:
    service = CRUDService(session=MagicMock(), repository=mock_repository)
    await service.before_delete(uuid4())


@pytest.mark.asyncio
async def test_after_delete_is_noop(mock_repository: MagicMock) -> None:
    service = CRUDService(session=MagicMock(), repository=mock_repository)
    await service.after_delete(uuid4())
