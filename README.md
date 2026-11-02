# RoomReady (Python)

[![tests](https://github.com/KUBENDHIRAN-V-B/roomready-python/actions/workflows/tests.yml/badge.svg)](https://github.com/KUBENDHIRAN-V-B/roomready-python/actions/workflows/tests.yml)

Hotel housekeeping: dirty, cleaned, inspected, ready — raced against the day's arrivals.

## Progress

- [x] Ticket 1 · The hotel, as something you can look at
- [x] Ticket 2 · A checkout makes a room dirty
- [x] Ticket 3 · Assign it, and start the clock
- [x] Ticket 4 · Three ways to say no
- [x] Ticket 5 · The room reaches ready
- [x] Ticket 6 · A clipboard nobody can re-tick
- [x] Ticket 7 · One file becomes an app
- [x] Ticket 8 · The rule table, and then the rule changes
- [ ] Ticket 9 · It runs on the machine in the back office
- [ ] Ticket 10 · It survives being switched off

## Run it

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest          # the tests
python -m uvicorn roomready.app:app --port 8080   # the app, on http://127.0.0.1:8080
```

## Built with

Python 3.12 · FastAPI · SQLAlchemy · Pydantic · pytest

---

Built by KUBENDHIRAN V B on [LearnTube Guided Projects](https://guidedprojects.learntube.ai).
