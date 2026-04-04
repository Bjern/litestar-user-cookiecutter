from app.lib.crud.discovery import discover_models
from app.lib.crud.mixin import CRUDMixin


def test_discover_finds_no_crud_models_when_none_have_operations() -> None:
    """User model has no CRUDMixin, default domain has no model."""
    models = discover_models()
    assert all(issubclass(m, CRUDMixin) for m in models)
    assert all(m.CRUDMeta.operations for m in models)


def test_discover_imports_all_domain_models() -> None:
    """Calling discover_models imports all models.py files.
    After calling, UUIDBase.__subclasses__() should include User."""
    from advanced_alchemy.base import UUIDBase

    discover_models()
    subclass_names = {cls.__name__ for cls in UUIDBase.__subclasses__()}
    assert "User" in subclass_names
