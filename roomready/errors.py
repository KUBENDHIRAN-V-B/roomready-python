"""Domain refusals: the exception classes and the error types. Nothing here knows about HTTP frameworks —
services raise these, and `handlers.py` maps every one of them to application/problem+json.

The class attributes below are the single source of truth for status, type and title.
"""
class DomainError(Exception):
    status: int = 400
    type: str = "/errors/domain"
    title: str = "Refused"

    def __init__(self, detail: str, **extra):
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class NoSuchProperty(DomainError):
    status, type, title = 404, "/errors/no-such-property", "No such property"


class NoSuchRoom(DomainError):
    status, type, title = 404, "/errors/no-such-room", "No such room in this property"


# (status, type, title) of the errors no domain class raises
FILTER = (400, "/errors/validation", "Invalid filter value")
