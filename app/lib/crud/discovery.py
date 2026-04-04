from __future__ import annotations

import importlib
from pathlib import Path

from advanced_alchemy.base import UUIDBase

from app.lib.crud.mixin import CRUDMixin


def discover_models(domain_path: str = "app/domain") -> list[type]:
    """Import all models.py under app/domain/*, return CRUDMixin models with operations."""
    domain_root = Path(domain_path)
    for subdir in sorted(domain_root.iterdir()):
        if subdir.is_dir() and (subdir / "models.py").exists():
            module_name = f"app.domain.{subdir.name}.models"
            importlib.import_module(module_name)

    return [
        cls
        for cls in UUIDBase.__subclasses__()
        if issubclass(cls, CRUDMixin) and cls.CRUDMeta.operations
    ]
