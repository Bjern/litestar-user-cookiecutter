from app.lib.crud.pagination import PaginatedResponse


def test_paginated_response_schema() -> None:
    resp = PaginatedResponse[dict](
        items=[{"name": "a"}, {"name": "b"}],
        total=10,
        limit=20,
        offset=0,
    )
    assert resp.items == [{"name": "a"}, {"name": "b"}]
    assert resp.total == 10
    assert resp.limit == 20
    assert resp.offset == 0


def test_paginated_response_defaults() -> None:
    resp = PaginatedResponse[dict](items=[], total=0)
    assert resp.limit == 20
    assert resp.offset == 0
