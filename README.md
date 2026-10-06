# Belong Django

Server-rendered Django app for Belong — a card-driven social experience using Tailwind CSS and HTMX.

## Stack
- Python 3.12, Django 5.x, SQLite (dev)
- Tailwind CLI (via `npx`) for styles
- HTMX (CDN script in base template)
- `uv` for dependency management

## Local dev and browser-test workflow

Requires Python 3.12+, `uv`, and Node.js/`npx` (for the dev Tailwind watcher).
Run commands from the main checkout:

```bash
# Dev: current feature source, Python/Tailwind watchers, foreground; Ctrl+C stops it
./start_belong.sh

# Product review: present exact committed HEAD, no PR merge required
./scripts/present-test.sh

# Explicitly return browser-test to current origin/master
./scripts/refresh-test.sh

# Start/restart the current browser-test revision in the background
./start_test.sh

# Stop only the managed browser-test process
./scripts/stop-test.sh
```

Dev runs at http://127.0.0.1:8000. Browser-test runs at
http://127.0.0.1:8001 with committed CSS and `--noreload`. Presentation installs
locked dependencies, checks Django, applies migrations, starts a background
server that survives the invoking task, and verifies HTTP readiness. It prints
`Browser-test ready at http://127.0.0.1:8001 — <short SHA>` only after success.
A newly created database is empty; signup and demo seeding remain explicit.

Normal Codex implementation iterations finish with a committed PR **already
running in browser-test**. Frank only reloads the browser. PR descriptions give
review pointers, not deployment commands. See AGENTS.md for the completion rule.

Browser-test is the ignored `.worktrees/test/` checkout, with its own `.venv`,
SQLite database, `.env.local`, and `.django-secret-key`. Presentation uses detached
HEAD at the exact feature commit; refresh returns it to the `browser-test` branch
tracking `origin/master`. The main dev branch is never switched by these tools.
This persistent product-review environment is separate from automated test databases.

Presentation refuses uncommitted tracked or untracked source in the main or test
checkout. Refresh permits unfinished main work but refuses test source changes
and local test commits. Ignored files are preserved, and revision switches refuse
to overwrite them if the target starts tracking those paths. Nothing is reset,
copied, deleted, or automatically reseeded. Migrations may update the test schema.

Ignored `.belong-runtime/` holds the operation lock, preview commit, process state,
and `browser-test.log`. Server ownership checks PID/start time, exact command,
and checkout before stopping a process. Readiness checks the owned listening
socket and login endpoint. Unknown port occupancy fails without killing anything;
stale PID state cannot authorize killing another process. Refresh stops and
restarts a managed server when returning to master; otherwise it only updates
source. Concurrent operations are refused. Failed startup clears PID state and
points to the log. These process checks require local Linux/WSL `/proc`.

An older foreground `start_test.sh` server has no managed PID state. Stop that
launcher once before adopting this workflow; presentation deliberately treats
it as unknown rather than killing a process based on port or command alone.

Dev and test use different session/CSRF cookie names because browsers share
cookies between localhost ports. Both bind only to `127.0.0.1`; no public deployment,
firewall configuration, production setup, Docker, or systemd is involved.

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
After setting up browser-test once with `./start_test.sh`, use
`./scripts/stop-test.sh` if it is running, then populate
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

## Discover facets and structured costs

Discover has four checkbox menus: When, Where, Cost and Open to. Multiple choices
within a menu OR together; menus AND together. An empty menu is unrestricted.
Changes apply immediately while Search/Enter commits text. Menus preserve keyboard
position across filter submissions; without JavaScript use Apply filters. Show hidden
is a separate private list control. There is no Advanced filters or top-level Category.

Where offers Online and distance buckets under 1 / 1–3 / 3–5 / 5–10 / 10–25 / 25+
miles. Distances require browser location and valid activity coordinates; only
in-person/hybrid activities match physical buckets. Hybrid also matches Online.
Denied/unavailable geolocation clears distance choices with feedback and preserves
other selections. Repeated facet values survive pagination and participation changes.

Paid tiers use the optional exact USD `cost_amount` field, with Free and $ through
$$$$$ shorthand. Decimal amounts use disjoint positive ranges through 10, 25, 50,
100 and over 100. Existing arbitrary display strings are never parsed for filtering.
Human-readable/exact costs remain visible on cards. The schema migration leaves
existing amounts unknown; the demo migration populates only authored prices on
tracked activities with unchanged ownership/type/display and no existing amount.

## Tailwind Production Build

`DESIGN_SYSTEM.md` and `assets/tailwind.css` define reusable `ui-*` families for
actions, navigation, fields, filters, disclosures, menus, and response/view state.
Use those classes instead of adding a local border/height/color recipe. Default
controls are 40px, dense card controls 36px, form/detail controls 44px, and the
floating Create is 48px. Page gutters are shared at 24/32/40px.

