"""Public ids are opaque strings (ST0412, HK03, room 214); database integers never reach the wire."""


def stay_public(internal_id: int) -> str:
    return f"ST{internal_id:04d}"


