from advanced_alchemy.extensions.litestar import (
    SQLAlchemyAsyncConfig,
    SQLAlchemyInitPlugin,
)

from app.lib.settings import get_settings

db_config = SQLAlchemyAsyncConfig(
    connection_string=get_settings().database_url,
    session_dependency_key="session",
    before_send_handler="autocommit",
)

db_plugin = SQLAlchemyInitPlugin(config=db_config)
