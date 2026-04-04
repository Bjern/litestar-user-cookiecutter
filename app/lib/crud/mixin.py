class CRUDMeta:
    """Default CRUDMeta configuration. Models override this via inner class."""

    operations: set[str] = set()
    path: str | None = None
    tags: list[str] | None = None
    exclude_fields: set[str] = {"sa_orm_sentinel"}
    public_operations: set[str] = set()
    filterable_fields: set[str] = set()
    service_class: type | None = None


class CRUDMixin:
    """Mixin that marks a model for auto-CRUD route generation.

    Define an inner CRUDMeta class to configure which operations to generate.
    Without CRUDMeta (or with empty operations), no routes are generated.
    """

    CRUDMeta: type = CRUDMeta
