# Application audit and implementation roadmap

Audit date: 2026-07-14

## Current architecture

- **Frontend:** not present in this repository. Configured origins indicate a
  separate Vite application, but its routes, components and styles cannot be audited here.
- **Backend:** Flask with an `/events` blueprint and `/health`; routes call a
  small service/repository layer.
- **Database:** Firestore collection `Events`. There is no migration system;
  event documents are merge-upserted by the scraper.
- **Authentication:** none. A sample JWT login is commented out and is not an account system.
- **Scraper:** one-shot paginated HTTP/BeautifulSoup City of Geneva scraper. It
  batch-upserts deterministic documents and safely prunes after completeness checks.
- **Tests:** none existed at audit time. Pytest now covers parsing, normalization and filters.
- **Deployment:** Python 3.12, Gunicorn, Render, Docker, and scheduled GitHub Actions scraping.

## Event data reliability

| Field | Status | Notes |
| --- | --- | --- |
| title | reliable | Required; incomplete cards are rejected. |
| description/image/category | optional | Taken directly from agenda cards. |
| start date | reliable | Required; stored in legacy `date` and canonical `start_at`. |
| start time | optional/reliable | Explicit time only; `has_start_time` distinguishes unknown time. |
| end date/time | optional | Parsed only from explicit ranges. |
| venue/address/postal code/city | unavailable | Not reliably structured on listing cards. |
| latitude/longitude | unavailable | Must not be fabricated or browser-geocoded. |
| price | partial | Explicit `100% gratuit` becomes `free`; otherwise `unknown`. |
| source URL | reliable when linked | Original absolute URL is preserved. |
| organiser | unavailable | Not reliably present on cards. |
| scraping source | reliable | `geneve_city_agenda`. |
| last update | reliable | UTC `scraped_at` and `updated_at`. |

Legacy `day`, `month`, `year`, `date`, `tag` and `img` remain to avoid breaking
consumers. `raw_date` is retained for diagnostics.

## Risks and constraints

1. Third-party markup can change; missing-card and empty-scrape guards protect production.
2. Existing documents gain fields after the next successful scrape. Merge writes are additive.
3. Date bounds run in Firestore; category/time checks run on the bounded result
   to avoid mandatory composite indexes at the current data volume.
4. Saved events, submissions, roles and administration require real identity
   verification and Firestore authorization design.
5. Calendar, map, detail, navigation and accessibility UI work belongs in the absent frontend.

## Phased plan

1. Normalize schedule/source fields additively and test parsing.
2. Expose combinable URL filters for reliable date/category/time data.
3. Enrich detail pages for venue/address only after reliability and scrape cost are proven.
4. Reuse the query contract for list/calendar views in the frontend repository.
5. Implement production authentication, saved-event ownership, personal calendar and ICS.
6. Only then add moderated submissions, organiser roles and administration.

## Additive migration and rollback

Run `python3 -m scraper.scrape_articles --prune` to populate `start_at`,
`end_at`, `has_start_time`, `raw_date`, `price_type`, `source`, `scraped_at`, and
`updated_at`. No field is renamed or removed. Roll back by deploying the prior
scraper/API; extra fields may safely remain. Physical removal should only use a
separately reviewed admin script after a Firestore export, so no destructive
rollback command is included.
