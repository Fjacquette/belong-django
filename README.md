# Belong Django

Server-rendered Django app for Belong — a card-driven social experience using Tailwind CSS and HTMX.

## Stack
- Python 3.12, Django 5.x, SQLite (dev)
- Tailwind CLI (via `npx`) for styles
- HTMX (CDN script in base template)
- `uv` for dependency management

## Getting Started (macOS/Linux/WSL)
```bash
# 1. Install dependencies into a virtualenv managed by uv
uv sync

# 2. Activate the environment
source .venv/bin/activate

# 3. Run migrations
python manage.py migrate

# 4. Seed demo data (creates admin/admin123 + demo/demo123)
python manage.py seed_demo
```

## Run Dev Workflow
Open two terminals:

Terminal A — Tailwind watch:
```bash
source .venv/bin/activate
npx tailwindcss@3.4.13 -i assets/tailwind.css -o static/css/tailwind.css --watch --minify
# or: scripts/tailwind-watch.sh
```

Terminal B — Django server:
```bash
source .venv/bin/activate
python manage.py runserver
```

Visit http://127.0.0.1:8000 and log in with `demo/demo123` to try joining events via HTMX without reloading the page.

## Seeding Notes
The `seed_demo` command is idempotent; re-running it won’t duplicate activities already created by the admin host.

## Tailwind Production Build
For a one-off build (e.g., before deploying), run:
```bash
source .venv/bin/activate
npx tailwindcss@3.4.13 -i assets/tailwind.css -o static/css/tailwind.css --minify
```

## Adding Images Later
When you’re ready for card artwork, place uploaded assets under `static/img/` (or another static directory) and reference them from the templates. Add an `image_url` field to `Activity` only once we have a real storage target.
