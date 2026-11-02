"""RoomReady application: one error handler, request ids on every request."""
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .clock import get_clock
from .db import init_db, make_engine, make_sessionmaker
from .handlers import (
    FILTER_RESPONSE,
    INTERNAL_RESPONSE,
    VALIDATION_RESPONSE,
    install_handlers,
)
from .routers import assignments, checkouts, inspections, rooms
from .services.seed import seed
from .settings import Settings

STATIC = Path(__file__).parent / "static"
TAGS = [
    {"name": "rooms", "description": "The board — 60 rooms, their derived state, the housekeepers, one room's history"},
    {"name": "checkouts", "description": "A guest leaves; the room is dirty"},
    {"name": "assignments", "description": "Assign, start, finish — the clean, timed"},
    {"name": "inspections", "description": "Somebody else passes or fails the room"},
]


def _can_fail(param: dict) -> bool:
    """A query or path parameter the framework can refuse: anything but an unconstrained string."""
    schema = param.get("schema", {})
    options = schema.get("anyOf", [schema])
    return any(o.get("type") not in ("string", "null") or set(o) - {"type", "title"} for o in options)


def honest_openapi(app: FastAPI):
    """The spec documents exactly what each operation can answer. FastAPI's stock 422 (HTTPValidationError,
    application/json) is never sent — a bad query is the 400 validation problem, a bad body the 422 validation
    problem — so it is replaced; every operation gets the 500 problem it can always answer."""
    def openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        spec = get_openapi(
            title=app.title, version=app.version, description=app.description, routes=app.routes,
            tags=app.openapi_tags
        )
        for ops in spec["paths"].values():
            for op in ops.values():
                answers = op["responses"]
                if "application/json" in answers.get("422", {}).get("content", {}):
                    del answers["422"]  # the stock HTTPValidationError
                if "requestBody" in op:
                    answers["422"] = VALIDATION_RESPONSE[422]
                if any(_can_fail(p) for p in op.get("parameters", [])):
                    answers.setdefault("400", FILTER_RESPONSE[400])
                answers["500"] = INTERNAL_RESPONSE[500]
        schemas = spec.get("components", {}).get("schemas", {})
        for name in ("HTTPValidationError", "ValidationError"):
            if name in schemas and f"#/components/schemas/{name}" not in str({**spec["paths"], **schemas}):
                del schemas[name]
        app.openapi_schema = spec
        return spec
    return openapi


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        clock = app.dependency_overrides.get(get_clock, get_clock)()
        with app.state.sessionmaker() as session:
            seed(session, settings.seed_dir, clock)
        yield
        engine.dispose()

    app = FastAPI(
        title="RoomReady", version="0.1.0", lifespan=lifespan, openapi_tags=TAGS,
        description="Hotel housekeeping: dirty, cleaned, inspected, ready — raced against the day's arrivals."
    )
    app.state.sessionmaker = make_sessionmaker(engine)

    @app.middleware("http")
    async def request_id_and_log(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        response = await call_next(request)
        return response

    install_handlers(app)
    for r in (rooms.router, checkouts.router, assignments.router, inspections.router):
        app.include_router(r)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    app.openapi = honest_openapi(app)
    return app


app = create_app()
