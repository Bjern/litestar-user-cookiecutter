from app.lib.crud.discovery import discover_models
from app.lib.crud.mixin import CRUDMixin
from app.lib.crud.routes import _pluralize


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


def test_discover_nonexistent_path_returns_empty() -> None:
    models = discover_models(domain_path="/nonexistent/path")
    assert models == []


# --- Pluralization ---


def test_pluralize_regular() -> None:
    assert _pluralize("product") == "products"


def test_pluralize_ends_in_s() -> None:
    assert _pluralize("status") == "statuses"


def test_pluralize_ends_in_y() -> None:
    assert _pluralize("category") == "categories"


def test_pluralize_snake_case() -> None:
    assert _pluralize("test_item") == "test-items"
