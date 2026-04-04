from litestar import Litestar
from litestar.openapi import OpenAPIConfig
from loguru import logger

from app.domain.default.routes import router as default_router
from app.lib.crud import CRUDPlugin
from app.lib.db import db_plugin
from app.lib.logging import setup_logging
from app.lib.security import litestar_users
from app.lib.settings import get_settings

setup_logging()

settings = get_settings()

# Change these to match the project details
openapi_config = OpenAPIConfig(
    title=settings.app_title,
    version="1.0.0",
)

app = Litestar(
    route_handlers=[default_router],
    openapi_config=openapi_config,
    plugins=[db_plugin, CRUDPlugin(), litestar_users],
)

logger.info("Application started | app_title={title}", title=settings.app_title)
