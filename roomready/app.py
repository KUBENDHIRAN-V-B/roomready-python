from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .clock import get_clock
from .db import init_db, make_engine, make_sessionmaker
from .handlers import install_handlers
from .routers import assignments, checkouts, inspections, rooms
from .services.seed import seed
from .settings import Settings

STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        clock = app.dependency_overrides.get(get_clock, get_clock)()  # the same clock the routes see
        with app.state.sessionmaker() as session:
            seed(session, settings.seed_dir, clock)
        yield
        engine.dispose()

    app = FastAPI(title="RoomReady", version="0.1.0", lifespan=lifespan)
    app.state.sessionmaker = make_sessionmaker(engine)
    install_handlers(app)
    for r in (rooms.router, checkouts.router, assignments.router, inspections.router):
        app.include_router(r)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    return app


app = create_app()
