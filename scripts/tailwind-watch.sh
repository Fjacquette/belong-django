#!/usr/bin/env bash
set -euo pipefail

npx tailwindcss@3.4.13 \
  -i assets/tailwind.css \
  -o static/css/tailwind.css \
  --watch \
  --minify
