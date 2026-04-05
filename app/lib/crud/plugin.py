from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from litestar.plugins import InitPlugin

from app.lib.crud.discovery import discover_models
from app.lib.crud.routes import build_crud_router

if TYPE_CHECKING:
    from litestar.config.app import AppConfig


class CRUDPlugin(InitPlugin):
    """Litestar plugin that auto-generates CRUD routes from CRUDMixin models.

    Args:
        models: Optional list of model classes to register. If provided, these
            are used instead of auto-discovery. Useful for testing.
    """

    def __init__(self, models: list[type] | None = None) -> None:
        self._explicit_models = models

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        models = (
            self._explicit_models
            if self._explicit_models is not None
            else discover_models()
        )
        for model in models:
            router = build_crud_router(model, model.CRUDMeta)  # type: ignore[attr-defined]
            app_config.route_handlers.append(router)
            logger.info(
                "crud.registered | model={model} path={path} operations={ops}",
                model=model.__name__,
                path=router.path,
                ops=model.CRUDMeta.operations,  # type: ignore[attr-defined]
            )
        return app_config
