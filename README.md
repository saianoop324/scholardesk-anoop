# ScholarDesk

A local, single-user Semantic Scholar research workspace. Python 3.11 or newer; no runtime packages, paid AI services, or model training required.

## Run

1. Copy `.env.example` to `.env`.
2. Put your key after `SEMANTIC_SCHOLAR_API_KEY=` in `.env`.
3. Run `python3 server.py` from this folder.
4. Open http://localhost:8000.

Restart the server after changing `.env`. Search can use unauthenticated public access when no key is configured, but shared limits apply. Keys never go to the browser. The server binds to localhost and is intended for personal local use, not internet deployment.

## Features

- Filtered paper search, author search and profiles.
- Paper details, API-provided TLDR summaries when available, and open PDF links.
- References, citing papers, and a labeled SVG citation neighborhood.
- Pretrained Semantic Scholar recommendations, with negative feedback and library seeds.
- SQLite library, projects, reading/review status, notes, inclusion/exclusion tracking.
- Up to six papers compared side by side.
- Batch identifier imports and JSON, BibTeX, RIS, CSV exports.
- Saved searches with manual checks for results absent from the original snapshot.
- Library publication timeline and metrics.
- Latest dataset release browser with documentation links.
- Server-side caching, serialized requests, and bounded retries for API throttling.

## Scope and limits

No chat assistant is included: Semantic Scholar's documented APIs provide recommendations and summaries, not a ready-to-embed conversational assistant. No additional paid model provider is used.

Metadata may be missing. PDF links do not guarantee that publishers permit embedding or full-text retrieval. Citation maps show up to 40 relationships (12 graph nodes), author pages show the first 40 publications, and recommendation responses contain up to 30 papers. Paper search paginates in sets of 20 within upstream limits. Saved searches compare the first 20 relevance-ranked results; they are manual checks, not scheduled alerts or exhaustive publication monitoring. Dataset browsing does not download or index the corpus. Analytics describe saved records rather than the entire field. Exports use available metadata and may need bibliographic cleanup.

Library data lives in `research.sqlite3`; back up this file to preserve projects and notes. `.env` and the database are ignored by Git. JSON exports include your research notes. This is a single-user app, without account synchronization.

## Tests

Run `python3 -m unittest discover -s tests -v`. Tests use a temporary database and mocked upstream API responses, so they do not need an API key.

## Render deployment

For a password-protected free trial deployment, follow [RENDER.md](RENDER.md). The included `render.yaml` configures the service. Render hosting uses HTTPS, its assigned hostname, and an app password. Free-hosted SQLite storage is temporary; export important research or configure persistent storage before relying on it.
