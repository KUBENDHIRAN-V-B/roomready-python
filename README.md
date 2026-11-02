# RoomReady

Hotel housekeeping at Harbour View: checkout at eleven, arrivals from one, and in between sixty rooms go from dirty
to ready — cleaned, then inspected by somebody who did not clean them. This folder is the state of the project at the
end of its last ticket.

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
| Running it | Data on a volume, every setting from an env-file, `.dockerignore`, logs on stdout |

## Run it

```bash
docker build -t roomready .
docker run -d --name roomready -p 8080:8080 -v roomready-data:/data --env-file .env.example roomready
```

The image starts the app with

```dockerfile
CMD ["sh", "-c", "exec uvicorn roomready.app:app --host \"$HOST\" --port \"$PORT\""]
```

so `HOST` and `PORT` come from the env-file (the image carries only its defaults, `0.0.0.0` and `8080`), and so
does everything else: the database path, the inspection policy, the seed folder.

Open `http://<back-office-pc-ip>:8080/` from the front-desk screen — the floor, the work screen, one room's card, the
rule book, the API and the runtime, with a walkthrough. Docs at `/docs`, health at `/healthz`,
logs with `docker logs -f roomready`.

The six a.m. power test: `docker rm -f roomready`, then the same `docker run` — every room is exactly as housekeeping
left it, because the database lives on the `roomready-data` volume (the Runtime screen's Before restart / After
restart buttons compare the board across the restart). To change a rule, edit the env-file (copy `.env.example` to
`.env` and pass `--env-file .env`) and restart; no rebuild:

```
DATABASE_URL=sqlite:////data/roomready.db
INSPECTION_REQUIRED_FOR=Standard,Deluxe,Suite
STALL_AFTER_MINUTES=60
SEED_DIR=seed
HOST=0.0.0.0
PORT=8080
```

### Verified on this build

Docker is not installed in the development environment used to prepare these files, so an image build, container run,
remote-host health/rooms checks, restart test, and image-size measurement have not been performed here. Record the
Docker version, date, tag, port mapping, volume name, env-file, health and rooms responses, log counts, `docker diff`,
and image size after running the checks on a Docker-equipped PC. Do not treat those checks as verified until run.

## Run it locally

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
python -m uvicorn roomready.app:app --host 127.0.0.1 --port 8080
python -m pytest            # each test on its own SQLite file with a clock it controls
```

## One room, checkout to ready

```bash
curl -s -X POST http://localhost:8080/checkouts -H 'content-type: application/json' -d '{"room":"214","at":"2026-09-28T10:40:00Z","arrival_at":"2026-09-28T13:00:00Z"}'
# {"stay_id":"ST0029","room":"214","checked_out_at":"2026-09-28T10:40:00Z","state":"dirty"}      ← Location: /properties/harbour-view/rooms/214
curl -s -X POST http://localhost:8080/assignments -H 'content-type: application/json' -d '{"room":"214","housekeeper":"HK03"}'
# {"assignment_id":"AS001","room":"214","assigned_to":"Sunita","assigned_at":"…"}
curl -s -X POST http://localhost:8080/assignments/AS001/start      # {"assignment_id":"AS001","started_at":"…"}            the clock starts
curl -s -X POST http://localhost:8080/assignments/AS001/finish     # {"assignment_id":"AS001","finished_at":"…","clean_minutes":36}
curl -s -X POST http://localhost:8080/inspections -H 'content-type: application/json' -d '{"room":"214","inspector":"HK01","result":"pass"}'
# {"inspection_id":"IN001","room":"214","cleaned_by":"Sunita","inspected_by":"Grace","result":"pass","state":"ready","ready_at":"…","arrival_at":"…","margin_minutes":40}
curl -s http://localhost:8080/properties/harbour-view/rooms/214      # ready
curl -s http://localhost:8080/properties/harbour-view/rooms/214/history   # checked_out → assigned → started → finished → inspected
```

The checkout time must not be in the future: on a live server use a time from the last hour.

Refusals to try: check 214 out again → 400 room-not-occupied; a blank or future `at` → 422 naming the field; assign an
occupied room → 409 step-skipped with `state` and `needs`; assign a room Sunita is on → 409 already-assigned naming
her; finish before start → 409 step-skipped (`needs: start`); let Sunita inspect her own room → 409 self-inspection.

## Conventions

- Every error is `application/problem+json`: `type, title, status, detail` plus the fields the ticket names.
- Ids are opaque strings (room `214`, stay `ST0029`, assignment `AS001`, inspection `IN001`, housekeeper `HK03`);
  database integers never reach the wire or a log line. Timestamps are UTC with a Z.
- Room state is one of occupied | dirty | assigned | cleaning | toinspect | ready | out_of_order, always derived from
  the latest stay, assignment, inspection and readiness rows. Minutes are whole numbers, rounded down.
- Logs are one line per request and per event on stdout; the guest never appears in a log line or an event.

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
- [x] Ticket 10 · It survives being switched off

Built by KUBENDHIRAN V B on [LearnTube Guided Projects](https://guidedprojects.learntube.ai).
<!-- learntube:end -->
