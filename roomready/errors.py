class DomainError(Exception):
    status: int = 400
    type: str = "/errors/domain"
    title: str = "Refused"

    def __init__(self, detail: str, **extra):
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class Malformed(DomainError):
    """A body that passes its Field constraints but fails a rule the clock or the row decides (`at` in the
    future, `at` before check-in) — the validation status, naming the field, like any other malformed body."""
    status, type, title = 422, "/errors/validation", "The request body is not valid"


class NoSuchProperty(DomainError):
    status, type, title = 404, "/errors/no-such-property", "No such property"


class NoSuchRoom(DomainError):
    status, type, title = 404, "/errors/no-such-room", "No such room in this property"


class NoSuchHousekeeper(DomainError):
    status, type, title = 404, "/errors/no-such-housekeeper", "No such housekeeper"


class NoSuchAssignment(DomainError):
    status, type, title = 404, "/errors/no-such-assignment", "No such assignment"


class RoomNotOccupied(DomainError):
    status, type, title = 400, "/errors/room-not-occupied", "The room has no guest to check out"


class StepSkipped(DomainError):
    """The room is not in the state this action needs; `state` says where it is, `needs` what must happen first."""
    status, type, title = 409, "/errors/step-skipped", "A step in the sequence was skipped"


# (status, type, title) of the errors no domain class raises
VALIDATION = (422, "/errors/validation", "The request body is not valid")
FILTER = (400, "/errors/validation", "Invalid filter value")
