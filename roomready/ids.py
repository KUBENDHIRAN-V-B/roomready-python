"""Public ids are opaque strings (ST0412, AS118, HK03, room 214); database integers never reach the wire."""
import re

_STAY = re.compile(r"^ST(\d{4,})$")
_ASSIGNMENT = re.compile(r"^AS(\d{3,})$")


def stay_public(internal_id: int) -> str:
    return f"ST{internal_id:04d}"



def stay_internal(public_id: str) -> int | None:
    m = _STAY.match(public_id or "")
    return int(m.group(1)) if m else None


def assignment_public(internal_id: int) -> str:
    return f"AS{internal_id:03d}"


def assignment_internal(public_id: str) -> int | None:
    m = _ASSIGNMENT.match(public_id or "")
    return int(m.group(1)) if m else None


_INSPECTION = re.compile(r"^IN(\d{3,})$")

def inspection_public(internal_id: int) -> str:
    return f"IN{internal_id:03d}"
