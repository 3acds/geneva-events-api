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

The scraper also requires `FIREBASE_STORAGE_BUCKET`. It downloads each source
image, validates and normalizes it to WebP, then uploads it to
`events/<event-id>/cover.webp`. Firestore therefore exposes a stable image URL
owned by this project rather than a third-party hotlink.

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
and add the repository variable `FIREBASE_STORAGE_BUCKET` (for example,
`your-project.firebasestorage.app`). Then run **Sync Geneva events** manually
once to verify it. Scheduled GitHub Actions jobs can start a few
minutes late, so this is near-real-time synchronization rather than an
instantaneous feed.

To perform the same safe synchronization locally:

```bash
python3 -m scraper.scrape_articles --prune
```

Pruning is rejected when `--max-pages` is used, and an empty scrape is never
written. By default, pruning is also rejected if the scrape returns fewer than
50% of the existing record count. Override that threshold with
`PRUNE_MIN_RATIO` only when a large legitimate drop is expected.

If downloading a refreshed image fails, the synchronization retains the last
valid Storage image and its source metadata. A placeholder is used only when
an event has never had a valid downloadable image.

## API

- `GET /health` — liveness check (does not contact Firestore)
- `GET /events/` — all events ordered by date
- `GET /events/<id>` — one event, used when a detail page is opened directly
- `GET /events/tag/<tag>` — events with an exact normalized tag
- `GET /events/date?day=14&month=3&year=2026` — filter by one or more date parts

Successful collection responses are JSON arrays, including an empty array when
there are no matches. Missing event IDs return `404`; bad date-filter input
returns `400`; database configuration failures return `503`.

## Docker

```bash
docker build -t geneva-events-api .
docker run --rm -p 10000:10000 \
  -e FIREBASE_CREDENTIALS_JSON="$FIREBASE_CREDENTIALS_JSON" \
  geneva-events-api
```

The API image does not install Chrome. Run the scraper in an environment that
provides Chrome/Chromium, or extend the image with a browser package.
