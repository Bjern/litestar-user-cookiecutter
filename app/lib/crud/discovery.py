from __future__ import annotations

import importlib
from pathlib import Path

from loguru import logger

from advanced_alchemy.base import UUIDBase

from app.lib.crud.mixin import CRUDMixin, VALID_OPERATIONS


def _all_subclasses(cls: type) -> list[type]:
    """Recursively find all subclasses of a class."""
    result = []
    for sub in cls.__subclasses__():
        result.append(sub)
        result.extend(_all_subclasses(sub))
    return result


def discover_models(domain_path: str | None = None) -> list[type]:
    """Import all models.py under app/domain/*, return CRUDMixin models with operations.

    Args:
        domain_path: Path to the domain directory. Defaults to app/domain relative to the project root.
    """
    if domain_path is None:
        # Resolve relative to this file: app/lib/crud/discovery.py -> app/domain
        domain_root = Path(__file__).resolve().parent.parent.parent / "domain"
    else:
        domain_root = Path(domain_path)

    if not domain_root.is_dir():
        logger.warning(
            "crud.discovery | domain path not found: {path}", path=domain_root
        )
        return []

    for subdir in sorted(domain_root.iterdir()):
        if subdir.is_dir() and (subdir / "models.py").exists():
            module_name = f"app.domain.{subdir.name}.models"
            try:
                importlib.import_module(module_name)
            except Exception:
                logger.exception(
                    "crud.discovery | failed to import {mod}", mod=module_name
                )
                raise

    models = []
    for cls in _all_subclasses(UUIDBase):
        if not issubclass(cls, CRUDMixin):
            continue
        # Only include models from the app.domain package
        if not getattr(cls, "__module__", "").startswith("app.domain."):
            continue
        operations: set[str] = getattr(cls.CRUDMeta, "operations", set())  # type: ignore[attr-defined]
        if not operations:
            continue
        # Validate operations
        invalid = set(operations) - VALID_OPERATIONS
        if invalid:
            logger.warning(
                "crud.discovery | model={model} has invalid operations: {invalid}",
                model=cls.__name__,
                invalid=invalid,
            )
        models.append(cls)

    return models
