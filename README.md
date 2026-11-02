# RoomReady

Hotel housekeeping at Harbour View: checkout at eleven, arrivals from one, and in between sixty rooms go from dirty
to ready — cleaned, then inspected by somebody who did not clean them. This folder is the state of the project at the
end of this ticket.

## What is here

| Part | What it does |
|---|---|
| Rooms | 60 rooms on four floors and nine housekeepers loaded once from `seed/`; `GET /properties/{property}/rooms` filterable by floor, state and type, state derived from the rows — no stored flag; `GET …/rooms/{no}`, `GET …/housekeepers` |
| Checkouts | `POST /checkouts` with real constraints; 422 for a malformed body or a time the clock rules out, 400 room-not-occupied for a room with no guest |
| Cleaning | `POST /assignments`, `…/start`, `…/finish`: the clean timed against an injected clock, `clean_minutes` stored once |
| Refusals | Three refusals — step-skipped (`state`, `needs`), already-assigned (`assigned_to`), self-inspection — raised in the service, mapped once |
| Inspections | `POST /inspections`: a pass makes the room ready and stamps `margin_minutes` before the arrival, one transaction with the assignment close |
| History | An append-only event log per room and stay (`GET …/rooms/{no}/history`); the database refuses UPDATE and DELETE |
| The API | Routers per resource, one error shape for every error (framework 404/405 and the 500 included), docs with every refusal documented |
| Rules | `tests/rules.csv` — the rule table under three `INSPECTION_REQUIRED_FOR` settings; conditional inspection; `GET /settings` |
| The image | A Dockerfile, `HOST=0.0.0.0`, the board reachable from the front-desk screen |

## Run it

```bash
docker build -t roomready .
docker run -d --name roomready -p 8080:8080 roomready
```

The image starts the app with

```dockerfile
CMD ["sh", "-c", "exec uvicorn roomready.app:app --host \"$HOST\" --port \"$PORT\""]
```

so `HOST` and `PORT` come from the image's `ENV` defaults, `0.0.0.0` and `8080`.

Open `http://<back-office-pc-ip>:8080/` from the front-desk screen — the floor, the work screen, one room's card, the
rule book, the API and the runtime, with a walkthrough. Docs at `/docs`, health at `/healthz`.

### Verified on this build

Docker is not installed in the development environment used to prepare these files, so an image build, container run,
remote-host health/rooms checks, and image-size measurement have not been performed here. Run the commands above on a
Docker-equipped PC and replace this note with the observed Docker version, date, image tag, host port, health response,
60-room response, package comparison, image contents, and image size. Do not treat those checks as verified until run.

## Run it locally

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
python -m uvicorn roomready.app:app --host 127.0.0.1 --port 8080
python -m pytest            # each test on its own SQLite file with a clock it controls
```

## Conventions

- Every error is `application/problem+json`: `type, title, status, detail` plus the fields the ticket names.
- Ids are opaque strings (room `214`, stay `ST0029`, assignment `AS001`, inspection `IN001`, housekeeper `HK03`);
  database integers never reach the wire. Timestamps are UTC with a Z.
- Room state is one of occupied | dirty | assigned | cleaning | toinspect | ready | out_of_order, always derived from
  the latest stay, assignment, inspection and readiness rows. Minutes are whole numbers, rounded down.

<!-- learntube:start -->
---

[![tests](https://github.com/KUBENDHIRAN-V-B/roomready-python/actions/workflows/tests.yml/badge.svg)](https://github.com/KUBENDHIRAN-V-B/roomready-python/actions/workflows/tests.yml)

### Progress

- [x] Ticket 1 · The hotel, as something you can look at
- [x] Ticket 2 · A checkout makes a room dirty
- [x] Ticket 3 · Assign it, and start the clock
- [x] Ticket 4 · Three ways to say no
- [x] Ticket 5 · The room reaches ready
- [x] Ticket 6 · A clipboard nobody can re-tick
- [x] Ticket 7 · One file becomes an app
- [x] Ticket 8 · The rule table, and then the rule changes
- [x] Ticket 9 · It runs on the machine in the back office
- [ ] Ticket 10 · It survives being switched off

Built by KUBENDHIRAN V B on [LearnTube Guided Projects](https://guidedprojects.learntube.ai).
<!-- learntube:end -->
