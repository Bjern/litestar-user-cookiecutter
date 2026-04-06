from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger
from litestar import get
from litestar.plugins import InitPlugin

from app.lib.crud.discovery import discover_models
from app.lib.crud.routes import build_crud_router

if TYPE_CHECKING:
    from litestar.config.app import AppConfig

_UI_ATTRS = ("icon", "label", "field_order", "list_columns", "searchable_fields", "field_overrides")


def _snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _collect_ui_metadata(models: list[type]) -> dict[str, Any]:
    """Collect UI metadata from CRUDMeta of each model."""
    result: dict[str, Any] = {}
    for model in models:
        meta = model.CRUDMeta  # type: ignore[attr-defined]
        entry: dict[str, Any] = {}
        for attr in _UI_ATTRS:
            value = getattr(meta, attr, None)
            if value is not None:
                entry[_snake_to_camel(attr)] = value
        if entry:
            result[model.__name__] = entry
    return result


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

        ui_metadata = _collect_ui_metadata(models)

        @get("/schema/ui-metadata", exclude_from_auth=True, tags=["Schema"])
        async def ui_metadata_handler() -> dict[str, Any]:
            return ui_metadata

        app_config.route_handlers.append(ui_metadata_handler)

        return app_config
