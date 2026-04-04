from dataclasses import dataclass

from advanced_alchemy.extensions.litestar import SQLAlchemyDTO, SQLAlchemyDTOConfig
from litestar.dto import DataclassDTO

from app.domain.users.models import User


@dataclass
class UserRegistrationSchema:
    email: str
    password: str


class UserRegistrationDTO(DataclassDTO[UserRegistrationSchema]):
    """User registration DTO."""


class UserReadDTO(SQLAlchemyDTO[User]):
    # exclude password_hash so the hash is never sent to the client
    config = SQLAlchemyDTOConfig(exclude={"password_hash"})


class UserUpdateDTO(SQLAlchemyDTO[User]):
    # password_hash excluded: password changes are handled via /reset-password only.
    config = SQLAlchemyDTOConfig(exclude={"password_hash"}, partial=True)
