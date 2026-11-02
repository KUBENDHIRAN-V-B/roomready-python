"""Runtime contract: stdout logging, env-file configuration, persistent data and image hygiene."""
import logging
import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from roomready.app import create_app
from roomready.clock import get_clock
from roomready.models import Stay
from roomready.settings import Settings
from tests.conftest import ROOT, P, cleaned, inspect, make_settings


def test_every_request_and_event_is_logged_and_no_line_carries_the_guest(client, clock, db, caplog):
    caplog.set_level(logging.INFO)
    cleaned(client, clock, "214", "HK03")
    inspect(client, "214", "HK03", "pass")     # the refusal path logs too
    inspect(client, "214", "HK01", "pass")
    client.get(f"{P}/rooms/214/history")
    with db() as s:
        guest = s.get(Stay, 29).guest_ref
    lines = [r.getMessage() for r in caplog.records]
    assert "event kind=checked_out room=214 stay=ST0029 assignment=- actor=front-desk" in lines
    assert "event kind=inspected room=214 stay=ST0029 assignment=AS001 actor=HK01" in lines
    assert not any(re.search(r"\b(room|stay|assignment)_id=", line) for line in lines), "log lines carry public ids only"
    assert any("request method=POST path=/inspections status=409" in line for line in lines)
    assert any("request method=GET path=/properties/harbour-view/rooms/214/history status=200" in line for line in lines)
    assert all(guest not in line for line in lines)
    assert logging.getLogger("uvicorn.access").disabled, "one line per request: uvicorn's access line is off"


def test_the_ready_line_reports_where_the_settings_object_binds(tmp_path, caplog):
    settings = make_settings(tmp_path, host="0.0.0.0", port=8080)
    app = create_app(settings)                    # configures logging afresh, so capture from here on
    logging.getLogger().addHandler(caplog.handler)
    caplog.set_level(logging.INFO)
    try:
        with TestClient(app):
            pass
    finally:
        logging.getLogger().removeHandler(caplog.handler)
    assert any(r.getMessage().startswith("ready host=0.0.0.0 port=8080 ") for r in caplog.records)
    defaults = Settings(_env_file=None)
    assert (defaults.host, defaults.port) == ("0.0.0.0", 8080), "the defaults"


def test_settings_come_from_an_env_file(tmp_path, clock):
    env = tmp_path / ".env"
    db = (tmp_path / "env.db").as_posix()
    env.write_text(
        f"DATABASE_URL=sqlite:///{db}\nINSPECTION_REQUIRED_FOR=Deluxe,Suite\nSTALL_AFTER_MINUTES=45\nSEED_DIR={ROOT / 'seed'}\n"
        "HOST=127.0.0.1\nPORT=9090\n", encoding="utf-8")
    settings = Settings(_env_file=env)
    assert settings.inspection_types == ["Deluxe", "Suite"] and settings.stall_after_minutes == 45
    assert (settings.host, settings.port) == ("127.0.0.1", 9090)
    app = create_app(settings)
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app) as c:
        assert c.get("/settings").json() == {"inspection_required_for": ["Deluxe", "Suite"], "stall_after_minutes": 45}
        assert len(c.get(f"{P}/rooms").json()["rooms"]) == 60
    assert Path(db).exists()


def test_data_survives_a_restart_on_the_same_database(tmp_path, clock):
    settings = make_settings(tmp_path)
    app = create_app(settings)
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app) as c:
        cleaned(c, clock, "214", "HK03")
        cleaned(c, clock, "301", "HK04")
        inspect(c, "301", "HK01", "pass")
        board_before = c.get(f"{P}/rooms").json()
        history_before = c.get(f"{P}/rooms/214/history").json()
    app = create_app(settings)
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app) as c:
        assert c.get(f"{P}/rooms").json() == board_before, "the whole board is exactly as housekeeping left it"
        assert c.get(f"{P}/rooms/214/history").json() == history_before
    with app.state.sessionmaker() as s:
        assert len(s.scalars(select(Stay)).all()) == 60, "the restart did not seed a second hotel"


def test_dockerfile_matches_the_contract_and_reads_host_and_port_from_the_environment():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in dockerfile
    assert "pip install --no-cache-dir -r requirements.lock" in dockerfile
    assert re.search(r"ENV HOST=0\.0\.0\.0 \\\n\s+PORT=8080", dockerfile), "the defaults are in the image"
    assert "DATABASE_URL" not in dockerfile, "the env-file carries the database, nothing else is baked in"
    assert 'CMD ["sh", "-c", "exec uvicorn roomready.app:app --host \\"$HOST\\" --port \\"$PORT\\""]' in dockerfile
    assert 'VOLUME ["/data"]' in dockerfile


def test_dockerignore_keeps_tests_databases_and_caches_out_of_the_image():
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    assert ignore == [".git", ".venv", "venv", "**/__pycache__", "**/*.pyc", "**/.pytest_cache", ".ruff_cache", "tests", "sandbox", "**/*.db", ".env", "build", "dist", "*.egg-info"]


def test_env_example_lists_every_setting_the_app_reads():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    keys = {line.split("=", 1)[0] for line in example.splitlines() if line and not line.startswith("#")}
    assert keys == {name.upper() for name in Settings.model_fields}
    assert "DATABASE_URL=sqlite:////data/roomready.db" in example


def test_lock_file_pins_every_package():
    lock = [line for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    names = {line.split("==")[0].lower() for line in lock}
    assert all("==" in line for line in lock) and len(lock) == 17
    assert {"fastapi", "uvicorn", "sqlalchemy", "pydantic", "pydantic-settings", "starlette", "pydantic-core"} <= names
    assert "uvicorn[standard]" not in (ROOT / "requirements.txt").read_text(encoding="utf-8")


def test_readme_builds_runs_with_volume_and_env_file_and_walks_one_room():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docker build -t roomready ." in readme
    assert re.search(r"docker run [^\n]*-p 8080:8080 [^\n]*-v roomready-data:/data [^\n]*--env-file \.env", readme), "the run line publishes 8080, mounts the volume and passes the env-file"
    curls = [line for line in readme.splitlines() if line.startswith("curl ")]
    assert curls and all("http://localhost:8080/" in line for line in curls), "every curl call runs as written"
    order = [next(i for i, line in enumerate(curls) if needle in line) for needle in ("/checkouts", "/assignments ", "/start", "/finish", "/inspections")]
    assert order == sorted(order), "checkout -> assign -> start -> finish -> inspect"
    assert 'CMD ["sh", "-c", "exec uvicorn roomready.app:app' in readme and "Verified on this build" in readme
