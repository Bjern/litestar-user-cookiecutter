from litestar.middleware.session.server_side import ServerSideSessionConfig

from litestar_users import LitestarUsersConfig, LitestarUsersPlugin
from litestar_users.config import (
    AuthHandlerConfig,
    CurrentUserHandlerConfig,
    PasswordResetHandlerConfig,
    RegisterHandlerConfig,
    VerificationHandlerConfig,
)

from app.domain.users.models import User
from app.domain.users.schemas import UserReadDTO, UserRegistrationDTO, UserUpdateDTO
from app.domain.users.services import UserService
from app.lib.settings import get_settings

litestar_users = LitestarUsersPlugin(
    config=LitestarUsersConfig(
        auth_config=ServerSideSessionConfig(),
        secret=get_settings().encoding_secret,
        user_model=User,  # pyright: ignore
        user_read_dto=UserReadDTO,
        user_registration_dto=UserRegistrationDTO,
        user_update_dto=UserUpdateDTO,
        user_service_class=UserService,  # pyright: ignore
        auth_handler_config=AuthHandlerConfig(tags=["Auth"]),
        current_user_handler_config=CurrentUserHandlerConfig(tags=["Users"]),
        password_reset_handler_config=PasswordResetHandlerConfig(tags=["Auth"]),
        register_handler_config=RegisterHandlerConfig(tags=["Auth"]),
        verification_handler_config=VerificationHandlerConfig(tags=["Auth"]),
        auth_exclude_paths=["^/$", "^/health$", "^/schema"],
    )
)
