# Geneva Events API

Flask API backed by Firestore, plus a Selenium scraper for the City of Geneva
agenda.

## Setup

Requires Python 3.12+. The agenda is server-rendered, so the scraper does not
need Chrome, a browser driver, or JavaScript execution.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r api/requirements.txt
```

Configure Firebase in one of these ways:

- set `FIREBASE_CREDENTIALS_JSON` to the complete service-account JSON;
- use Google Application Default Credentials; or
- set `FIRESTORE_EMULATOR_HOST` for local development.

Set `CORS_ORIGINS` to a comma-separated list when the frontend is hosted on
additional domains. The defaults are `https://gee.bsilva.ch` and the local
Vite development server.

## Run

```bash
# Development API (http://localhost:8080)
python3 -m api.app

# Production API
gunicorn --bind 0.0.0.0:${PORT:-10000} api.app:app

# Scrape all agenda pages once
python3 -m scraper.scrape_articles

# Quick scraper smoke run
python3 -m scraper.scrape_articles --max-pages 1
```

Schedule the one-shot scraper with cron, a cloud scheduler, or a CI workflow.
Running scheduling inside the API process can duplicate jobs when Gunicorn uses
multiple workers.

This repository includes a GitHub Actions workflow that performs a complete
scrape every 30 minutes, upserts the current events, and removes records that
are no longer on the agenda. Add the Firebase service-account JSON as the
repository secret `FIREBASE_CREDENTIALS_JSON`, then run **Sync Geneva events**
manually once to verify it. Scheduled GitHub Actions jobs can start a few
minutes late, so this is near-real-time synchronization rather than an
instantaneous feed.

Changes to the scraper also trigger an immediate synchronization when pushed
to `main`, so fixes do not have to wait for the next scheduled interval.

To perform the same safe synchronization locally:

```bash
python3 -m scraper.scrape_articles --prune
```

Pruning is rejected when `--max-pages` is used, and an empty scrape is never
written. By default, pruning is also rejected if the scrape returns fewer than
50% of the existing record count. Override that threshold with
`PRUNE_MIN_RATIO` only when a large legitimate drop is expected.

## API

- `GET /health` — liveness check (does not contact Firestore)
- `GET /events/` — all events ordered by date
- `GET /events/?when=today|tomorrow|this_week|this_weekend` — date presets
- `GET /events/?date_from=2026-07-14&date_to=2026-07-20&category=Concert` —
  combinable inclusive date range and category filters
- `GET /events/?start_time_from=18:00&start_time_to=23:00` — known-time events
- `GET /events/<id>` — one event, used when a detail page is opened directly
- `GET /events/<id>/related?limit=4` — bounded related events near its date
- `GET /events/tag/<tag>` — events with an exact normalized tag
- `GET /events/date?day=14&month=3&year=2026` — filter by one or more date parts
- `GET /saved-events` — list the verified user's saved events
- `PUT /saved-events/<id>` — idempotently save an existing event
- `DELETE /saved-events/<id>` — remove the verified user's save
- `GET /saved-events/status?event_id=<id>` — check saved state for up to 100 IDs

Successful collection responses are JSON arrays, including an empty array when
there are no matches. Missing event IDs return `404`; bad date-filter input
returns `400`; database configuration failures return `503`.

Filters are URL-based and combinable. Dates use `YYYY-MM-DD`, times use
`HH:MM`, and unsupported or contradictory filters return `400`. Unknown event
times are excluded from time filters rather than treated as midnight.

Saved-event routes require a Firebase ID token in the `Authorization: Bearer`
header. The API verifies the token server-side and derives ownership from its
UID; clients never submit a user ID as proof of identity.

See [docs/AUDIT_AND_ROADMAP.md](docs/AUDIT_AND_ROADMAP.md) for the schema
reliability matrix, migration notes, constraints, and phased roadmap.

Location detail enrichment is cached and rate-limited. Optional controls are
`LOCATION_ENRICH_LIMIT` (default `20` records/run),
`LOCATION_REQUEST_DELAY_SECONDS` (default `0.25`) and
`LOCATION_REFRESH_DAYS` (default `30`). No geocoding credentials are required.

## Test

```bash
pip install -r requirements-dev.txt
pytest -q
python3 -m compileall -q api scraper tests
```

## Docker

```bash
docker build -t geneva-events-api .
docker run --rm -p 10000:10000 \
  -e FIREBASE_CREDENTIALS_JSON="$FIREBASE_CREDENTIALS_JSON" \
  geneva-events-api
```

The scraper uses ordinary HTTP requests and can run in the same Python
environment without browser packages.
