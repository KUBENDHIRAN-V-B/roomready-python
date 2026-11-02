"""The one place errors become HTTP: every exception — domain refusal, validation failure, framework 404/405,
anything unexpected — leaves as application/problem+json from a handler installed here. Also the OpenAPI helpers
routes use to document how each endpoint can say no."""
import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import (
    FILTER,
    HTTP,
    INTERNAL,
    METHOD_NOT_ALLOWED,
    NOT_FOUND,
    VALIDATION,
    DomainError,
)
log = logging.getLogger("roomready.errors")

PROBLEM = "application/problem+json"


def problem(status: int, type_: str, title: str, detail: str, headers: dict | None = None, **extra) -> JSONResponse:
    body = {"type": type_, "title": title, "status": status, "detail": detail, **extra}
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM, headers=headers)


def example(cls: type[DomainError], detail: str, **extra) -> dict:
    """An OpenAPI `responses` entry for one refusal, so /docs shows how each endpoint can say no."""
    return {
        "description": cls.title,
        "content": {PROBLEM: {"example": {
            "type": cls.type, "title": cls.title, "status": cls.status,
            "detail": detail, **extra}}},
    }


def responses(*entries: tuple[type[DomainError], str] | tuple[type[DomainError], str, dict]) -> dict:
    """Refusals that share a status are shown as one entry with every example, so none is hidden from /docs."""
    out: dict[int | str, dict] = {}
    for entry in entries:
        cls, detail = entry[0], entry[1]
        extra = entry[2] if len(entry) == 3 else {}
        item = example(cls, detail, **extra)
        if cls.status in out:
            existing = out[cls.status]
            examples = existing["content"][PROBLEM].setdefault("examples", {})
            if "example" in existing["content"][PROBLEM]:
                first = existing["content"][PROBLEM].pop("example")
                examples[first["type"]] = {"value": first}
            examples[cls.type] = {"value": item["content"][PROBLEM]["example"]}
            existing["description"] += " · " + cls.title
        else:
            out[cls.status] = item
    return out


VALIDATION_RESPONSE = {
    422: {
        "description": VALIDATION[2],
        "content": {PROBLEM: {"example": {
            "type": VALIDATION[1], "title": VALIDATION[2], "status": 422,
            "detail": "1 field(s) failed validation",
            "errors": [{"field": "at", "message": "Field required"}]}}},
    }
}
FILTER_RESPONSE = {
    400: {
        "description": FILTER[2],
        "content": {PROBLEM: {"example": {
            "type": FILTER[1], "title": FILTER[2], "status": 400,
            "detail": "1 filter(s) invalid",
            "errors": [{"field": "state", "message": "Input should be 'occupied', 'dirty', 'assigned', 'cleaning', 'toinspect', 'ready' or 'out_of_order'"}]}}},
    }
}
INTERNAL_RESPONSE = {
    500: {
        "description": INTERNAL[2],
        "content": {PROBLEM: {"example": {
            "type": INTERNAL[1], "title": INTERNAL[2], "status": 500,
            "detail": "The request could not be completed", "request_id": "3f9c2a71b0d4"}}},
    }
}


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_request: Request, exc: DomainError):
        return problem(exc.status, exc.type, exc.title, exc.detail, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError):
        errors = [
            {"field": ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path")), "message": e["msg"]}
            for e in exc.errors()
        ]
        if any(e["loc"] and e["loc"][0] == "body" for e in exc.errors()):
            status, type_, title = VALIDATION
            return problem(status, type_, title, f"{len(errors)} field(s) failed validation", errors=errors)
        status, type_, title = FILTER
        return problem(status, type_, title, f"{len(errors)} filter(s) invalid", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _framework(request: Request, exc: StarletteHTTPException):
        # an unknown path or a method the path does not take: the framework's own refusals, in the same shape
        if exc.status_code == 404:
            status, type_, title = NOT_FOUND
            detail = f"There is no resource at {request.url.path}"
        elif exc.status_code == 405:
            status, type_, title = METHOD_NOT_ALLOWED
            detail = f"{request.method} is not allowed on {request.url.path}"
        else:
            status, type_ = exc.status_code, HTTP
            title = HTTPStatus(exc.status_code).phrase if exc.status_code in HTTPStatus._value2member_map_ else "HTTP error"
            detail = str(exc.detail)
        return problem(status, type_, title, detail, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "-")
        log.exception("unhandled error method=%s path=%s request_id=%s", request.method, request.url.path, request_id)
        status, type_, title = INTERNAL
        return problem(status, type_, title, "The request could not be completed", request_id=request_id)
