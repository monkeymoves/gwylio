# ADR 0005: Access control for the hosted site

- Status: proposed
- Date: 2026-10-06
- Deciders: Luke Maggs (to decide), with the work package 10 builder

## Context

ADR 0001 puts the production site on Firebase Hosting as static, prerendered
pages that read JSON snapshots published by `gwylio publish`. Firebase
Hosting serves every file to anyone who has the URL: there is no login, and
every snapshot file under `/data/` can be fetched directly, whatever the
pages show. Version 1 therefore publishes only the register, which is built
from public sources, and must not carry anything that needs access control.

That may change. Natural Resources Wales (NRW) colleagues may want analyst
notes, owners, follow-up actions or draft products on the site, and some of
those are not for public reading. This record sets out the options so the
owner can choose before anything sensitive is published. Nothing here is
built yet.

One constraint shapes every option: hiding a page behind a client-side login
is not access control on a static host. If the JavaScript Object Notation
(JSON) files stay on Firebase Hosting, anyone can still fetch them. Real
control means the data is served only after a server, or a database's
security rules, has checked who is asking.

## Decision

Proposed: keep the site public and publish nothing sensitive (option 3)
for version 1, and adopt option 1 (Firebase Authentication with an allow
list) when the first sensitive field needs to reach the site. Option 2 stays
the fallback if the organisation requires its own identity provider in front
of everything.

The rule a reviewer can check today: no field that is not already in the
public register (built from public pages) goes into a published snapshot,
and `frontend/static/data/` holds only what `gwylio publish` writes from the
register.

## Options

### Option 1: Firebase Authentication with an allow list

Users sign in with Firebase Authentication (Google or Microsoft accounts).
An allow list of email addresses or a domain (held as custom claims or in a
small Firestore collection) decides who may read. To be real control, the
snapshot must move off the public static host: either a Cloud Function or
Cloud Run service behind a Hosting rewrite serves `/data/**` after verifying
the user's identity token, or the snapshot is written to Cloud Storage or
Firestore behind security rules that check the claim. The pages themselves
can stay static.

- For: stays inside Firebase, which the project already uses; free tier
  likely sufficient; per-person access and revocation.
- Against: adds a sign-in flow, a token-checking service or security rules,
  and a way to manage the allow list; `gwylio publish` gains a second
  target; the data client must send the token.

### Option 2: Cloud Run behind Identity-Aware Proxy

Serve the built site and the snapshot (or the FastAPI read API, the seam
ADR 0001 names) from Cloud Run, with Google Cloud Identity-Aware Proxy (IAP)
in front. IAP checks every request against Google Cloud Identity and Access
Management (IAM) before it reaches the service.

- For: everything is behind the proxy, pages and data alike; no
  authentication code in the app; access is managed in IAM, where an
  organisation's administrators expect it.
- Against: needs a Google Cloud project with a load balancer, so a monthly
  cost; leaves Firebase Hosting; IAP works most simply with Google
  identities, so NRW's own accounts may need workforce identity federation.

### Option 3: Keep the site public and publish nothing sensitive

Keep ADR 0001 as it stands. The register holds only what public sources
already say; analyst-only material stays in the repository (private on
GitHub) and in chat, not on the site.

- For: no new moving parts; nothing to secure or pay for; matches version 1.
- Against: the site cannot carry owners' notes, draft products or anything
  embargoed; the URL can be shared further than intended, so even the
  framing of public material (what is followed up, by whom) is visible.

## Consequences

- Until this record is accepted with option 1 or 2, every change that adds
  a field to a published read model must ask whether it is public. The
  snapshot contract test already pins what is published.
- Choosing option 1 or 2 means a new work package: the serving change, the
  data client sending credentials, an end to end test that an anonymous
  request for `/data/meta.json` is refused, and an update to
  `docs/DEPLOY.md`.
- Revisit when the first sensitive field is proposed, or if NRW asks for the
  site on its own identity provider.

## Alternatives considered

- **A client-side password or login screen over the static files.** Rejected:
  the files remain fetchable by URL, so it gives the appearance of control
  without the substance.
- **Obscure URLs.** Rejected for the same reason: anyone who has the link
  has everything.
