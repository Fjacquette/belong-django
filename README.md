# Belong Django

Server-rendered Django app for Belong — a card-driven social experience using Tailwind CSS and HTMX.

## Stack
- Python 3.12, Django 5.x, SQLite (dev)
- Tailwind CLI (via `npx`) for styles
- HTMX (CDN script in base template)
- `uv` for dependency management

## Local dev and browser-test workflow

Requires Python 3.12+, `uv`, and Node.js/`npx` (for the dev Tailwind watcher).
Run these commands from the main checkout:

```bash
# Start dev from your current feature branch, on http://127.0.0.1:8000
./start_belong.sh

# In another terminal, create or refresh browser-test from origin/master
./scripts/refresh-test.sh

# Start browser-test on http://127.0.0.1:8001
./start_test.sh
```

The launchers install locked Python dependencies, create missing local config and
secret files, check Django, and apply migrations. A newly created database starts
empty: use **Sign up** in the browser to create an account, then add activities.
Existing databases, keys, and configuration are preserved; no data is copied or
reseeded. Dev keeps your current `db.sqlite3` and watches Tailwind and Python
changes. Browser-test uses master's committed CSS; restart it after refreshing
so dependency changes and migrations are applied. Stop either launcher with
Ctrl+C. Both bind only to `127.0.0.1`; there is no public deployment.

Browser-test lives in the ignored `.worktrees/test/` directory, on the dedicated
`browser-test` branch tracking `origin/master`. It is a separate checkout with
its own `.venv`, `db.sqlite3`, `.env.local`, and `.django-secret-key`. It shows
integrated master, even while the main checkout contains unfinished feature
work. It is a **persistent environment for browser/product evaluation**, separate
from the temporary database created by `python manage.py test`.

Refresh fetches master and fast-forwards only the browser-test branch. It does
not switch, merge into, or clean your dev branch. Local source edits or commits
in browser-test stop refresh with an error; preserve them before retrying. No
reset, database copying, or database deletion is performed.

Dev and test use different session/CSRF cookie names because browsers share
cookies between localhost ports. You can stay logged into both independently.

## Local configuration

Each checkout reads its own ignored `.env.local` file. The launchers create this
file once; edit it to customize that environment. Values use `KEY=value` syntax,
with quotes for spaces and optional `#` comments. No shell expansion is performed.

| Setting | Local default | Purpose |
| --- | --- | --- |
| `BELONG_ENV` | `dev` in main; `test` in worktree | Environment name and cookie isolation |
| `DJANGO_DEBUG` | `true` | Accepts true/false, 1/0, yes/no, on/off |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | Comma-separated hostnames |
| `DJANGO_DB_PATH` | `db.sqlite3` | Relative to that checkout, or an absolute path |
| `DJANGO_SECRET_KEY` | Unset | Optional alternative to that checkout's private key file |

The generated secret key is stored in `.django-secret-key` with owner-only
permissions. Each environment gets a separate key. Existing keys are retained.
Keep database paths distinct; the launchers reject paths shared between dev and test.
The launchers use the selected checkout's configuration rather than inheriting
Django configuration or an active virtualenv from the other environment.

For direct Django commands, process environment variables override `.env.local`.
After initial setup:

```bash
# Dev checks/tests; Django creates an isolated automated test database
.venv/bin/python manage.py check
.venv/bin/python manage.py test

# Browser-test maintenance, using that checkout's local config/database
(cd .worktrees/test && .venv/bin/python manage.py check)
(cd .worktrees/test && .venv/bin/python manage.py createsuperuser)
```

For a new checkout, the launcher handles setup; no manual secret generation or
file copying is needed. Production/Sage setup is deferred to a later issue.

## Seeding Notes

Demo seeding is an explicit command; launchers never run it automatically.
After setting up browser-test once with `./start_test.sh`, stop it, then populate
its database from the main checkout:

