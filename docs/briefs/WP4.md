# WP4 brief: real collectors (web, site, feed, academic)

You are building work package 4 of the project described in `docs/PLAN.md`
(read it fully first). Then read `CLAUDE.md`, the briefs WP0 to WP3 under
`docs/briefs/`, and the code under `backend/src/gwylio/`, especially
`collection/ports.py` (the `Collector` protocol and `CollectResult`),
`collection/service.py` (`RunScan`), `infrastructure/collectors/fake.py`,
`infrastructure/sqlite/`, `infrastructure/config/settings.py`, and the shipped
`config/instrument.json` and `config/sources.json` (which queries carry which
disciplines, how feed queries carry keywords, how site queries name sources).
Follow their conventions exactly. Project root is `gwylio/`. Do not touch
anything outside it except to READ `/home/user/NRW-Scan-Tool/collect.py`
lines 60 to 130 and 285 to 330 for the old Brave, RSS and academic call shapes
(patterns only, never code reuse). Do not run git.

## Environment facts

- Outbound HTTPS goes through a proxy. httpx honours `HTTPS_PROXY` by default.
  If TLS verification fails, set `verify` from the `SSL_CERT_FILE` environment
  variable or `/root/.ccr/ca-bundle.crt` when present; never disable
  verification. Read `/root/.ccr/README.md` if a transfer is refused.
- There is NO Brave key in this environment. The Brave collectors must be
  fully tested on recorded fixtures and simply absent (with one warning line)
  when no key is configured.
- Tests never touch the network. Mark any optional live test
  `@pytest.mark.live` and exclude that marker by default in `pyproject.toml`.

## Deliverables

`backend/src/gwylio/infrastructure/http/client.py`

- `HttpClient` over `httpx.Client`: 20 second timeout, a User-Agent naming
  gwylio and a contact address read from settings (`GWYLIO_CONTACT_EMAIL`,
  default `gwylio@example.invalid`), `get_json(url, params, headers)` and
  `get_text(...)`. Retries: up to 3 retries on 429, 5xx, timeouts and
  connection errors, exponential backoff starting at 1 second with full
  jitter, honouring `Retry-After` when present; retries are injectable sleeps
  so tests run instantly. A per-host token bucket rate limiter (`RateLimit(
  requests_per_second)`), 1 request per second for `api.search.brave.com`,
  5 per second elsewhere. Counts requests made (including retries) so the run
  budget is honest. Raises `HttpError(status, url)` after retries are spent.

`backend/src/gwylio/infrastructure/collectors/`

- `brave_web.py`: Brave Search API `GET https://api.search.brave.com/res/v1/web/search`
  with header `X-Subscription-Token`, params `q`, `count=20`, `country=GB`,
  `search_lang=en`, `safesearch=off`. Maps `web.results[]` to `RawHit(url,
  title, description as snippet, page_age or age parsed to a date when
  possible)`. One request per query; `requests_used` reported exactly.
- `brave_site.py`: same endpoint, one request per (query, source) pair with
  `q = "site:<domain> (<phrase OR phrase ...>)"`, honouring the remaining
  budget (stop and warn when it would be exceeded).
- `feed.py`: fetches each active feed source for the query's lane, parses RSS
  2.0 and Atom with the standard library `xml.etree`, extracts title, link,
  summary or description or content, and published date (RFC 822 or ISO).
  Keeps an item only if any of the query's keywords appears in title or
  summary (case-insensitive). A malformed or unreachable feed yields zero
  hits plus a warning naming the source; it never raises out of `collect`.
  Records the source id on each hit.
- `openalex.py` and `crossref.py`: enabled only when `GWYLIO_ACADEMIC=1`.
  OpenAlex `GET https://api.openalex.org/works` with `search`, `filter=
  from_publication_date:<a year ago>`, `per_page=15`, `mailto`. Crossref `GET
  https://api.crossref.org/works` with `query`, `filter=from-pub-date:...`,
  `rows=15`, `mailto`, and the User-Agent contact. Map to RawHit with the DOI
  URL. Both carry a note in the module docstring that the academic indexes
  ignore geography, so the relevance gate does the filtering.
- `registry.py`: `build_collectors(settings, http) -> dict[Discipline,
  Collector]` plus `missing_disciplines(requested, available) -> list[str]`
  with reasons (no Brave key; academic flag off). The fake collector is never
  in the real registry.

CLI

- `gwylio collect [--discipline D ...]` (no flag): builds the real registry,
  runs `RunScan` with SQLite persistence and the candidates file exactly like
  `--fake`, prints the funnel table and the warnings, and exits 0 even when
  some requested disciplines were unavailable (it prints which and why), but
  exits 3 when NO requested discipline is available. Default disciplines:
  all OSINT disciplines in the instrument.
- `gwylio probe "<text>" --discipline D` now uses the real registry; writes
  nothing.

Settings additions: `brave_api_key` (from `GWYLIO_BRAVE_API_KEY`, then
`BRAVE_API_KEY`, then a `search_keys.txt` file in the project root if present,
which must be gitignored), `academic_enabled`, `contact_email`.

## Tests (`backend/tests/integration/collectors/`, all with `respx`)

- Cassettes as JSON files under `backend/tests/fixtures/http/<collector>/`:
  one realistic Brave web response (hand-written, 5 to 8 results, realistic
  Welsh environmental titles and gov.wales, senedd.wales, bbc.co.uk URLs), one
  Brave site response, one RSS 2.0 feed, one Atom feed, one malformed feed,
  one OpenAlex response, one Crossref response.
- HTTP client: 429 then 200 succeeds with two requests counted; three 5xx then
  200 succeeds; four 5xx raises `HttpError`; `Retry-After: 2` is honoured via
  the injected sleep; rate limiter spaces two Brave calls by at least one
  second of injected sleep.
- Each collector maps its cassette to the expected `RawHit`s (assert exact
  field values for at least two hits each).
- Feed: keyword filter keeps and drops as expected; malformed feed gives zero
  hits and one warning; a 404 feed likewise.
- Site collector stops at the remaining budget and warns.
- Registry: no key means no Brave collectors and a reason; flag off means no
  academic collectors and a reason.
- End to end: `collect` with a respx-mocked Brave and feeds writes a
  candidates file whose funnel you assert by hand from the cassettes.

## Live run (after tests are green)

Run `uv run --directory backend gwylio collect --discipline osint_feed` once
for real. Feeds in `config/sources.json` that fail should produce warnings,
not failures. Commit nothing yourself, but leave the resulting
`data/candidates/<run_id>.json` and `data/exports/runs.json` in place and
report the funnel, the warnings, and how many feeds responded. If the network
blocks every feed, say so plainly; do not fabricate a run.

## Style rules

No em or en dashes anywhere. British English. Only infrastructure touches
the network; the domain stays pure.

## Definition of done

1. `make ci` exits 0 from `gwylio/`.
2. The live feed run above has been attempted and reported honestly.
3. Report back: commands run with status lines, test counts before and after,
   deviations and why, and notes for WP5 (anything about candidates and
   sightings the Intelligence context must know).
