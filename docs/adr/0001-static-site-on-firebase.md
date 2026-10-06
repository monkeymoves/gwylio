# ADR 0001: Static site on Firebase Hosting; the API is a development tool

- Status: accepted
- Date: 2026-10-06
- Deciders: Luke Maggs, with the planning agent

## Context

Gwylio needs a front end that analysts and colleagues can open without
running anything. The register changes when a scan is ingested, at most a few
times a month, not continuously. The project already uses Firebase, there is
no budget or need for an always-on server, and nobody will be on call for one.
Analysis happens outside the app, so the site only has to read.

## Decision

Production is a static SvelteKit site built with `@sveltejs/adapter-static`,
every page prerendered, deployed to Firebase Hosting. It reads JSON snapshots
that `gwylio publish` writes into `frontend/static/data/` (and keeps a copy in
`data/snapshots/`). There is no server in production.

The FastAPI application is a local development and analyst tool. It serves
the same JSON shapes as the snapshot at `/api/v1/<name>`, read only, and a
contract test asserts that the exporter output equals the API output on the
seed database. The front end data client can switch its base URL between the
snapshot and the API in development.

Cloud Run is a designed seam, not built: if a live API is ever needed, the
same FastAPI application can be containerised and placed behind Firebase
Hosting rewrites without changing the front end's data shapes.

## Consequences

- Hosting is cheap, fast and has nothing to patch or keep running.
- The site is only as fresh as the last `publish`; that matches the cadence of
  scans and ingests.
- Firebase Hosting is public by URL. Version 1 publishes only the register and
  must not carry anything that needs access control. Firebase Authentication
  is the planned answer if that changes, and would get its own ADR.
- Every view must work from prerendered pages and client-side filtering over
  the snapshot; there is no server-side search.
- Two serving paths (snapshot and API) must stay identical; the contract test
  guards that.

## Alternatives considered

- **Server-rendered SvelteKit on Cloud Run.** Fresher data, but an always-on
  service to run, secure and pay for, with no current need.
- **FastAPI plus a single-page app in production.** Same costs as above, and a
  second production code path to test.
- **Hand-written single HTML dashboard.** What the previous tool did; it does
  not scale to the planned pages and cannot be component tested.
