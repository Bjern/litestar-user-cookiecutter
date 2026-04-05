class CRUDMeta:
    """Default CRUDMeta configuration. Models override this via inner class."""

    operations: frozenset[str] = frozenset()
    path: str | None = None
    tags: list[str] | None = None
    exclude_fields: frozenset[str] = frozenset({"sa_orm_sentinel"})
    public_operations: frozenset[str] = frozenset()
    filterable_fields: frozenset[str] = frozenset()
    service_class: type | None = None


VALID_OPERATIONS = frozenset({"create", "read", "list", "update", "delete"})


class CRUDMixin:
    """Mixin that marks a model for auto-CRUD route generation.

    Define an inner CRUDMeta class to configure which operations to generate.
    Without CRUDMeta (or with empty operations), no routes are generated.
    """

    CRUDMeta: type = CRUDMeta
