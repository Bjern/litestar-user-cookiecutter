from advanced_alchemy.base import UUIDBase
from litestar_users.mixins import SQLAlchemyUserMixin


class User(UUIDBase, SQLAlchemyUserMixin):
    """User model."""