```bash
(cd .worktrees/test && .venv/bin/python manage.py seed_demo)
```

Restart `./start_test.sh` and log in as `belong_demo` / `demo123`.
The optional demo administrator is `belong_demo_admin` / `admin123`.
These initial credentials are **local dev/test only**; the command refuses other
environment names. For dev, use `.venv/bin/python manage.py seed_demo` after
applying migrations with the launcher or `manage.py migrate`.

The command retains the nine existing activity examples, twenty categories,
friends, coordination groups, response examples, and available repository artwork.
Each seed-owned record is identified by a `DemoSeedRecord` entry. Repeated runs
refresh only known demo data, without duplicating it or resetting account
passwords, privileges, or existing responses. Untracked activities created during
review remain intact, even when hosted by a demo account or sharing a demo title.
Existing accounts (including legacy `admin`/`demo`), categories, and uploaded
images are not adopted by name. Demo categories use `belong-demo-` slugs.

If an untracked account already uses a reserved demo username, or a tracked demo
activity has been transferred to another owner, the command stops and rolls back
the entire run. Resolve the conflict without deleting personal data, then retry.
The ownership migration adds a tracking table; it does not claim legacy records.
Manually edited seed-owned activity examples may be refreshed on the next run.

## Tailwind Production Build
For a one-off build (e.g., before deploying), run:
```bash
source .venv/bin/activate
npx tailwindcss@3.4.13 -i assets/tailwind.css -o static/css/tailwind.css --minify
```

Tailwind scans templates and the app Python form files containing literal widget
classes. Commit rebuilt `static/css/tailwind.css` with changes to those classes so
the browser-test checkout receives the same styling.

## Pilot audience and image rules

Activity discovery, details, and participation actions share the same audience
rule: hosts always have access; Everyone includes authenticated users; Friends
includes direct friends; Friends of friends includes at most two friendship hops.
Group and custom audiences are not offered by creation/admin forms yet; existing
rows with these or unknown audience values remain host-only. Unauthorized detail
and participation requests return 404.

Image uploads support JPEG, PNG, and non-animated WebP. Pillow validates actual
image bytes; GIF, SVG, other formats, corrupt files, and animated images are
rejected. Image URLs require login and serve a MIME type and Content-Length
derived from actual bytes, with private/no-store caching and `nosniff`, including
for legacy rows with incorrect metadata. Invalid legacy assets return 404 without
rewriting stored data. BinaryField storage is unchanged.

Action URL fields accept only HTTP/HTTPS links (or blank values). Legacy unsafe
links render as `#`. Default response choices are Interested, Count me in, and
I have a question; Declined remains an explicit opt-in. The join shortcut prefers
Interested, then Count me in, and leaves responses unchanged when neither is
available. Cards offer direct Interested and Count me in buttons; activity
details show all allowed response buttons.
Responses update in place with HTMX, can be changed or removed, and keep
interest separate from commitment. Custom action links remain secondary.

The legacy `import_mock_activities` command is disabled, including `--reset`;
use the explicitly invoked `seed_demo` workflow above. Its unused React fixture
was removed; source artwork used by the supported seeder remains available.

## Adding Images Later
When you’re ready for card artwork, place uploaded assets under `static/img/` (or another static directory) and reference them from the templates. Add an `image_url` field to `Activity` only once we have a real storage target.

## Local Data and Secrets

Django reads `DJANGO_SECRET_KEY` from the environment, or falls back to the
ignored `.django-secret-key` file. Keep this key private and persistent across
restarts. For deployments, set a fresh `DJANGO_SECRET_KEY`; do not reuse a key
from repository history.

SQLite databases, local environment files, uploaded media, virtual environments,
caches, and Windows download metadata are ignored. Keep local data on your
machine or back it up separately. Source artwork in `mock_images/` and `static/`
remains versioned.

Demo credentials are development-only and belong to the explicitly seeded
accounts. Personal browser-test accounts can also be created through signup.
