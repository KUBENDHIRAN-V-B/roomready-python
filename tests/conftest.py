from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roomready.app import create_app
from roomready.clock import FixedClock, get_clock
from roomready.settings import Settings

ROOT = Path(__file__).resolve().parent.parent
T0 = datetime(2026, 9, 28, 10, 40, tzinfo=timezone.utc)  # Monday, twenty to eleven: the guest in 214 leaves
P = "/properties/harbour-view"


def make_settings(tmp_path: Path, **overrides) -> Settings:
    db = (tmp_path / "roomready-test.db").as_posix()
    values = {"database_url": f"sqlite:///{db}", "seed_dir": str(ROOT / "seed")}
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def clock():
    return FixedClock(T0)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def app(settings, clock):
    app = create_app(settings)
    app.dependency_overrides[get_clock] = lambda: clock
    return app


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def inspect(client, room="214", inspector="HK01", result="pass"):
    return client.post("/inspections", json={"room": room, "inspector": inspector, "result": result})



def room(client, no="214") -> dict:
    r = client.get(f"{P}/rooms/{no}")
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def db(app):
    """A fresh session factory for looking at rows the API wrote."""
    return app.state.sessionmaker


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def checkout(client, room="214", at=None, arrival_at=None) -> dict:
    body = {"room": room, "at": at or iso(T0)}
    if arrival_at is not None:
        body["arrival_at"] = arrival_at
    r = client.post("/checkouts", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def assign(client, room="214", housekeeper="HK03"):
    return client.post("/assignments", json={"room": room, "housekeeper": housekeeper})


def assigned(client, room="214", housekeeper="HK03", arrival_at=None) -> dict:
    """checkout + assign, returning the assignment body"""
    checkout(client, room, arrival_at=arrival_at)
    r = assign(client, room, housekeeper)
    assert r.status_code == 201, r.text
    return r.json()


def cleaned(client, clock, room="214", housekeeper="HK03", minutes=36, arrival_at=None) -> dict:
    """checkout + assign + start + finish (the clock moved `minutes`), returning the finish body plus the assignment id"""
    a = assigned(client, room, housekeeper, arrival_at=arrival_at)
    assert client.post(f"/assignments/{a['assignment_id']}/start").status_code == 200
    clock.advance(minutes=minutes)
    r = client.post(f"/assignments/{a['assignment_id']}/finish")
    assert r.status_code == 200, r.text
    return {**r.json(), "room": room, "housekeeper": housekeeper}
