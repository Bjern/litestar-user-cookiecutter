from litestar import Router, get, Response

from app.domain.default.schemas import Health


@get("/health")
async def health() -> Response[Health]:
    return Response(Health(status="pass"), status_code=200)


router = Router(path="", route_handlers=[health])
