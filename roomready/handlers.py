"""The one place errors become HTTP: every domain refusal and every validation failure leaves as
application/problem+json from a handler installed here."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import (
    FILTER,
    DomainError,
)

PROBLEM = "application/problem+json"


def problem(status: int, type_: str, title: str, detail: str, **extra) -> JSONResponse:
    body = {"type": type_, "title": title, "status": status, "detail": detail, **extra}
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_request: Request, exc: DomainError):
        return problem(exc.status, exc.type, exc.title, exc.detail, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError):
        # A filter outside its enum is 400.
        errors = [
            {
                "field": ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path")),
                "message": e["msg"],
            }
            for e in exc.errors()
        ]
        status, type_, title = FILTER
        return problem(status, type_, title, f"{len(errors)} filter(s) invalid", errors=errors)
