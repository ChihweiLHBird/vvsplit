#!/usr/bin/env bash
# Stage deployable static assets into ./dist (the directory Pulumi uploads).
# Single source of truth for "what ships". Run before `pulumi up`.
# Only the explicit manifest below ships. Ignored and untracked files are never
# inferred as deployable assets.
set -euo pipefail
cd "$(dirname "$0")/.."

ASSETS=(
  index.html
  styles.css
  main.py
  ui.py
  storage.py
  pyscript.toml
  sw.js
  manifest.webmanifest
  splitcore/__init__.py
  splitcore/model.py
  splitcore/calc.py
  icons/favicon.png
  icons/icon-192.png
  icons/icon-512.png
  icons/icon-512-maskable.png
  icons/apple-touch-icon.png
)

# Validate first so a missing source asset cannot destroy a previously staged
# artifact and leave an incomplete directory behind.
for asset in "${ASSETS[@]}"; do
  if [[ ! -f "$asset" ]]; then
    echo "Missing required deploy asset: $asset" >&2
    exit 1
  fi
done

mkdir -p dist
find dist -mindepth 1 -delete
for asset in "${ASSETS[@]}"; do
  mkdir -p "dist/$(dirname "$asset")"
  cp -p "$asset" "dist/$asset"
done

# Derive the service-worker cache version from the exact staged shell. The
# source sw.js is copied afresh before hashing, so identical inputs produce an
# identical key locally and in CI while any asset change advances the key.
cache_digest="$(python3 - "${ASSETS[@]}" <<'PY'
import hashlib
import pathlib
import sys

digest = hashlib.sha256()
for relative in sys.argv[1:]:
    digest.update(relative.encode("utf-8"))
    digest.update(b"\0")
    digest.update((pathlib.Path("dist") / relative).read_bytes())
    digest.update(b"\0")
print(digest.hexdigest()[:16])
PY
)"
sed "s|^const CACHE_VERSION = '.*';$|const CACHE_VERSION = 'bunnysplit-$cache_digest';|" \
  dist/sw.js > dist/sw.js.tmp
mv dist/sw.js.tmp dist/sw.js

echo "Staged $(find dist -type f | wc -l) files into dist/:"
find dist -type f | sort
