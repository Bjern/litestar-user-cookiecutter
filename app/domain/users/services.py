from typing import Any

from loguru import logger
from litestar_users.service import BaseUserService

from app.domain.users.models import User
from app.lib.settings import get_settings


class UserService(BaseUserService[User, Any, Any]):  # type: ignore[type-var]
    async def post_registration_hook(self, user: User, request: Any = None) -> None:
        settings = get_settings()
        if settings.auto_verify_users:
            user.is_verified = True
            await self.user_repository.update(user)
            logger.info(
                "user.registered | id={id} email={email} auto_verified=true",
                id=user.id,
                email=user.email,
            )
        else:
            logger.info(
                "user.registered | id={id} email={email} auto_verified=false verification_pending=true",
                id=user.id,
                email=user.email,
            )

    async def send_verification_token(self, user: User, token: str) -> None:
        """Send a verification token to the user.

        Called automatically by litestar-users after registration when
        `require_verification_on_registration` is True (the default).
        The token is a time-limited JWT (24h) that the user must POST to
        `/verify` to activate their account.

        Override this method to deliver the token via your preferred channel
        (email, SMS, etc). The base class implementation is a no-op — if you
        don't override it, the token is silently discarded.

        Example using an email service:

            async def send_verification_token(self, user: User, token: str) -> None:
                verification_url = f"{settings.BASE_URL}/verify?token={token}"
                await email_service.send(
                    to=user.email,
                    subject="Verify your account",
                    body=f"Click here to verify: {verification_url}",
                )
        """
        # TODO: Replace with actual email/SMS delivery
        logger.warning(
            "verification.token_generated | id={id} email={email} delivery=console_only",
            id=user.id,
            email=user.email,
        )

    async def send_password_reset_token(self, user: User, token: str) -> None:
        """Send a password reset token to the user.

        Called by litestar-users when a user requests a password reset via
        `/forgot-password`. The token is a time-limited JWT (24h) that the
        user must POST to `/reset-password` along with their new password.

        Override this method to deliver the token via your preferred channel.
        The base class implementation is a no-op.

        Example using an email service:

            async def send_password_reset_token(self, user: User, token: str) -> None:
                reset_url = f"{settings.BASE_URL}/reset-password?token={token}"
                await email_service.send(
                    to=user.email,
                    subject="Reset your password",
                    body=f"Click here to reset: {reset_url}",
                )
        """
        # TODO: Replace with actual email/SMS delivery
        logger.warning(
            "password_reset.token_generated | id={id} email={email} delivery=console_only",
            id=user.id,
            email=user.email,
        )