Cards are 440px tall at a stable preferred/max width of 258px. Band 1 shows the
name plus readable when/where; Band 2 shows organizer and audience/cost with
a compact organizer avatar. The 160px stack offset exposes both top bands.
The 128px image and 104px description region preserve the portrait balance.
The 48px take-action band contains only one or two complete response labels;
a second choice appears only when it fits without clipping. Remaining choices
are on Details. Title navigation opens the detail page for counts, Hide/Unhide
and response removal. The image band contains only image/fallback artwork;
compact cards have no generic utility menu or response counts.
A selected direct response clears on repeat-click. Current state is visible through
the first direct button or a body line for later choices; full truncated descriptive
values remain available on focus/hover.

The demo response migration updates only known seed-owned legacy default sets,
including the former Interested/Count me in/Question trio. Custom choices,
transferred activities, and real/custom response records are preserved. A follow-up
migration reconciles only tracked stale sample Interested responses against the
exact curated choices, demo user and organizer ownership. New seeds
use activity-specific choices and sample responses; no automatic reseed is needed.

For a one-off build (e.g., before deploying), run:
```bash
source .venv/bin/activate
npx tailwindcss@3.4.13 -i assets/tailwind.css -o static/css/tailwind.css --minify
```

Tailwind scans templates, local JavaScript (including dynamically added stack classes),
and the app Python form files containing literal widget
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
links render as `#`. New activities default only to Interested, a low-friction
expression of proto-intent.
Creators explicitly opt into stronger or context-specific choices such as Count me in,
Tell me more, I have a question, Vote on details, or Cannot make it when appropriate.
Existing creator-selected choices remain intact. The legacy join shortcut uses the
first creator-selected choice and remains idempotent; it does not impose an RSVP pair.
Cards offer the first two creator-selected response buttons; activity
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

## Groups foundation

The floating **+** opens a small create chooser: Activity first, Group second.
Groups are persistent people/context, separate from activities and the existing
personal FriendGroup lists. Create a group with a name, description, and access
mode; its creator becomes the primary organizer and an active member.
The four modes are **Open** (visible, immediate join), **Closed** (visible, request
approval), **Unlisted** (not proactively surfaced, immediate join through a link or
linked activity), and **Private** (hidden from nonmembers, invitation only).
There is no group directory or group feed. Member rosters are visible
only to active members/organizers, while Open/Closed/Unlisted visitors see identity and
member count.

Open and Unlisted groups admit members immediately; Closed groups create pending requests
that organizers can approve or decline. Invitation-only groups block self-joining;
email invitations and invite-based joining arrive in #22. Accepting a valid private
invitation will grant membership directly, without another approval step; invitation
authority remains a separate organizer-controlled capability for that slice.
Owners/organizers can block and unblock membership. Blocked users cannot join,
request membership, or erase a block by leaving; blocking does not change independent
activity participation. Only the owner can block another organizer; the owner cannot
be blocked. Members can leave or
cancel requests; the primary organizer cannot leave or demote themselves. Only
the primary organizer appoints/removes additional organizers; additional organizers
can approve requests and create linked activities. Group settings and membership
also have Django admin support. No invitation button is shown before it works.

Activity creation has an optional Group selector restricted to groups the creator
organizes. Activities keep their existing audience/response rules regardless of
group membership; linking a group does not grant access to either private group
details or restricted activities. Deleting a group preserves its activities by
clearing their group reference. Existing activities and personal friend lists are
left intact by the migrations. The access-mode migration retains group identity,
owners, memberships, and activity links. Legacy private groups stay Private;
unlisted groups become Unlisted; public open/approval groups become Open/Closed.
Legacy public invitation-only groups become Private to retain the membership
restriction. Existing pending memberships are retained rather than auto-approved.

## Pilot discovery and presence

Discover uses the four faceted menus described above. Search submits only on
Search/Enter. Stacked / Spread out is a local view preference on the results utility
line; it changes overlap without querying the server. Empty results keep the same
Discover/friends layout and menus so individual selections can be cleared.
Time filters and datetime-local creation fields use America/New_York, including DST.
Device coordinates stay in the query, not the user's profile; distance uses Haversine
on valid latitude/longitude. These are pilot filters, not a geospatial service.

Hide is a unique private user/activity preference. It never changes a response or
informs the organizer. Normal discovery excludes hidden activities; the separate
Show hidden control permits recovery with Unhide. Creators choose from six response
types: Interested, Count me in, I have a question, Cannot make it, Tell me more, and
Vote on details. One or two whole labels appear directly when they fit; Details
exposes all. Repeating a selected response clears it.

Presence records authenticated HTTP requests, throttled to at most one update per
minute: **Active** within 5 minutes, **Idle** within 30, **Offline** after 30 minutes
or with no recorded activity. Creating a profile or changing a status does not mark
someone Active. These are activity-based hints, not real-time/socket connection state.
