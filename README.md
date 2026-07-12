# Geneva Events API

Flask API backed by Firestore, plus a Selenium scraper for the City of Geneva
agenda.

## Setup

Requires Python 3.12+ and Chrome/Chromium when running the scraper.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r api/requirements.txt
```

Configure Firebase in one of these ways:

- set `FIREBASE_CREDENTIALS_JSON` to the complete service-account JSON;
- use Google Application Default Credentials; or
- set `FIRESTORE_EMULATOR_HOST` for local development.

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

## API

- `GET /health` — liveness check (does not contact Firestore)
- `GET /events/` — all events ordered by date
- `GET /events/tag/<tag>` — events with an exact normalized tag
- `GET /events/date?day=14&month=3&year=2026` — filter by one or more date parts

Successful event responses are JSON arrays. Empty result sets return `404`; bad
date-filter input returns `400`; database configuration failures return `503`.

## Docker

```bash
docker build -t geneva-events-api .
docker run --rm -p 10000:10000 \
  -e FIREBASE_CREDENTIALS_JSON="$FIREBASE_CREDENTIALS_JSON" \
  geneva-events-api
```

The API image does not install Chrome. Run the scraper in an environment that
provides Chrome/Chromium, or extend the image with a browser package.
