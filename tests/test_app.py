from app.main import app


def test_app_has_routes() -> None:
    assert len(app.routes) > 0


def test_app_has_openapi() -> None:
    assert app.openapi_config is not None
