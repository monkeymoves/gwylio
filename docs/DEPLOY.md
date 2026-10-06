# Deploying Gwylio

Gwylio (Welsh: to watch, to keep watch) is a Welsh environmental open-source
intelligence (OSINT) system. Its production form is a static website on
Firebase Hosting. This guide takes you from a clone to a live site. It also
covers the one-off steps that need the owner: a Firebase login and, for web
search, a Brave Search key. Nothing here has been done yet (see
`docs/STATUS.md`).

The site is static: every page is prerendered and reads JavaScript Object
Notation (JSON) snapshots that `gwylio publish` writes. No server runs in
production (`docs/adr/0001-static-site-on-firebase.md`).

## First deployment

1. **Install the tools.** You need Python 3.11, uv, Node 22, pnpm 10, GNU Make
   and the Firebase command line interface (CLI):

   ```bash
   npm install -g firebase-tools
   ```

2. **Install the project dependencies.** From the repository root:

   ```bash
   make setup
   ```

3. **Check the build is healthy.**

   ```bash
   make ci
   ```

4. **Log in to Firebase.**

   ```bash
   firebase login
   ```

5. **Choose the Firebase project.** No `.firebaserc` is committed, because
   the project id is yours. Create a project in the Firebase console first,
   then link this folder to it:

   ```bash
   firebase use --add
   ```

   Pick the project and give it an alias such as `default`. This writes
   `.firebaserc` locally. It is gitignored, as is the `.firebase/` deploy
   cache, so the project id stays out of the repository. You can also create
   the project from the command line with `firebase projects:create`.

6. **Rebuild the database and look at the site locally.** The database is
   gitignored, so a fresh clone has none.

   ```bash
   uv run --directory backend gwylio rebuild
   make dev
   ```

7. **Deploy.**

   ```bash
   make deploy
   ```

   The target does three things in order: `gwylio publish` (writes the
   snapshot into `frontend/static/data/` and `data/snapshots/`), `pnpm -C
   frontend build` (the static site into `frontend/build`) and `firebase
   deploy --only hosting`. If the `firebase` command is missing, it stops
   at once with a line saying so, before it publishes anything.

8. **Open the URL** that Firebase prints and check the Picture page shows the
   register.

## Every later deployment

After each scan cycle (see `skill/SKILL.md`) the facts are committed and the
snapshot has been published. Then run `make deploy`. It republishes, so it is
safe to run again. The site is only as fresh as the last deploy.

## What the hosting configuration does

`firebase.json` serves `frontend/build` with clean URLs (`/reports` rather
than `/reports.html`) and no trailing slash. It sets three header rules:

| Path | Header | Why |
|---|---|---|
| `/data/**` | `Cache-Control: no-cache` | The snapshot must never be served stale. |
| `/_app/immutable/**` | `Cache-Control: public, max-age=31536000, immutable` | Hashed build files never change, so cache them for a year. |
| `/products/*.md` | `Content-Type: text/markdown; charset=utf-8`, `no-cache` | Products open as Markdown, not a download. |

A test (`backend/tests/integration/test_hosting.py`) pins this file and the
`make deploy` recipe.

## Publishing without deploying

`make publish` writes the snapshot only. Use it to review the JSON, or in the
scan cycle, where deploying is the owner's step. `gwylio publish --at
<instant>` pins the clock for a reproducible snapshot.

## Before the first live scan

The deployment does not need these, but a useful register does.

- **Brave Search key.** Without one only the osint_feed discipline runs; web
  and site search print a skip line. Put the key in `BRAVE_API_KEY` or a
  gitignored `search_keys.txt` at the repository root, as a line
  `BRAVE_API_KEY=<key>`.
- **Install the analyst skill.** Link the folder, or place it in the project:

  ```bash
  ln -s "$PWD/skill" ~/.claude/skills/gwylio-scan
  ```

  Paths in the skill are relative to the repository root.
- **Contact address.** Set `GWYLIO_CONTACT_EMAIL` so the collector's
  User-Agent names someone to write to.

## Access control: the site is public by URL

Firebase Hosting serves every file to anyone with the link, including every
file under `/data/`. Version 1 therefore publishes only the register, which is
built from public sources, and nothing that needs protecting. Do not add
analyst notes, owners or drafts to a published read model until access
control exists.

ADR 0005 (`docs/adr/0005-access-control.md`, status proposed) sets out the
options: Firebase Authentication with an allow list, Cloud Run behind
Identity-Aware Proxy, or keeping the site public and publishing nothing
sensitive. Its key point is that a client-side login over static files is
not access control: the JSON files stay fetchable by URL. Real control means
the data is served only after a server, or database security rules, has
checked who is asking.

## Troubleshooting

- **`deploy: the firebase command is missing`**: run `npm install -g
  firebase-tools`, then `firebase login` and `firebase use --add`.
- **`firebase deploy` asks which project**: step 5 was skipped.
- **An empty site or missing pages**: `make publish` ran against an empty
  database. Run `gwylio rebuild`, then deploy again.
- **A stale page after a deploy**: hard refresh. Only `/data/**` is set to
  `no-cache`; the pages themselves follow Firebase's defaults.
- **Port 4173 or 5173 in use** when running `make e2e`, `make seed-screenshots`
  or `make dev`: stop the other server first.
