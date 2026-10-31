"""Public ids are opaque strings (ST0412, AS118, HK03, room 214); database integers never reach the wire."""
import re

_ASSIGNMENT = re.compile(r"^AS(\d{3,})$")


def stay_public(internal_id: int) -> str:
    return f"ST{internal_id:04d}"



def assignment_public(internal_id: int) -> str:
    return f"AS{internal_id:03d}"


def assignment_internal(public_id: str) -> int | None:
    m = _ASSIGNMENT.match(public_id or "")
    return int(m.group(1)) if m else None
