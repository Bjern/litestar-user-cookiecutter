import os
from datetime import datetime, timedelta

import pytest
from advanced_alchemy.base import UUIDBase
from advanced_alchemy.extensions.litestar import (
    SQLAlchemyAsyncConfig,
    SQLAlchemyInitPlugin,
)
from litestar import Litestar
from litestar.security.jwt.token import Token
from litestar.testing import TestClient

os.environ.setdefault("ENCODING_SECRET", "test-secret-key-32-characters!!!")
os.environ.setdefault("AUTO_VERIFY_USERS", "true")

from app.domain.default.routes import router as default_router  # noqa: E402
from app.lib.security import litestar_users  # noqa: E402
from app.lib.settings import get_settings  # noqa: E402


def _build_app() -> Litestar:
    test_db_config = SQLAlchemyAsyncConfig(
        connection_string="sqlite+aiosqlite://",
        session_dependency_key="session",
        before_send_handler="autocommit",
        create_all=True,
        metadata=UUIDBase.metadata,
    )
    test_db_plugin = SQLAlchemyInitPlugin(config=test_db_config)

    return Litestar(
        route_handlers=[default_router],
        plugins=[test_db_plugin, litestar_users],
    )


def make_token(user_id: str, aud: str) -> str:
    """Generate a JWT token identical to what litestar-users produces."""
    settings = get_settings()
    token = Token(
        exp=datetime.now() + timedelta(hours=24),  # noqa: DTZ005
        sub=user_id,
        aud=aud,
    )
    return token.encode(secret=settings.encoding_secret, algorithm="HS256")


USER_EMAIL = "test@example.com"
USER_PASSWORD = "Secret123!"


@pytest.fixture()
def client():
    with TestClient(app=_build_app()) as tc:
        yield tc


@pytest.fixture()
def authenticated_client(client: TestClient) -> TestClient:
    """A client with a pre-registered and logged-in user."""
    client.post("/register", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    client.post("/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    return client
