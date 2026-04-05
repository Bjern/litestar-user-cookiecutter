from advanced_alchemy.base import UUIDBase
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.crud.mixin import CRUDMixin


class MinimalModel(UUIDBase, CRUDMixin):
    name: Mapped[str] = mapped_column(String(100))


class ConfiguredModel(UUIDBase, CRUDMixin):
    name: Mapped[str] = mapped_column(String(100))

    class CRUDMeta:
        operations = {"create", "read", "list"}
        path = "/widgets"
        tags = ["Widgets"]
        exclude_fields = {"sa_orm_sentinel", "name"}
        public_operations = {"list"}
        filterable_fields = {"name"}


def test_default_meta_has_empty_operations() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.operations == set()


def test_default_meta_path_is_none() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.path is None


def test_default_meta_tags_is_none() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.tags is None


def test_default_meta_exclude_fields() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.exclude_fields == {"sa_orm_sentinel"}


def test_default_meta_public_operations_empty() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.public_operations == set()


def test_default_meta_filterable_fields_empty() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.filterable_fields == set()


def test_default_meta_service_class_is_none() -> None:
    meta = MinimalModel.CRUDMeta
    assert meta.service_class is None


def test_configured_meta_overrides() -> None:
    meta = ConfiguredModel.CRUDMeta
    assert meta.operations == {"create", "read", "list"}
    assert meta.path == "/widgets"
    assert meta.tags == ["Widgets"]
    assert meta.exclude_fields == {"sa_orm_sentinel", "name"}
    assert meta.public_operations == {"list"}
    assert meta.filterable_fields == {"name"}


def test_crud_mixin_is_subclass_check() -> None:
    assert issubclass(MinimalModel, CRUDMixin)
    assert not issubclass(UUIDBase, CRUDMixin)
